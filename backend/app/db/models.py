"""ORM models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Preset(Base):
    __tablename__ = "presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    roi_json: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    stride: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    roi_json: Mapped[str] = mapped_column(Text, nullable=False)
    stride: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String, default="created")
    video_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grid_cell_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grid_occ_fraction: Mapped[float | None] = mapped_column(Float, nullable=True)
    refine_edges: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    frame_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    fg_px: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_px: Mapped[int] = mapped_column(Integer, nullable=False)
    fg_area_pct: Mapped[float] = mapped_column(Float, nullable=False)
    stone_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float] = mapped_column(Float, nullable=False)
    infer_ms: Mapped[float] = mapped_column(Float, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    tracks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
