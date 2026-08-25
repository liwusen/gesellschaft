from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from .. import security, serializers
from ..deps import (current_account, get_conn, require_registry_enabled)

router = APIRouter()

MAX_SIZE = 131072


def _valid_slug(slug: str) -> bool:
    import re

    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug))


def _version_key(version: str) -> tuple:
    return tuple(int(x) for x in version.split("."))


def bump_patch(version: str) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


@router.post("/modules", status_code=201)
async def publish_module(request: Request,
                         slug: str = Form(...),
                         description: str = Form(""),
                         usage_text: str = Form(""),
                         version: str = Form(""),
                         no_announce: bool = Form(False),
                         file=File(...),
                         user=Depends(current_account),
                         conn=Depends(get_conn)):
    await require_registry_enabled(request)
    if not request.app.state.publish_limiter.allow(f"user:{user['id']}"):
        raise HTTPException(status_code=429, detail="发布过于频繁，每天最多10次")
    if not _valid_slug(slug):
        raise HTTPException(status_code=400, detail="slug 格式不合法")
    source = await file.read()
    if len(source) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="模块超过 128KB 上限")
    try:
        source.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="模块必须是 UTF-8 文本")
    sha = security.sha256_hex(source)

    cursor = await conn.execute("SELECT * FROM modules WHERE slug=?", (slug,))
    module = await cursor.fetchone()
    if module is None:
        ver = version or "1.0.0"
        if version and not ver.count(".") == 2:
            raise HTTPException(status_code=400, detail="版本号必须是 semver")
        cursor = await conn.execute(
            "INSERT INTO modules(slug, owner_user_id, description, usage_text,"
            " latest_version) VALUES(?,?,?,?,?)",
            (slug, user["id"], description, usage_text, ver),
        )
        module_id = cursor.lastrowid
    else:
        if module["owner_user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="只能发布自己名下的模块")
        if module["taken_down"]:
            raise HTTPException(status_code=403, detail="模块已被下架")
        if version:
            if version.count(".") != 2 or any(
                not p.isdigit() for p in version.split(".")
            ):
                raise HTTPException(status_code=400, detail="版本号必须是 semver")
            if _version_key(version) <= _version_key(module["latest_version"]):
                raise HTTPException(status_code=409, detail="版本必须大于当前最新版本")
            ver = version
        else:
            ver = bump_patch(module["latest_version"])
        module_id = module["id"]
        await conn.execute(
            "UPDATE modules SET description=?, usage_text=?, latest_version=?"
            " WHERE id=?", (description, usage_text, ver, module_id),
        )

    cursor = await conn.execute(
        "SELECT version FROM module_versions WHERE module_id=? AND version=?",
        (module_id, ver),
    )
    if await cursor.fetchone():
        await conn.rollback()
        raise HTTPException(status_code=409, detail=f"版本 {ver} 已存在且不可变")

    await conn.execute(
        "INSERT INTO module_versions(module_id, version, sha256, size, source)"
        " VALUES(?,?,?,?,?)", (module_id, ver, sha, len(source), source.decode("utf-8")),
    )

    announce_thread_id = None
    if not no_announce:
        cursor = await conn.execute(
            "SELECT id FROM categories WHERE slug='module-release'"
        )
        cat = await cursor.fetchone()
        if cat is not None:
            content = (
                f"{description}\n\n## 用法\n{usage_text}\n\n安装:\n"
                f"npx gesellschaft agile add {slug}"
            )
            cursor = await conn.execute(
                "INSERT INTO threads(category_id, author_user_id, title, content)"
                " VALUES(?,?,?,?)",
                (cat["id"], user["id"], f"[模块] {slug} v{ver}", content),
            )
            announce_thread_id = cursor.lastrowid
            await conn.execute(
                "UPDATE modules SET announced_thread_id=? WHERE id=?",
                (announce_thread_id, module_id),
            )
    await conn.commit()
    return {"slug": slug, "version": ver, "sha256": sha,
            "announce_thread_id": announce_thread_id}


@router.get("/modules")
async def list_modules(request: Request, q: str = "", mine: bool = False,
                       page: int = 1, page_size: int = 20, format: str = "json",
                       conn=Depends(get_conn)):
    await require_registry_enabled(request)
    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    where = "m.taken_down=0"
    args: list = []
    if mine:
        from ..deps import resolve_account_optional

        user = await resolve_account_optional(request)
        if user is None:
            raise HTTPException(status_code=401, detail="需要账号 Token 才能查询 mine")
        where += " AND m.owner_user_id=?"
        args.append(user["id"])
    if q:
        where += " AND (m.slug LIKE ? OR m.description LIKE ? OR m.usage_text LIKE ?)"
        like = f"%{q}%"
        args.extend([like, like, like])
    cursor = await conn.execute(
        f"SELECT COUNT(*) AS c FROM modules m WHERE {where}", args
    )
    total = (await cursor.fetchone())["c"]
    args.extend([page_size, (page - 1) * page_size])
    cursor = await conn.execute(
        "SELECT m.slug, m.description, m.usage_text, m.latest_version, m.license,"
        " m.download_count, u.login AS owner_login, m.created_at"
        f" FROM modules m JOIN users u ON u.id=m.owner_user_id WHERE {where}"
        " ORDER BY m.id DESC LIMIT ? OFFSET ?", args
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    if format == "text":
        return Response(serializers.modules_text(rows),
                        media_type="text/plain; charset=utf-8")
    return {"modules": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/modules/{slug}")
async def module_meta(slug: str, request: Request, conn=Depends(get_conn)):
    await require_registry_enabled(request)
    cursor = await conn.execute(
        "SELECT m.*, u.login AS owner_login FROM modules m"
        " JOIN users u ON u.id=m.owner_user_id WHERE m.slug=?", (slug,)
    )
    module = await cursor.fetchone()
    if module is None or module["taken_down"]:
        raise HTTPException(status_code=404, detail="模块不存在或已下架")
    cursor = await conn.execute(
        "SELECT version, sha256, size, taken_down, created_at FROM module_versions"
        " WHERE module_id=?", (module["id"],)
    )
    versions = [dict(v) for v in await cursor.fetchall()]
    meta = dict(module)
    meta.pop("owner_user_id", None)
    return {"module": meta, "versions": versions}


@router.get("/modules/{slug}/source")
async def module_source(slug: str, request: Request, version: str = "latest",
                        conn=Depends(get_conn)):
    await require_registry_enabled(request)
    cursor = await conn.execute("SELECT * FROM modules WHERE slug=?", (slug,))
    module = await cursor.fetchone()
    if module is None:
        raise HTTPException(status_code=404, detail="模块不存在")
    if version == "latest":
        version = module["latest_version"]
    cursor = await conn.execute(
        "SELECT * FROM module_versions WHERE module_id=? AND version=?",
        (module["id"], version),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    if row["taken_down"] or module["taken_down"]:
        raise HTTPException(status_code=410, detail="该版本已下架")
    await conn.execute(
        "UPDATE modules SET download_count=download_count+1 WHERE id=?",
        (module["id"],),
    )
    await conn.commit()
    return PlainTextResponse(
        row["source"],
        media_type="text/x-python; charset=utf-8",
        headers={"X-Module-Version": row["version"], "X-Module-Sha256": row["sha256"]},
    )
