from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.admin.routes import router as admin_router
from app.admin.session_secret import load_or_create_secret
from app.auth import bootstrap_admin_user
from app.config import get_settings
from app import db as _db
from app.db import get_session, init_db
from app.logging_setup import setup_logging
from app.scanner import full_scan
from app.subsonic.endpoints import router as subsonic_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(settings.logs_dir)
    init_db(settings.db_path)
    with get_session() as session:
        bootstrap_admin_user(session, settings.admin_user, settings.admin_password)
    # Startup full scan (Goal 6: startup + manual only).
    if settings.music_dir.exists():
        try:
            with get_session() as session:
                full_scan(session, settings.music_dir, settings.covers_dir)
        except Exception:
            import logging as _lg
            _lg.getLogger(__name__).exception("startup scan failed")
    yield
    if _db._engine is not None:
        _db._engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    secret = load_or_create_secret(settings.secret_key_path)
    app = FastAPI(title="BitVelox", lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=secret, session_cookie="mp3s")
    static_dir = Path(__file__).parent / "admin" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/admin", StaticFiles(directory=str(static_dir)), name="admin-static")
    app.include_router(subsonic_router)
    app.include_router(admin_router)
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.http_port,
        log_config=None,
    )


if __name__ == "__main__":
    run()
