"""CRUD helpers for presets."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db.models import Preset, Session as SessionModel, Measurement
from app.db.schemas import PresetCreate, PresetUpdate


def create_preset(db: Session, data: PresetCreate) -> Preset:
    preset = Preset(
        name=data.name,
        roi_json=json.dumps(data.roi_json),
        model=data.model,
        threshold=data.threshold,
        stride=data.stride,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


def get_preset(db: Session, preset_id: int) -> Preset | None:
    return db.get(Preset, preset_id)


def list_presets(db: Session) -> list[Preset]:
    return list(db.query(Preset).order_by(Preset.id).all())


def update_preset(db: Session, preset_id: int, data: PresetUpdate) -> Preset | None:
    preset = db.get(Preset, preset_id)
    if not preset:
        return None
    updates = data.model_dump(exclude_unset=True)
    if "roi_json" in updates:
        updates["roi_json"] = json.dumps(updates["roi_json"])
    for k, v in updates.items():
        setattr(preset, k, v)
    db.commit()
    db.refresh(preset)
    return preset


def delete_preset(db: Session, preset_id: int) -> bool:
    preset = db.get(Preset, preset_id)
    if not preset:
        return False
    db.delete(preset)
    db.commit()
    return True


# --- Sessions ---------------------------------------------------------------
def create_session(
    db: Session,
    *,
    name: str,
    model: str,
    threshold: float,
    roi_json: list,
    stride: int,
    source_type: str = "upload",
    grid_cell_px: int | None = None,
    grid_occ_fraction: float | None = None,
    refine_edges: bool | None = None,
) -> SessionModel:
    from app.config import settings as _s
    if refine_edges is None:
        refine_edges = _s.REFINE_EDGES
    sess = SessionModel(
        name=name,
        source_type=source_type,
        model=model,
        threshold=threshold,
        roi_json=json.dumps(roi_json),
        stride=stride,
        status="created",
        grid_cell_px=grid_cell_px,
        grid_occ_fraction=grid_occ_fraction,
        refine_edges=1 if refine_edges else 0,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def get_session(db: Session, session_id: int) -> SessionModel | None:
    return db.get(SessionModel, session_id)


def list_sessions(db: Session) -> list[SessionModel]:
    return list(db.query(SessionModel).order_by(SessionModel.id.desc()).all())


def delete_session(db: Session, session_id: int) -> bool:
    sess = db.get(SessionModel, session_id)
    if not sess:
        return False
    db.query(Measurement).filter(Measurement.session_id == session_id).delete(synchronize_session=False)
    db.delete(sess)
    db.commit()
    return True


def update_session_status(db: Session, session_id: int, *, status: str, started_at=None, ended_at=None) -> SessionModel | None:
    sess = db.get(SessionModel, session_id)
    if not sess:
        return None
    sess.status = status
    if started_at is not None:
        sess.started_at = started_at
    if ended_at is not None:
        sess.ended_at = ended_at
    db.commit()
    db.refresh(sess)
    return sess


# --- Measurements -----------------------------------------------------------
def add_measurement(db: Session, **kwargs) -> Measurement:
    m = Measurement(**kwargs)
    db.add(m)
    db.commit()
    return m


def add_measurements_bulk(db: Session, rows: list[dict]) -> int:
    """Persist many measurement rows in a single transaction (one commit).

    Used after detection completes so the inference loop is not slowed by a
    DB commit (fsync) per frame. Returns the number of rows inserted.
    """
    if not rows:
        return 0
    db.bulk_insert_mappings(Measurement, rows)
    db.commit()
    return len(rows)


def list_measurements(db: Session, session_id: int) -> list[Measurement]:
    return list(
        db.query(Measurement)
        .filter(Measurement.session_id == session_id)
        .order_by(Measurement.frame_idx)
        .all()
    )


def delete_measurements(db: Session, session_id: int) -> int:
    """Delete all measurements for a session (used when a run is cancelled)."""
    n = (
        db.query(Measurement)
        .filter(Measurement.session_id == session_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return n


def session_summary(db: Session, session_id: int) -> dict:
    rows = list_measurements(db, session_id)
    if not rows:
        return {"frames": 0, "avg_fg_area_pct": 0.0, "avg_coverage_pct": 0.0, "max_stone_count": 0, "avg_fps": 0.0}
    n = len(rows)
    return {
        "frames": n,
        "avg_fg_area_pct": round(sum(r.fg_area_pct for r in rows) / n, 4),
        "avg_coverage_pct": round(sum((r.coverage_pct or 0.0) for r in rows) / n, 4),
        "max_stone_count": max(r.stone_count for r in rows),
        "avg_fps": round(sum(r.fps for r in rows) / n, 2),
    }
