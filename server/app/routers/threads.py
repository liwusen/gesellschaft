import math

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import db as dbm
from .. import serializers
from ..deps import (current_actor, get_conn, require_forum_enabled)

router = APIRouter()


class ThreadIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=8000)
    category: str = "chat"


class ReplyIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_reply_id: int | None = None


THREAD_SELECT = f"""
SELECT t.id, t.title, t.content, t.created_at,
       c.slug AS category, c.name AS category_name,
       {serializers.AUTHOR_EXPR} AS author,
       t.author_user_id,
       (SELECT COUNT(*) FROM replies r
        WHERE r.thread_id=t.id AND r.deleted=0) AS reply_count,
       (SELECT COUNT(*) FROM likes l
        WHERE l.target_type='thread' AND l.target_id=t.id) AS like_count
FROM threads t
JOIN categories c ON c.id=t.category_id
JOIN users u ON u.id=t.author_user_id
LEFT JOIN agents a ON a.id=t.author_agent_id
"""

REPLY_SELECT = f"""
SELECT r.id, r.parent_reply_id, r.content, r.created_at,
       {serializers.AUTHOR_EXPR} AS author, r.author_user_id,
       (SELECT COUNT(*) FROM likes l
        WHERE l.target_type='reply' AND l.target_id=r.id) AS like_count
FROM replies r
JOIN users u ON u.id=r.author_user_id
LEFT JOIN agents a ON a.id=r.author_agent_id
"""


def _write_allowed(request: Request, kind: str, user) -> None:
    if not request.app.state.write_limiter.allow(f"{kind}:{user['id']}"):
        raise HTTPException(status_code=429, detail="操作过于频繁，稍后再试")


async def _notify(conn, recipient_id, actor_name: str, ntype: str,
                  thread_id: int, excerpt: str) -> None:
    if recipient_id is None:
        return
    await conn.execute(
        "INSERT INTO notifications(user_id, actor_name, type, thread_id, excerpt)"
        " VALUES(?,?,?,?,?)",
        (recipient_id, actor_name, ntype, thread_id, excerpt[:120]),
    )


@router.get("/categories")
async def categories(conn=Depends(get_conn)):
    cursor = await conn.execute("SELECT slug, name FROM categories ORDER BY sort")
    rows = await cursor.fetchall()
    return {"categories": [dict(r) for r in rows]}


@router.get("/threads")
async def list_threads(request: Request, page: int = 1, page_size: int = 20,
                       category: str = "", format: str = "json",
                       conn=Depends(get_conn),
                       _forum=Depends(require_forum_enabled)):
    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    where = "t.deleted=0"
    args: list = []
    if category:
        where += " AND c.slug=?"
        args.append(category)
    cursor = await conn.execute(
        f"SELECT COUNT(*) AS c FROM threads t "
        f"JOIN categories c ON c.id=t.category_id WHERE {where}", args
    )
    total = (await cursor.fetchone())["c"]
    args.extend([page_size, (page - 1) * page_size])
    cursor = await conn.execute(
        THREAD_SELECT + f" WHERE {where} ORDER BY t.id DESC LIMIT ? OFFSET ?", args
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    if format == "text":
        return Response(serializers.threads_text(rows), media_type="text/plain; charset=utf-8")
    return {"threads": rows, "total": total, "page": page, "page_size": page_size}


@router.post("/threads", status_code=201)
async def create_thread(body: ThreadIn, request: Request,
                        actor=Depends(current_actor), conn=Depends(get_conn)):
    await require_forum_enabled(request)
    kind, user, agent = actor
    _write_allowed(request, kind, user)
    cursor = await conn.execute(
        "SELECT id FROM categories WHERE slug=?", (body.category,)
    )
    cat = await cursor.fetchone()
    if cat is None:
        raise HTTPException(status_code=400, detail="分类不存在")
    cursor = await conn.execute(
        "INSERT INTO threads(category_id, author_user_id, author_agent_id,"
        " title, content) VALUES(?,?,?,?,?)",
        (cat["id"], user["id"], agent["id"] if agent else None,
         body.title, body.content),
    )
    thread_id = cursor.lastrowid
    await conn.commit()
    author = f"{agent['name']}(@{user['login']})" if agent else f"@{user['login']}"
    return {
        "id": thread_id,
        "title": body.title,
        "category": body.category,
        "author": author,
    }


@router.get("/threads/{thread_id}")
async def thread_detail(thread_id: int, request: Request, page: int = 1,
                        page_size: int = 20, format: str = "json",
                        conn=Depends(get_conn),
                        _forum=Depends(require_forum_enabled)):
    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    cursor = await conn.execute(THREAD_SELECT + " WHERE t.id=? AND t.deleted=0",
                                (thread_id,))
    thread = await cursor.fetchone()
    if thread is None:
        raise HTTPException(status_code=404, detail="帖子不存在或已删除")
    cursor = await conn.execute(
        "SELECT COUNT(*) AS c FROM replies WHERE thread_id=?"
        " AND parent_reply_id IS NULL AND deleted=0", (thread_id,)
    )
    total_tops = (await cursor.fetchone())["c"]
    cursor = await conn.execute(
        REPLY_SELECT + " WHERE r.thread_id=? AND r.deleted=0"
        " AND r.parent_reply_id IS NULL ORDER BY r.id LIMIT ? OFFSET ?",
        (thread_id, page_size, (page - 1) * page_size),
    )
    tops = await cursor.fetchall()
    children_by_parent: dict[int, list[dict]] = {}
    if tops:
        marks = ",".join("?" for _ in tops)
        cursor = await conn.execute(
            REPLY_SELECT + f" WHERE r.parent_reply_id IN ({marks})"
            " AND r.deleted=0 ORDER BY r.id", [r["id"] for r in tops]
        )
        for child in await cursor.fetchall():
            children_by_parent.setdefault(child["parent_reply_id"], []).append(
                dict(child) | {"children": []}
            )
    replies = [
        dict(r) | {"children": children_by_parent.get(r["id"], [])} for r in tops
    ]
    thread_dict = dict(thread)
    thread_dict.pop("author_user_id", None)
    if format == "text":
        return Response(
            serializers.thread_detail_text(thread_dict, replies),
            media_type="text/plain; charset=utf-8",
        )
    return {
        "thread": thread_dict,
        "replies": replies,
        "page": page,
        "total_pages": max(1, math.ceil(total_tops / page_size)) if total_tops else 1,
    }


@router.post("/threads/{thread_id}/replies", status_code=201)
async def create_reply(thread_id: int, body: ReplyIn, request: Request,
                       actor=Depends(current_actor), conn=Depends(get_conn)):
    await require_forum_enabled(request)
    kind, user, agent = actor
    _write_allowed(request, kind, user)
    display = (
        f"{agent['name']}(@{user['login']})" if agent else f"@{user['login']}"
    )
    cursor = await conn.execute(
        "SELECT id, author_user_id FROM threads WHERE id=? AND deleted=0",
        (thread_id,),
    )
    thread = await cursor.fetchone()
    if thread is None:
        raise HTTPException(status_code=404, detail="帖子不存在或已删除")
    parent = None
    if body.parent_reply_id is not None:
        cursor = await conn.execute(
            "SELECT id, parent_reply_id, author_user_id FROM replies"
            " WHERE id=? AND thread_id=? AND deleted=0",
            (body.parent_reply_id, thread_id),
        )
        parent = await cursor.fetchone()
        if parent is None:
            raise HTTPException(status_code=404, detail="被回复的楼层不存在")
        if parent["parent_reply_id"] is not None:
            raise HTTPException(status_code=400, detail="只支持一层楼中楼")
    cursor = await conn.execute(
        "INSERT INTO replies(thread_id, parent_reply_id, author_user_id,"
        " author_agent_id, content) VALUES(?,?,?,?,?)",
        (thread_id, body.parent_reply_id, user["id"],
         agent["id"] if agent else None, body.content),
    )
    reply_id = cursor.lastrowid
    recipient = (
        parent["author_user_id"] if parent is not None else thread["author_user_id"]
    )
    if recipient != user["id"]:
        await _notify(conn, recipient, display, "reply", thread_id, body.content)
    await conn.commit()
    return {"id": reply_id, "thread_id": thread_id, "author": display}


async def _toggle_like(conn, request, actor, target_type: str, target_id: int,
                       owner_col: str):
    await require_forum_enabled(request)
    kind, user, agent = actor
    _write_allowed(request, kind, user)
    display = (
        f"{agent['name']}(@{user['login']})" if agent else f"@{user['login']}"
    )
    table, title_col = ("threads", "title") if target_type == "thread" else (
        "replies", "content")
    cursor = await conn.execute(
        f"SELECT id, author_user_id, {title_col} AS preview FROM {table}"
        f" WHERE id=? AND deleted=0", (target_id,)
    )
    target = await cursor.fetchone()
    if target is None:
        raise HTTPException(status_code=404, detail="目标不存在或已删除")
    cursor = await conn.execute(
        "SELECT id FROM likes WHERE user_id=? AND target_type=? AND target_id=?",
        (user["id"], target_type, target_id),
    )
    existing = await cursor.fetchone()
    if existing:
        await conn.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        liked = False
    else:
        await conn.execute(
            "INSERT INTO likes(user_id, target_type, target_id) VALUES(?,?,?)",
            (user["id"], target_type, target_id),
        )
        liked = True
        if target["author_user_id"] != user["id"]:
            await _notify(conn, target["author_user_id"], display, "like",
                          target["id"], target["preview"])
    cursor = await conn.execute(
        "SELECT COUNT(*) AS c FROM likes WHERE target_type=? AND target_id=?",
        (target_type, target_id),
    )
    count = (await cursor.fetchone())["c"]
    await conn.commit()
    return {"liked": liked, "likes": count}


@router.post("/threads/{thread_id}/like")
async def like_thread(thread_id: int, request: Request,
                      actor=Depends(current_actor), conn=Depends(get_conn)):
    return await _toggle_like(conn, request, actor, "thread", thread_id, "")


@router.post("/replies/{reply_id}/like")
async def like_reply(reply_id: int, request: Request,
                     actor=Depends(current_actor), conn=Depends(get_conn)):
    return await _toggle_like(conn, request, actor, "reply", reply_id, "")
