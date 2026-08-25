import hmac

from fastapi import Header, HTTPException, Request

from . import db, security


async def get_conn(request: Request):
    return request.app.state.conn


async def get_settings(request: Request):
    return request.app.state.settings


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要 Bearer Token")
    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="需要 Bearer Token")
    return token


async def current_account(request: Request, authorization: str | None = Header(None)):
    """GLA- 账号 Token → 用户行。"""
    settings = request.app.state.settings
    token = _bearer(authorization)
    if not token.startswith("GLA-"):
        raise HTTPException(status_code=401, detail="需要账号 Token (GLA-)")
    payload = security.verify_payload(token, settings.secret_key)
    if not payload or payload.get("kind") != "account":
        raise HTTPException(status_code=401, detail="账号 Token 无效或已过期")
    cursor = await request.app.state.conn.execute(
        "SELECT * FROM users WHERE id=?", (payload["uid"],)
    )
    user = await cursor.fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user["banned"]:
        raise HTTPException(status_code=403, detail="账号已被封禁")
    return user


async def resolve_account_optional(request: Request):
    """尽力解析 GLA-,失败返回 None(不抛错)。"""
    authorization = request.headers.get("authorization", "")
    try:
        return await current_account(request, authorization)
    except HTTPException:
        return None


ActorIdentity = tuple[str, object, object | None]


async def current_actor(request: Request, authorization: str | None = Header(None)):
    """GLS- 或 GLA- 均可 → (kind, user_row, agent_row|None)。"""
    conn = request.app.state.conn
    token = _bearer(authorization)
    if token.startswith("GLS-"):
        cursor = await conn.execute(
            "SELECT a.*, u.banned AS owner_banned FROM agents a "
            "JOIN users u ON u.id=a.owner_id WHERE a.token_hash=?",
            (security.sha256_hex(token),),
        )
        agent = await cursor.fetchone()
        if agent is None or agent["revoked"]:
            raise HTTPException(status_code=401, detail="Agent Token 无效或已被吊销")
        if agent["owner_banned"]:
            raise HTTPException(status_code=403, detail="账号已被封禁")
        await conn.execute(
            "UPDATE agents SET last_used_at=datetime('now') WHERE id=?", (agent["id"],)
        )
        await conn.commit()
        cursor = await conn.execute(
            "SELECT * FROM users WHERE id=?", (agent["owner_id"],)
        )
        user = await cursor.fetchone()
        return ("agent", user, agent)
    if token.startswith("GLA-"):
        user = await current_account(request, authorization)
        return ("user", user, None)
    raise HTTPException(status_code=401, detail="无法识别的 Token")


async def require_forum_enabled(request: Request) -> None:
    enabled = await db.get_setting(request.app.state.conn, "forum_enabled")
    if enabled != "1":
        raise HTTPException(status_code=403, detail="论坛已关闭")


async def require_registry_enabled(request: Request) -> None:
    enabled = await db.get_setting(request.app.state.conn, "registry_enabled")
    if enabled != "1":
        raise HTTPException(status_code=403, detail="模块注册表已关闭")


async def require_admin(request: Request) -> None:
    settings = request.app.state.settings
    raw = request.cookies.get("gadmin", "")
    if security.read_cookie(raw, settings.secret_key) != "admin":
        raise HTTPException(status_code=401, detail="管理员未登录")


def actor_display(kind: str, user, agent) -> str:
    if agent is not None:
        return f"{agent['name']}(@{user['login']})"
    return f"@{user['login']}"


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
