import urllib.parse
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from .. import github_oauth, security

router = APIRouter()

ACCOUNT_TTL = 90 * 24 * 3600
SESSION_TTL = 30 * 24 * 3600


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


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
    try:
        access_token = await github_oauth.exchange_code(
            code,
            settings.oauth_client_id,
            settings.oauth_client_secret,
            settings.public_base_url.rstrip("/") + "/oauth/cli/callback",
        )
        return await github_oauth.fetch_user(access_token)
    except github_oauth.GitHubOAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/oauth/cli/start")
async def cli_start(request: Request, port: int, nonce: str = ""):
    settings = request.app.state.settings
    if not (1024 <= port <= 65535):
        raise HTTPException(status_code=400, detail="port 无效")
    if not nonce:
        raise HTTPException(status_code=400, detail="nonce 不能为空")
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
    session_id = "gs-" + secrets.token_hex(20)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    await conn.execute(
        "INSERT INTO sessions(id, user_id, expires_at) VALUES(?,?,?)",
        (session_id, user["id"], expires_at),
    )
    await conn.commit()
    resp = RedirectResponse(next_path, status_code=303)
    resp.set_cookie(
        "gsession", session_id, max_age=SESSION_TTL, httponly=True, samesite="lax"
    )
    return resp
