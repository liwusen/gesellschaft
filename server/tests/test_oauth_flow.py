import urllib.parse

from app.routers import oauth as oauth_router


def _fake_github(monkeypatch, login="alice"):
    calls = {}

    async def fake_exchange(code, cid, cs, redirect_uri):
        calls["code"] = code
        calls["redirect_uri"] = redirect_uri
        return "gh-token"

    async def fake_fetch_user(token):
        calls["token"] = token
        return {"github_id": 424242, "login": login, "avatar_url": ""}

    monkeypatch.setattr(oauth_router.github_oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(oauth_router.github_oauth, "fetch_user", fake_fetch_user)
    return calls


def test_cli_flow_returns_token_to_loopback(client, monkeypatch):
    calls = _fake_github(monkeypatch)
    start = client.get("/oauth/cli/start?port=9876&nonce=n0nce",
                       follow_redirects=False)
    assert start.status_code == 302
    gh_url = start.headers["location"]
    assert "github.com/login/oauth/authorize" in gh_url
    state = urllib.parse.parse_qs(
        urllib.parse.urlparse(gh_url).query
    )["state"][0]

    cb = client.get(
        f"/oauth/cli/callback?code=abc&state={urllib.parse.quote(state)}",
        follow_redirects=False,
    )
    assert cb.status_code == 302
    loc = cb.headers["location"]
    assert loc.startswith("http://127.0.0.1:9876/callback?")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
    assert q["nonce"] == ["n0nce"]
    tok = q["account_token"][0]
    assert tok.startswith("GLA-")
    me = client.get("/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    assert me.json()["user"]["login"] == "alice"
    assert calls["token"] == "gh-token"


def test_cli_start_rejects_bad_port(client):
    resp = client.get("/oauth/cli/start?port=80", follow_redirects=False)
    assert resp.status_code == 400


def test_cli_callback_bad_state(client):
    resp = client.get("/oauth/cli/callback?code=abc&state=bogus")
    assert resp.status_code == 400


def test_web_login_sets_cookie_and_session(client, monkeypatch):
    _fake_github(monkeypatch)
    start = client.get("/oauth/web/start?next=/me", follow_redirects=False)
    assert start.status_code == 302
    state = urllib.parse.parse_qs(
        urllib.parse.urlparse(start.headers["location"]).query
    )["state"][0]
    cb = client.get(
        f"/oauth/web/callback?code=abc&state={urllib.parse.quote(state)}",
        follow_redirects=False,
    )
    assert cb.status_code == 303
    assert cb.headers["location"] == "/me"
    assert "gsession=" in cb.headers.get("set-cookie", "")
    info = client.get("/me/session")
    assert info.json()["user"]["login"] == "alice"


def test_web_next_open_redirect_blocked(client, monkeypatch):
    _fake_github(monkeypatch)
    start = client.get("/oauth/web/start?next=//evil.example",
                       follow_redirects=False)
    state = urllib.parse.parse_qs(
        urllib.parse.urlparse(start.headers["location"]).query
    )["state"][0]
    cb = client.get(
        f"/oauth/web/callback?code=abc&state={urllib.parse.quote(state)}",
        follow_redirects=False,
    )
    assert cb.headers["location"] == "/"
