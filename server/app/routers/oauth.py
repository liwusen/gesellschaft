import urllib.parse

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from .. import github_oauth, security

router = APIRouter()

ACCOUNT_TTL = 90 * 24 * 3600
SESSION_TTL = 30 * 24 * 3600


def _safe_next(next_path: str) -> str:
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/"
    return next_path


async def upsert_user(conn, info: dict):
    await conn.execute(
        "INSERT INTO users(github_id, login, avatar_url) VALUES(?,?,?) "
        "ON CONFLICT(github_id) DO UPDATE SET login=excluded.login, "
        "avatar_url=excluded.avatar_url",
        (info["github_id"], info["login"], info["avatar_url"]),
    )
    cursor = await conn.execute(
        "SELECT * FROM users WHERE github_id=?", (info["github_id"],)
    )
    row = await cursor.fetchone()
    await conn.commit()
    return row


async def _complete_login(request: Request, code: str) -> dict | None:
    settings = request.app.state.settings
    access_token = await github_oauth.exchange_code(
        code,
        settings.oauth_client_id,
        settings.oauth_client_secret,
        settings.public_base_url.rstrip("/") + "/oauth/cli/callback",
    )
    if not access_token:
        return None
    return await github_oauth.fetch_user(access_token)


@router.get("/oauth/cli/start")
async def cli_start(request: Request, port: int, nonce: str = ""):
    settings = request.app.state.settings
    if not (1024 <= port <= 65535):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="port 无效")
    state = security.make_cookie(f"cli|{port}|{nonce}", settings.secret_key, 600)
    url = github_oauth.build_authorize_url(
        settings.oauth_client_id,
        settings.public_base_url.rstrip("/") + "/oauth/cli/callback",
        state,
    )
    return RedirectResponse(url, status_code=302)


@router.get("/oauth/cli/callback")
async def cli_callback(request: Request, code: str = "", state: str = ""):
    from fastapi import HTTPException

    conn = request.app.state.conn
    settings = request.app.state.settings
    blob = security.read_cookie(state, settings.secret_key)
    if not blob or not blob.startswith("cli|"):
        raise HTTPException(status_code=400, detail="state 无效或已过期，请重新 gesellschaft login")
    _, port, nonce = blob.split("|", 2)
    info = await _complete_login(request, code)
    if info is None:
        raise HTTPException(status_code=502, detail="GitHub 未返回 access_token")
    user = await upsert_user(conn, info)
    account_token = security.sign_payload(
        {"uid": user["id"], "kind": "account"}, settings.secret_key, ACCOUNT_TTL
    )
    target = (
        f"http://127.0.0.1:{int(port)}/callback"
        f"?nonce={urllib.parse.quote(nonce)}"
        f"&account_token={urllib.parse.quote(account_token)}"
    )
    return RedirectResponse(target, status_code=302)


@router.get("/oauth/web/start")
async def web_start(request: Request, next_path: str = Query("", alias="next")):
    settings = request.app.state.settings
    next_path = _safe_next(next_path)
    state = security.make_cookie(f"web|{next_path}", settings.secret_key, 600)
    url = github_oauth.build_authorize_url(
        settings.oauth_client_id,
        settings.public_base_url.rstrip("/") + "/oauth/web/callback",
        state,
    )
    return RedirectResponse(url, status_code=302)


@router.get("/oauth/web/callback")
async def web_callback(request: Request, code: str = "", state: str = ""):
    from fastapi import HTTPException

    conn = request.app.state.conn
    settings = request.app.state.settings
    blob = security.read_cookie(state, settings.secret_key)
    if not blob or not blob.startswith("web|"):
        raise HTTPException(status_code=400, detail="state 无效或已过期，请重新登录")
    next_path = _safe_next(blob.split("|", 1)[1])
    info = await _complete_login(request, code)
    if info is None:
        raise HTTPException(status_code=502, detail="GitHub 未返回 access_token")
    user = await upsert_user(conn, info)
    session = security.make_cookie(f"user|{user['id']}", settings.secret_key, SESSION_TTL)
    resp = RedirectResponse(next_path, status_code=303)
    resp.set_cookie(
        "gsession", session, max_age=SESSION_TTL, httponly=True, samesite="lax"
    )
    return resp
