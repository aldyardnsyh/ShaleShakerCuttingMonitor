"""FastAPI application entrypoint.

Registers API routers under /api and (when present) serves the built
Next.js static export from STATIC_DIR. Static serving is optional so the
backend runs standalone during development.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import (
    routes_health,
    routes_models,
    routes_predict,
    routes_presets,
    routes_roi,
    routes_sessions,
    routes_source_videos,
    ws_stream,
)
from app.db.database import init_db, SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


def _run_cleanup():
    """Delete video files for old sessions (best-effort, safe idempotent)."""
    from app.db.models import Session as SessionModel
    from app.db.crud import list_sessions

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.CLEANUP_RETENTION_DAYS)
    db = SessionLocal()
    try:
        sessions = list_sessions(db)
        removed = 0
        freed_bytes = 0

        for s in sessions:
            if s.status == "running":
                continue
            ended = s.ended_at or s.created_at
            if ended is None:
                continue
            if ended.tzinfo is None:
                ended = ended.replace(tzinfo=timezone.utc)
            if ended >= cutoff:
                continue
            vid = settings.UPLOAD_DIR / f"session_{s.id}.mp4"
            if vid.exists():
                try:
                    freed_bytes += vid.stat().st_size
                    vid.unlink()
                    removed += 1
                except Exception:
                    pass

        # Also purge orphaned video files (session row no longer exists).
        session_ids = {s.id for s in sessions}
        if settings.UPLOAD_DIR.exists():
            for f in settings.UPLOAD_DIR.iterdir():
                stem = f.stem
                if stem.startswith("session_") and f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
                    try:
                        sid = int(stem.split("_", 1)[1])
                    except (IndexError, ValueError):
                        continue
                    if sid not in session_ids:
                        try:
                            freed_bytes += f.stat().st_size
                            f.unlink()
                            removed += 1
                        except Exception:
                            pass

        if removed > 0:
            logger.info(
                "Cleanup: removed %d old video file(s) (freed %.1f MB)",
                removed, freed_bytes / (1024 * 1024),
            )
    except Exception:
        logger.exception("Cleanup task error")
    finally:
        db.close()


async def _cleanup_loop():
    await asyncio.sleep(120)  # wait for app to warm up
    while True:
        try:
            await asyncio.to_thread(_run_cleanup)
        except Exception:
            logger.exception("Cleanup loop failed")
        await asyncio.sleep(3600)  # check every hour


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialised at %s", settings.DATABASE_URL)
    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- API routers (all under /api) ---------------------------------------
    app.include_router(routes_health.router, prefix="/api")
    app.include_router(routes_models.router, prefix="/api")
    app.include_router(routes_presets.router, prefix="/api")
    app.include_router(routes_roi.router, prefix="/api")
    app.include_router(routes_predict.router, prefix="/api")
    app.include_router(routes_sessions.router, prefix="/api")
    app.include_router(routes_source_videos.router, prefix="/api")
    app.include_router(ws_stream.router)  # WebSocket at /ws/...

    # --- Static frontend (optional) -----------------------------------------
    _mount_static(app)

    return app


def _mount_static(app: FastAPI) -> None:
    """Serve the Next.js static export if it has been built into STATIC_DIR."""
    static_dir = settings.STATIC_DIR
    index = static_dir / "index.html"
    if not index.exists():
        logger.info("Static dir %s has no index.html; skipping static mount.", static_dir)
        return

    from fastapi.staticfiles import StaticFiles

    # html=True serves index.html for directory requests (SPA-style fallback).
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    logger.info("Mounted static frontend from %s", static_dir)


app = create_app()
