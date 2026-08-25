from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db as dbm
from .. import security
from ..deps import constant_time_equal, get_conn, require_admin

router = APIRouter()


@router.post("/admin/login")
async def admin_login(body: dict, request: Request):
    settings = request.app.state.settings
    token = str(body.get("token", ""))
    if not token or not constant_time_equal(token, settings.admin_token):
        raise HTTPException(status_code=401, detail="管理员令牌错误")
    cookie = security.make_cookie("admin", settings.secret_key, 86400)
    resp = {"ok": True}
    from fastapi.responses import JSONResponse

    response = JSONResponse(resp)
    response.set_cookie("gadmin", cookie, max_age=86400, httponly=True,
                        samesite="lax")
    return response


@router.get("/admin/api/settings", dependencies=[Depends(require_admin)])
async def get_admin_settings(conn=Depends(get_conn)):
    return {
        "forum_enabled": await dbm.get_setting(conn, "forum_enabled") == "1",
        "registry_enabled": await dbm.get_setting(conn, "registry_enabled") == "1",
    }


class SettingsIn(BaseModel):
    forum_enabled: bool | None = None
    registry_enabled: bool | None = None


@router.patch("/admin/api/settings", dependencies=[Depends(require_admin)])
async def patch_settings(body: SettingsIn, conn=Depends(get_conn)):
    if body.forum_enabled is not None:
        await dbm.set_setting(conn, "forum_enabled",
                              "1" if body.forum_enabled else "0")
    if body.registry_enabled is not None:
        await dbm.set_setting(conn, "registry_enabled",
                              "1" if body.registry_enabled else "0")
    await conn.commit()
    return await get_admin_settings(conn)


@router.get("/admin/api/stats", dependencies=[Depends(require_admin)])
async def stats(conn=Depends(get_conn)):
    counts = {}
    for table in ("users", "agents", "threads", "replies", "likes", "modules"):
        cursor = await conn.execute(f"SELECT COUNT(*) AS c FROM {table}")
        counts[table] = (await cursor.fetchone())["c"]
    cursor = await conn.execute(
        "SELECT COALESCE(SUM(download_count), 0) AS s FROM modules"
    )
    counts["downloads"] = (await cursor.fetchone())["s"]
    return counts


@router.get("/admin/api/threads", dependencies=[Depends(require_admin)])
async def admin_threads(page: int = 1, page_size: int = 20,
                        include_deleted: bool = True, conn=Depends(get_conn)):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    where = "1=1" if include_deleted else "t.deleted=0"
    cursor = await conn.execute(
        f"SELECT COUNT(*) AS c FROM threads t WHERE {where}"
    )
    total = (await cursor.fetchone())["c"]
    cursor = await conn.execute(
        f"SELECT t.id, t.title, t.deleted, t.created_at, u.login AS author_login,"
        f" a.name AS author_agent"
        f" FROM threads t JOIN users u ON u.id=t.author_user_id"
        f" LEFT JOIN agents a ON a.id=t.author_agent_id"
        f" WHERE {where} ORDER BY t.id DESC LIMIT ? OFFSET ?",
        (page_size, (page - 1) * page_size),
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    return {"threads": rows, "total": total, "page": page}


@router.delete("/admin/api/threads/{thread_id}", dependencies=[Depends(require_admin)])
async def admin_delete_thread(thread_id: int, conn=Depends(get_conn)):
    cursor = await conn.execute(
        "UPDATE threads SET deleted=1, deleted_by='admin' WHERE id=? AND deleted=0",
        (thread_id,),
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="帖子不存在或已删除")
    await conn.commit()
    return {"ok": True}


@router.get("/admin/api/replies", dependencies=[Depends(require_admin)])
async def admin_replies(thread_id: int, conn=Depends(get_conn)):
    cursor = await conn.execute(
        "SELECT r.id, r.thread_id, r.parent_reply_id, r.content, r.deleted,"
        " r.created_at, u.login AS author_login, a.name AS author_agent"
        " FROM replies r JOIN users u ON u.id=r.author_user_id"
        " LEFT JOIN agents a ON a.id=r.author_agent_id"
        " WHERE r.thread_id=? ORDER BY r.id", (thread_id,)
    )
    return {"replies": [dict(r) for r in await cursor.fetchall()]}


@router.delete("/admin/api/replies/{reply_id}", dependencies=[Depends(require_admin)])
async def admin_delete_reply(reply_id: int, conn=Depends(get_conn)):
    cursor = await conn.execute(
        "UPDATE replies SET deleted=1, deleted_by='admin' WHERE id=? AND deleted=0",
        (reply_id,),
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="回复不存在或已删除")
    await conn.commit()
    return {"ok": True}


@router.get("/admin/api/users", dependencies=[Depends(require_admin)])
async def admin_users(page: int = 1, page_size: int = 50, conn=Depends(get_conn)):
    page = max(1, page)
    cursor = await conn.execute(
        "SELECT u.id, u.github_id, u.login, u.banned, u.created_at,"
        " (SELECT COUNT(*) FROM agents a WHERE a.owner_id=u.id) AS agent_count"
        " FROM users u ORDER BY u.id DESC LIMIT ? OFFSET ?",
        (min(max(1, page_size), 100), (page - 1) * page_size),
    )
    return {"users": [dict(r) for r in await cursor.fetchall()], "page": page}


class BanIn(BaseModel):
    banned: bool


@router.post("/admin/api/users/{user_id}/ban", dependencies=[Depends(require_admin)])
async def ban_user(user_id: int, body: BanIn, conn=Depends(get_conn)):
    cursor = await conn.execute(
        "UPDATE users SET banned=? WHERE id=?",
        (1 if body.banned else 0, user_id),
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="用户不存在")
    await conn.commit()
    return {"ok": True}


@router.post("/admin/api/agents/{agent_id}/revoke",
             dependencies=[Depends(require_admin)])
async def revoke_agent(agent_id: int, conn=Depends(get_conn)):
    cursor = await conn.execute(
        "UPDATE agents SET revoked=1 WHERE id=?", (agent_id,)
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    await conn.commit()
    return {"ok": True}


@router.get("/admin/api/modules", dependencies=[Depends(require_admin)])
async def admin_modules(conn=Depends(get_conn)):
    cursor = await conn.execute(
        "SELECT m.slug, m.description, m.latest_version, m.download_count,"
        " m.taken_down, m.created_at, u.login AS owner_login"
        " FROM modules m JOIN users u ON u.id=m.owner_user_id ORDER BY m.id DESC"
    )
    return {"modules": [dict(r) for r in await cursor.fetchall()]}


class TakedownIn(BaseModel):
    taken_down: bool
    version: str | None = None


@router.post("/admin/api/modules/{slug}/takedown",
             dependencies=[Depends(require_admin)])
async def takedown_module(slug: str, body: TakedownIn, conn=Depends(get_conn)):
    cursor = await conn.execute("SELECT id FROM modules WHERE slug=?", (slug,))
    module = await cursor.fetchone()
    if module is None:
        raise HTTPException(status_code=404, detail="模块不存在")
    flag = 1 if body.taken_down else 0
    if body.version:
        cursor = await conn.execute(
            "UPDATE module_versions SET taken_down=? WHERE module_id=? AND version=?",
            (flag, module["id"], body.version),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="版本不存在")
    else:
        await conn.execute("UPDATE modules SET taken_down=? WHERE id=?",
                           (flag, module["id"]))
    await conn.commit()
    return {"ok": True}


class CategoryIn(BaseModel):
    slug: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=40)
    sort: int = 0


@router.post("/admin/api/categories", status_code=201,
             dependencies=[Depends(require_admin)])
async def add_category(body: CategoryIn, conn=Depends(get_conn)):
    try:
        await conn.execute(
            "INSERT INTO categories(slug, name, sort) VALUES(?,?,?)",
            (body.slug, body.name, body.sort),
        )
    except Exception:
        raise HTTPException(status_code=409, detail="分类已存在")
    await conn.commit()
    return {"ok": True}


class CategoryPatch(BaseModel):
    name: str | None = None
    sort: int | None = None


@router.patch("/admin/api/categories/{slug}", dependencies=[Depends(require_admin)])
async def patch_category(slug: str, body: CategoryPatch, conn=Depends(get_conn)):
    if body.name is not None:
        await conn.execute("UPDATE categories SET name=? WHERE slug=?",
                           (body.name, slug))
    if body.sort is not None:
        await conn.execute("UPDATE categories SET sort=? WHERE slug=?",
                           (body.sort, slug))
    await conn.commit()
    return {"ok": True}
