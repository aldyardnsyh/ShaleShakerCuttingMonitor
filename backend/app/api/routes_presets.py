"""Presets CRUD endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.crud import create_preset, delete_preset, get_preset, list_presets, update_preset
from app.db.database import get_db
from app.db.schemas import PresetCreate, PresetOut, PresetUpdate

router = APIRouter(tags=["presets"])


def _to_out(preset) -> dict:
    """Convert ORM preset to dict with parsed roi_json."""
    return {
        "id": preset.id,
        "name": preset.name,
        "roi_json": json.loads(preset.roi_json),
        "model": preset.model,
        "threshold": preset.threshold,
        "stride": preset.stride,
        "created_at": preset.created_at,
    }


@router.post("/presets", response_model=PresetOut, status_code=201)
def create(data: PresetCreate, db: Session = Depends(get_db)):
    preset = create_preset(db, data)
    return _to_out(preset)


@router.get("/presets", response_model=list[PresetOut])
def list_all(db: Session = Depends(get_db)):
    return [_to_out(p) for p in list_presets(db)]


@router.get("/presets/{preset_id}", response_model=PresetOut)
def get_one(preset_id: int, db: Session = Depends(get_db)):
    preset = get_preset(db, preset_id)
    if not preset:
        raise HTTPException(404, "Preset not found")
    return _to_out(preset)


@router.put("/presets/{preset_id}", response_model=PresetOut)
def update(preset_id: int, data: PresetUpdate, db: Session = Depends(get_db)):
    preset = update_preset(db, preset_id, data)
    if not preset:
        raise HTTPException(404, "Preset not found")
    return _to_out(preset)


@router.delete("/presets/{preset_id}", status_code=204)
def delete(preset_id: int, db: Session = Depends(get_db)):
    if not delete_preset(db, preset_id):
        raise HTTPException(404, "Preset not found")
