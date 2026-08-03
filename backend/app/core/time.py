"""Server timezone helpers for persisted and API timestamps."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings


def server_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.TIMEZONE))
    except Exception:
        return datetime.now().astimezone()


def server_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(settings.TIMEZONE))
    return value.isoformat()
