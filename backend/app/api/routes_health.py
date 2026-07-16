"""Health & metadata endpoints."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe + server time (used by the dashboard clock)."""
    try:
        now = datetime.now(ZoneInfo(settings.TIMEZONE))
    except Exception:
        now = datetime.now().astimezone()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "server_time": now.isoformat(),
        "timezone": settings.TIMEZONE,
    }
