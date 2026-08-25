from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import security
from ..deps import current_account, current_actor, get_conn, user_from_session

router = APIRouter()

AGENT_CAP = 10


@router.get("/me/session")
async def session_info(request: Request):
    user = await user_from_session(request)
    if user is None:
        return {"user": None}
    return {
        "user": {
            "id": user["id"],
            "github_id": user["github_id"],
            "login": user["login"],
            "avatar_url": user["avatar_url"],
        }
    }


@router.get("/me")
async def whoami(user=Depends(current_account), conn=Depends(get_conn)):
    cursor = await conn.execute(
        "SELECT id, name, persona, revoked, created_at FROM agents "
        "WHERE owner_id=? ORDER BY id DESC",
        (user["id"],),
    )
    agents = await cursor.fetchall()
    return {
        "user": {
            "id": user["id"],
            "login": user["login"],
            "avatar_url": user["avatar_url"],
        },
        "agents": [dict(a) for a in agents],
    }


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    persona: str = Field(default="", max_length=500)


@router.post("/me/agents", status_code=201)
async def create_agent(body: AgentIn, user=Depends(current_account),
                       conn=Depends(get_conn)):
    cursor = await conn.execute(
        "SELECT COUNT(*) AS c FROM agents WHERE owner_id=? AND revoked=0",
        (user["id"],),
    )
    row = await cursor.fetchone()
    if row["c"] >= AGENT_CAP:
        raise HTTPException(status_code=400, detail=f"Agent 数量已达上限({AGENT_CAP})")
    token = security.new_agent_token()
    cursor = await conn.execute(
        "INSERT INTO agents(owner_id, name, persona, token_hash) VALUES(?,?,?,?)",
        (user["id"], body.name, body.persona, security.sha256_hex(token)),
    )
    agent_id = cursor.lastrowid
    await conn.commit()
    return {"agent_id": agent_id, "name": body.name, "token": token}


@router.delete("/me/agents/{agent_id}")
async def revoke_agent(agent_id: int, user=Depends(current_account),
                       conn=Depends(get_conn)):
    cursor = await conn.execute(
        "UPDATE agents SET revoked=1 WHERE id=? AND owner_id=?", (agent_id, user["id"])
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    await conn.commit()
    return {"ok": True}


@router.get("/me/notifications")
async def notifications(actor=Depends(current_actor), conn=Depends(get_conn)):
    kind, user = actor[0], actor[1]
    cursor = await conn.execute(
        "SELECT n.type, n.actor_name, n.excerpt, n.thread_id, n.read, n.created_at "
        "FROM notifications n WHERE n.user_id=? ORDER BY n.id DESC LIMIT 100",
        (user["id"],),
    )
    items = await cursor.fetchall()
    await conn.execute(
        "UPDATE notifications SET read=1 WHERE user_id=? AND read=0", (user["id"],)
    )
    await conn.commit()
    return {"items": [dict(i) for i in items]}


@router.get("/me/notifications/web")
async def notifications_web(request: Request, conn=Depends(get_conn)):
    """网页会话版通知(gsession cookie)。"""
    user = await user_from_session(request)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    cursor = await conn.execute(
        "SELECT n.type, n.actor_name, n.excerpt, n.thread_id, n.read,"
        " n.created_at FROM notifications n WHERE n.user_id=?"
        " ORDER BY n.id DESC LIMIT 100",
        (user["id"],),
    )
    items = [dict(i) for i in await cursor.fetchall()]
    await conn.execute(
        "UPDATE notifications SET read=1 WHERE user_id=? AND read=0", (user["id"],)
    )
    await conn.commit()
    return {"items": items}
