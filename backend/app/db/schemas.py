"""Pydantic v2 schemas for presets."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.config import settings


class PresetCreate(BaseModel):
    name: str
    roi_json: list[list[float]] | list
    model: str = settings.DEFAULT_MODEL
    threshold: float
    stride: int = settings.DEFAULT_STRIDE


class PresetUpdate(BaseModel):
    name: str | None = None
    roi_json: list[list[float]] | list | None = None
    model: str | None = None
    threshold: float | None = None
    stride: int | None = None


class PresetOut(BaseModel):
    id: int
    name: str
    roi_json: list[list[float]] | list
    model: str
    threshold: float
    stride: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionCreate(BaseModel):
    name: str
    model: str = settings.DEFAULT_MODEL
    threshold: float = 0.5
    roi_json: list[list[float]] | list
    stride: int = settings.DEFAULT_STRIDE
    source_type: str = "upload"
    grid_cell_px: int | None = None
    grid_occ_fraction: float | None = None
    refine_edges: bool | None = None


class SessionOut(BaseModel):
    id: int
    name: str
    source_type: str
    model: str
    threshold: float
    roi_json: list[list[float]] | list
    stride: int
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    video_fps: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    grid_cell_px: int | None = None
    grid_occ_fraction: float | None = None
    refine_edges: bool | None = None


class MeasurementOut(BaseModel):
    frame_idx: int
    ts: datetime
    fg_area_pct: float
    coverage_pct: float | None = None
    stone_count: int
    fps: float
    infer_ms: float

    model_config = ConfigDict(from_attributes=True)
