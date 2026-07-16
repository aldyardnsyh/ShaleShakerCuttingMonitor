"""Source (demo) videos endpoint. Pre-loaded videos for quick evaluation
without requiring the user to upload their own file each time."""
from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

logger = logging.getLogger("app.source-videos")
router = APIRouter(tags=["source-videos"])

SOURCE_DIR = settings.SOURCE_VIDEOS_DIR
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def _ensure_dir() -> Path:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    return SOURCE_DIR


@router.get("/source-videos")
def list_source_videos():
    _ensure_dir()
    entries = []
    for f in sorted(SOURCE_DIR.iterdir(), key=lambda p: p.name.lower()):
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
            size_bytes = f.stat().st_size
            entries.append({
                "name": f.name,
                "path": str(f.relative_to(SOURCE_DIR)),
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
            })
    return {"videos": entries, "count": len(entries)}


@router.get("/source-videos/{name}/download")
def download_source_video(name: str):
    safe_name = os.path.basename(name)
    path = SOURCE_DIR / safe_name
    if not path.exists() or not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
        raise HTTPException(404, f"Source video '{safe_name}' not found")
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0
    mime, _ = mimetypes.guess_type(str(path))
    return FileResponse(
        str(path),
        media_type=mime or "video/mp4",
        filename=safe_name,
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)} if file_size else {},
    )
