from __future__ import annotations

import logging
import os
import secrets
import threading

import markdown as _markdown
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import __version__ as APP_VERSION
from app.admin import rate_limit
from app.admin.fs_browse import InvalidPath, list_directory
from app.auth import hash_password, verify_password
from app.config import get_settings
from app.db import get_session
from app.models import Album, Artist, AdminUser, Playlist, ScanError, ScanState, Track
from app.scanner import AlreadyRunning, full_scan, is_scan_running
from pathlib import Path as _Path

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = _Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals["app_version"] = APP_VERSION

router = APIRouter()


def _is_authed(request: Request) -> bool:
    return bool(request.session.get("uid"))


def _require_login(request: Request) -> RedirectResponse | None:
    """Return a redirect-to-login response if not authenticated, else None."""
    if not _is_authed(request):
        return RedirectResponse(url="/login", status_code=302)
    return None


def _flash(request: Request, message: str, type_: str = "info") -> None:
    request.session["flash"] = message
    request.session["flash_type"] = type_


def _pop_flash(request: Request) -> tuple[str | None, str | None]:
    return request.session.pop("flash", None), request.session.pop("flash_type", None)


def _render(
    request: Request,
    template: str,
    context: dict,
    nav_active: str | None = None,
) -> Response:
    """Render a template with the pop-flash + nav_active boilerplate merged in."""
    flash, flash_type = _pop_flash(request)
    ctx = {**context, "flash": flash, "flash_type": flash_type}
    if nav_active is not None:
        ctx["nav_active"] = nav_active
    return templates.TemplateResponse(request, template, ctx)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if (redir := _require_login(request)) is not None:
        return redir

    with get_session() as session:
        counts = {
            "artists": session.query(Artist).count(),
            "albums": session.query(Album).count(),
            "tracks": session.query(Track).count(),
            "playlists": session.query(Playlist).count(),
        }
        state = session.query(ScanState).first()
        if state is None:
            state = ScanState()
            session.add(state)
            session.commit()
        session.refresh(state)
        # Also reflect the module-level lock status (thread already running vs stale DB flag).
        running_live = is_scan_running()
        # Detach for template use
        state_snapshot = {
            "running": running_live or state.running,
            "started_at": state.started_at,
            "finished_at": state.finished_at,
            "last_scan_ok": state.last_scan_ok,
            "error_count": state.error_count,
            "total_tracks": state.total_tracks,
        }
        errors = (
            session.query(ScanError)
            .order_by(ScanError.ts.desc())
            .limit(100)
            .all()
        )
        errors_snap = [{"path": e.path, "error": e.error, "ts": e.ts} for e in errors]

    return _render(
        request,
        "dashboard.html",
        {"counts": counts, "scan": state_snapshot, "errors": errors_snap},
        nav_active="dashboard",
    )


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if _is_authed(request):
        return RedirectResponse(url="/", status_code=302)
    return _render(request, "login.html", {})


@router.post("/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    ip = request.client.host if request.client else "unknown"
    if not rate_limit.check_and_record(ip):
        return Response(
            "Too many login attempts. Please wait 5 minutes.",
            status_code=429,
        )

    with get_session() as session:
        user = session.query(AdminUser).filter_by(username=username).first()
        if user is None or not verify_password(password, user.password_hash):
            _flash(request, "Wrong username or password.", "error")
            return RedirectResponse(url="/login", status_code=302)
        request.session["uid"] = user.id
    rate_limit.reset(ip)
    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.post("/admin/rescan")
async def rescan(request: Request):
    if (redir := _require_login(request)) is not None:
        return redir

    if is_scan_running():
        _flash(request, "Scan already in progress.", "info")
        return RedirectResponse(url="/", status_code=302)

    settings = get_settings()
    music_dir = settings.music_dir
    covers_dir = settings.covers_dir

    def _worker():
        try:
            with get_session() as s:
                full_scan(s, music_dir, covers_dir)
        except AlreadyRunning:
            logger.info("rescan skipped: already running")
        except Exception:
            logger.exception("rescan failed")

    threading.Thread(target=_worker, daemon=True).start()
    _flash(request, "Scan started.", "success")
    return RedirectResponse(url="/", status_code=302)


@router.post("/admin/password")
async def change_password(
    request: Request,
    current: str = Form(...),
    new: str = Form(...),
):
    if (redir := _require_login(request)) is not None:
        return redir
    if len(new) < 4:
        _flash(request, "New password too short (min 4 chars).", "error")
        return RedirectResponse(url="/", status_code=302)

    with get_session() as session:
        user = session.get(AdminUser, request.session["uid"])
        if user is None or not verify_password(current, user.password_hash):
            _flash(request, "Current password is wrong.", "error")
            return RedirectResponse(url="/", status_code=302)
        user.password_hash = hash_password(new)
        user.plain_password = new
        session.commit()

    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/library", response_class=HTMLResponse)
async def library(request: Request, path: str = ""):
    if (redir := _require_login(request)) is not None:
        return redir
    settings = get_settings()
    try:
        result = list_directory(settings.music_dir, path)
    except InvalidPath:
        return Response("Not found", status_code=404)

    files_view = [{
        "name": f.name,
        "rel_path": f.rel_path,
        "size_mb": f.size_bytes / (1024 * 1024),
        "title": None,
        "duration": 0,
    } for f in result.files]

    if files_view:
        abs_paths = [str((settings.music_dir / f["rel_path"]).resolve()) for f in files_view]
        with get_session() as session:
            tracks = (
                session.query(Track)
                .filter(Track.path.in_(abs_paths))
                .all()
            )
            by_path = {t.path: t for t in tracks}
        for fv in files_view:
            key = str((settings.music_dir / fv["rel_path"]).resolve())
            t = by_path.get(key)
            if t is not None:
                stem = _Path(fv["name"]).stem
                if t.title and t.title.strip().lower() != stem.lower():
                    fv["title"] = t.title
                fv["duration"] = t.duration_s or 0

    return _render(
        request,
        "library.html",
        {
            "folders": result.folders,
            "files": files_view,
            "breadcrumb": result.breadcrumb,
            "current_path": result.rel_path,
        },
        nav_active="library",
    )


def _changelog_candidates() -> list[_Path]:
    """Ordered list of paths to try when locating CHANGELOG.md at request time."""
    candidates: list[_Path] = []
    env_path = os.environ.get("CHANGELOG_PATH", "").strip()
    if env_path:
        candidates.append(_Path(env_path))
    candidates.append(_Path(__file__).resolve().parents[3] / "CHANGELOG.md")
    candidates.append(_Path("/app/CHANGELOG.md"))
    candidates.append(_Path.cwd() / "CHANGELOG.md")
    return candidates


def _resolve_changelog_path() -> _Path | None:
    for p in _changelog_candidates():
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


@router.get("/changelog", response_class=HTMLResponse)
async def changelog(request: Request):
    if (redir := _require_login(request)) is not None:
        return redir
    path = _resolve_changelog_path()
    if path is None:
        tried = [str(p) for p in _changelog_candidates()]
        logger.warning("changelog: CHANGELOG.md not found, tried: %s", tried)
        return Response(
            "CHANGELOG.md not found — set CHANGELOG_PATH env var or check server logs.",
            status_code=404,
        )
    text = path.read_text(encoding="utf-8")
    html = _markdown.markdown(text, extensions=["fenced_code", "tables"])
    return _render(
        request,
        "changelog.html",
        {"changelog_html": html},
        nav_active="changelog",
    )


@router.get("/admin/scan/status")
async def scan_status(request: Request):
    if not _is_authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    with get_session() as session:
        state = session.query(ScanState).first()
    running_live = is_scan_running()
    if state is None:
        return JSONResponse({
            "running": running_live,
            "started_at": None,
            "finished_at": None,
            "last_scan_ok": None,
            "total_tracks": 0,
            "error_count": 0,
        })
    return JSONResponse({
        "running": running_live or bool(state.running),
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "finished_at": state.finished_at.isoformat() if state.finished_at else None,
        "last_scan_ok": state.last_scan_ok,
        "total_tracks": state.total_tracks,
        "error_count": state.error_count,
    })
