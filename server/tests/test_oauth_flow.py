import urllib.parse
import sqlite3

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


def test_web_session_persists_in_db(client, monkeypatch):
    """网页登录后会话落在 sessions 表,cookie 只是随机 id(重启不失效)。"""
    _fake_github(monkeypatch)
    start = client.get("/oauth/web/start?next=/me", follow_redirects=False)
    state = urllib.parse.parse_qs(
        urllib.parse.urlparse(start.headers["location"]).query
    )["state"][0]
    cb = client.get(
        f"/oauth/web/callback?code=abc&state={urllib.parse.quote(state)}",
        follow_redirects=False,
    )
    session_id = client.cookies.get("gsession")
    assert session_id.startswith("gs-")
    # cookie 是随机 id 而非签名载荷
    assert "user|" not in session_id
    # 服务端有对应行
    conn = sqlite3.connect(client.app.state.settings.db_path)
    row = conn.execute(
        "SELECT user_id, expires_at, revoked FROM sessions WHERE id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] >= 1
    # cookie 直接可换回身份
    info = client.get("/me/session")
    assert info.json()["user"]["login"] == "alice"


def test_web_session_revoked_rejected(client, monkeypatch):
    """吊销或过期后,同一 cookie 不再有效。"""
    _fake_github(monkeypatch)
    start = client.get("/oauth/web/start", follow_redirects=False)
    state = urllib.parse.parse_qs(
        urllib.parse.urlparse(start.headers["location"]).query
    )["state"][0]
    client.get(
        f"/oauth/web/callback?code=abc&state={urllib.parse.quote(state)}",
        follow_redirects=False,
    )
    session_id = client.cookies.get("gsession")
    conn = sqlite3.connect(client.app.state.settings.db_path)
    conn.execute(
        "UPDATE sessions SET revoked=1 WHERE id=?", (session_id,)
    )
    conn.commit()
    conn.close()
    assert client.get("/me/session").json()["user"] is None
