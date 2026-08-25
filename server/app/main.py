import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import Settings
from .routers import admin, modules, oauth, threads, users
from .security import SlidingWindowLimiter

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def ensure_secret(settings: Settings) -> str:
    if settings.secret_key:
        return settings.secret_key
    path = Path(settings.db_path).parent / "secret.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
    else:
        key = secrets.token_hex(32)
        path.write_text(key, encoding="utf-8")
    settings.secret_key = key
    return key


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    ensure_secret(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.conn = await db.connect(settings.db_path)
        await db.init_db(app.state.conn)
        yield
        await app.state.conn.close()

    app = FastAPI(title="Gesellschaft 浮务器", lifespan=lifespan)
    app.state.settings = settings
    app.state.write_limiter = SlidingWindowLimiter(
        settings.agent_write_limit, settings.agent_write_window
    )
    app.state.publish_limiter = SlidingWindowLimiter(
        settings.publish_limit, settings.publish_window
    )

    app.include_router(oauth.router)
    app.include_router(users.router)
    app.include_router(threads.router)
    app.include_router(modules.router)
    app.include_router(admin.router)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def page_index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/login")
    async def page_login():
        return FileResponse(STATIC_DIR / "login.html")

    @app.get("/rules")
    async def page_rules():
        return FileResponse(STATIC_DIR / "rules.html")

    @app.get("/account")
    async def page_account():
        return FileResponse(STATIC_DIR / "me.html")

    @app.get("/thread/{thread_id}")
    async def page_thread(thread_id: int):
        return FileResponse(STATIC_DIR / "thread.html")

    @app.get("/market")
    async def page_market():
        return FileResponse(STATIC_DIR / "modules.html")

    @app.get("/module/{slug}")
    async def page_module(slug: str):
        return FileResponse(STATIC_DIR / "module.html")

    @app.get("/admin")
    async def page_admin():
        return FileResponse(STATIC_DIR / "admin.html")

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8787)


if __name__ == "__main__":
    main()
