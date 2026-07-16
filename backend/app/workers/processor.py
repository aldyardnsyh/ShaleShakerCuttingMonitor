"""Session processing pipeline (mask-polygon streaming).

decode frame (stride) -> warp ROI -> ONNX inference -> % area + grid coverage
-> inverse-warp mask to full frame -> simplified contour polygons
-> persist Measurement (polygons JSON) -> optional emit (WebSocket).

The frontend plays the original video natively (smooth) and overlays the
streamed mask polygons (no IDs/labels) synced by frame time `t`.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import cv2

from app.config import settings
from app.core import video as videolib
from app.core.inference import get_manager
from app.core.metrics import compute_metrics, mask_to_blobs
from app.core.refine import refine_mask
from app.core.roi import warp_mask_to_full, warp_to_roi
from app.core.tracking import MultiObjectTracker
from app.db import crud
from app.db.database import SessionLocal
from app.db.models import Session as SessionModel

logger = logging.getLogger("app.processor")

EmitFn = Callable[[dict], None]

# --- Cooperative cancellation -------------------------------------------------
# A run can be stopped from the /stop endpoint or when the WebSocket client
# disconnects. process_session() checks the flag each frame and, on cancel,
# DISCARDS the partial data for that session.
_cancel_events: dict[int, threading.Event] = {}
_cancel_lock = threading.Lock()
# Pause control: when an event is SET, the worker blocks (detection paused) until
# it is cleared (resume) or the run is cancelled. Driven by the WS client when
# the user pauses/plays the video, so paused video == paused detection (no CPU).
_pause_events: dict[int, threading.Event] = {}


def _get_cancel_event(session_id: int) -> threading.Event:
    with _cancel_lock:
        ev = _cancel_events.get(session_id)
        if ev is None:
            ev = threading.Event()
            _cancel_events[session_id] = ev
        return ev


def _get_pause_event(session_id: int) -> threading.Event:
    with _cancel_lock:
        ev = _pause_events.get(session_id)
        if ev is None:
            ev = threading.Event()
            _pause_events[session_id] = ev
        return ev


def request_pause(session_id: int) -> None:
    _get_pause_event(session_id).set()


def request_resume(session_id: int) -> None:
    _get_pause_event(session_id).clear()


def request_cancel(session_id: int) -> None:
    _get_cancel_event(session_id).set()
    # Make sure a paused worker can observe the cancel and exit promptly.
    _get_pause_event(session_id).clear()


def _clear_cancel(session_id: int) -> None:
    with _cancel_lock:
        _cancel_events.pop(session_id, None)
        _pause_events.pop(session_id, None)


def session_video_path(session_id: int) -> Path:
    return settings.UPLOAD_DIR / f"session_{session_id}.mp4"


def session_csv_path(session_id: int) -> Path:
    return settings.EXPORTS_DIR / f"session_{session_id}.csv"


CSV_COLUMNS = ["frame_idx", "ts", "fg_px", "roi_px", "fg_area_pct",
               "coverage_pct", "stone_count", "fps", "infer_ms", "model"]


def write_session_csv(session_id: int, rows: list[dict]) -> Path:
    """Auto-save the buffered measurements to a CSV file (once, at the end)."""
    import csv as _csv

    path = session_csv_path(session_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh)
        w.writerow(CSV_COLUMNS)
        for r in rows:
            ts = r.get("ts")
            w.writerow([
                r.get("frame_idx"), ts.isoformat() if hasattr(ts, "isoformat") else ts,
                r.get("fg_px"), r.get("roi_px"), r.get("fg_area_pct"),
                r.get("coverage_pct"), r.get("stone_count"), r.get("fps"),
                r.get("infer_ms"), r.get("model"),
            ])
    return path


def _server_time_iso() -> str:
    try:
        return datetime.now(ZoneInfo(settings.TIMEZONE)).isoformat()
    except Exception:
        return datetime.now().astimezone().isoformat()


def process_session(
    session_id: int,
    emit: Optional[EmitFn] = None,
    max_frames: Optional[int] = None,
    include_overlay: bool = False,
) -> dict:
    """Run the full pipeline for a session. Returns a summary dict.

    Persists one Measurement row per processed frame (with tracks_json). If
    `emit` is given, a per-frame payload is pushed to it in real time. The
    server-rendered JPEG overlay is OFF by default now (the frontend renders
    the overlay on the native video using the stored tracks).
    """
    db = SessionLocal()
    try:
        session: SessionModel | None = db.get(SessionModel, session_id)
        if session is None:
            raise ValueError(f"Session {session_id} tidak ditemukan")

        video_path = session_video_path(session_id)
        if not video_path.exists():
            raise FileNotFoundError(f"Video untuk session {session_id} belum diupload")

        roi_src = json.loads(session.roi_json)
        model_name = session.model
        threshold = session.threshold
        stride = session.stride or settings.DEFAULT_STRIDE

        mgr = get_manager()
        info = mgr.get_info(model_name)

        # Capture + persist video metadata (needed by the frontend overlay).
        vinfo = videolib.get_video_info(str(video_path))
        session.video_fps = float(vinfo.fps)
        session.frame_width = int(vinfo.width)
        session.frame_height = int(vinfo.height)
        session.status = "running"
        session.started_at = datetime.utcnow()
        db.commit()

        video_fps = float(vinfo.fps) or 25.0
        cancel_ev = _get_cancel_event(session_id)
        pause_ev = _get_pause_event(session_id)
        use_refine = bool(session.refine_edges) if session.refine_edges is not None else settings.REFINE_EDGES
        tracker = MultiObjectTracker(
            iou_threshold=settings.TRACK_IOU,
            max_age=settings.TRACK_MAX_AGE,
            min_hits=settings.TRACK_MIN_HITS,
            dist_gate=settings.TRACK_DIST_GATE,
        )
        # velocity scale: Kalman step = `stride` source frames -> px/sec.
        vel_scale = (video_fps / stride) if stride else video_fps

        # Polygon mask of the ROI in FULL-FRAME space. Used to clip the
        # inverse-warped mask so detection NEVER leaks outside the ROI quad.
        import numpy as _np
        roi_clip = _np.zeros((int(vinfo.height), int(vinfo.width)), dtype=_np.uint8)
        cv2.fillPoly(roi_clip, [_np.array(roi_src, dtype=_np.int32)], 1)

        recent = deque(maxlen=15)  # smoothed processing FPS
        buffer: list[dict] = []    # measurements kept in memory until completion
        processed = 0
        sum_pct = 0.0
        max_stones = 0
        cancelled = False

        for frame_idx, frame_bgr in videolib.iter_frames(str(video_path), stride=stride, max_frames=max_frames):
            if cancel_ev.is_set():
                cancelled = True
                break
            # Pause gate: block here (no inference, no CPU) while the user has
            # the video paused. Wake on resume or cancel.
            while pause_ev.is_set() and not cancel_ev.is_set():
                time.sleep(0.05)
            if cancel_ev.is_set():
                cancelled = True
                break
            t0 = time.perf_counter()
            H, W = frame_bgr.shape[:2]

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            roi_rgb = warp_to_roi(rgb, roi_src, info.input_w, info.input_h)
            result = mgr.predict(model_name, roi_rgb, threshold=threshold)

            # Optional edge refinement (morphology + Canny) in ROI space.
            roi_mask = refine_mask(result.mask, roi_rgb, use_canny=True) if use_refine else result.mask

            # % area + grid-quadrat coverage in ROI space (per-session grid params).
            metrics = compute_metrics(
                roi_mask,
                roi_px=roi_mask.size,
                cell_px=session.grid_cell_px,
                occ_fraction=session.grid_occ_fraction,
            )

            # Full-frame mask -> blobs (polygon + bbox) -> Kalman velocity per blob.
            full_mask = warp_mask_to_full(roi_mask, roi_src, W, H)
            # Hard-clip to the ROI polygon so nothing is ever detected outside it.
            full_mask = full_mask * roi_clip
            blob_list = mask_to_blobs(full_mask, min_area=settings.TRACK_MIN_AREA)
            boxes = [b[1] for b in blob_list]
            det_vels = tracker.update(boxes)  # px/step, aligned to boxes; no IDs
            blobs = []
            for (poly, _bbox), (vx, vy) in zip(blob_list, det_vels):
                blobs.append({
                    "poly": poly,
                    "vx": round(vx * vel_scale, 1),   # px/sec
                    "vy": round(vy * vel_scale, 1),
                })
            stone_count = len(blobs)

            dt = time.perf_counter() - t0
            recent.append(dt)
            fps = (len(recent) / sum(recent)) if sum(recent) > 0 else 0.0
            t_sec = round(frame_idx / video_fps, 4)

            # Buffer the row in memory (no per-frame DB commit) — the inference
            # loop stays the priority; persistence happens once at the end.
            buffer.append({
                "session_id": session_id,
                "ts": datetime.utcnow(),
                "frame_idx": frame_idx,
                "fg_px": metrics.fg_px,
                "roi_px": metrics.roi_px,
                "fg_area_pct": metrics.fg_area_pct,
                "stone_count": stone_count,
                "fps": round(fps, 2),
                "infer_ms": round(result.infer_ms, 2),
                "model": model_name,
                "tracks_json": json.dumps(blobs),
                "coverage_pct": metrics.coverage_pct,
            })

            processed += 1
            sum_pct += metrics.coverage_pct
            max_stones = max(max_stones, stone_count)

            if emit is not None:
                emit({
                    "frame_idx": frame_idx,
                    "t": t_sec,
                    "server_time": _server_time_iso(),
                    "fg_area_pct": metrics.fg_area_pct,
                    "coverage_pct": metrics.coverage_pct,
                    "grid_cols": metrics.grid_cols,
                    "grid_rows": metrics.grid_rows,
                    "stone_count": stone_count,
                    "fps": round(fps, 2),
                    "infer_ms": round(result.infer_ms, 2),
                    "blobs": blobs,
                })

        if cancelled:
            # Discard the in-memory buffer — a stopped run is not saved.
            crud.update_session_status(db, session_id, status="cancelled", ended_at=datetime.utcnow())
            summary = {"session_id": session_id, "frames_processed": 0,
                       "avg_coverage_pct": 0.0, "max_stone_count": 0, "status": "cancelled"}
            logger.info("Session %s cancelled — in-memory buffer discarded (nothing saved).", session_id)
            return summary

        # ---- Persist once, at the end: bulk DB insert + auto CSV ----
        crud.delete_measurements(db, session_id)          # idempotent (re-runs)
        crud.add_measurements_bulk(db, buffer)
        try:
            write_session_csv(session_id, buffer)
        except Exception as e:                            # CSV is best-effort
            logger.warning("Gagal menulis CSV sesi %s: %s", session_id, e)

        crud.update_session_status(db, session_id, status="done", ended_at=datetime.utcnow())

        summary = {
            "session_id": session_id,
            "frames_processed": processed,
            "avg_coverage_pct": round(sum_pct / processed, 4) if processed else 0.0,
            "max_stone_count": max_stones,
            "status": "done",
        }
        logger.info("Session %s processed: %s", session_id, summary)
        return summary
    except Exception as e:
        try:
            crud.update_session_status(db, session_id, status="error")
        except Exception:
            pass
        logger.exception("Session %s gagal diproses: %s", session_id, e)
        raise
    finally:
        _clear_cancel(session_id)
        db.close()
