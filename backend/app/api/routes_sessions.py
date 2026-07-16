"""Session endpoints: create, upload video, process, query, export CSV."""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.db import crud
from app.db.database import get_db
from app.db.schemas import MeasurementOut, SessionCreate, SessionOut
from app.workers.processor import process_session, request_cancel, session_csv_path, session_video_path

router = APIRouter(tags=["sessions"])


def _to_out(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "source_type": s.source_type,
        "model": s.model,
        "threshold": s.threshold,
        "roi_json": json.loads(s.roi_json),
        "stride": s.stride,
        "status": s.status,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "created_at": s.created_at,
        "video_fps": s.video_fps,
        "frame_width": s.frame_width,
        "frame_height": s.frame_height,
        "grid_cell_px": s.grid_cell_px,
        "grid_occ_fraction": s.grid_occ_fraction,
        "refine_edges": bool(s.refine_edges) if s.refine_edges is not None else None,
    }


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create(data: SessionCreate, db: Session = Depends(get_db)):
    s = crud.create_session(
        db,
        name=data.name,
        model=data.model,
        threshold=data.threshold,
        roi_json=data.roi_json,
        stride=data.stride,
        source_type=data.source_type,
        grid_cell_px=data.grid_cell_px,
        grid_occ_fraction=data.grid_occ_fraction,
        refine_edges=data.refine_edges,
    )
    return _to_out(s)


@router.get("/sessions", response_model=list[SessionOut])
def list_all(db: Session = Depends(get_db)):
    return [_to_out(s) for s in crud.list_sessions(db)]


@router.get("/sessions/{session_id}")
def detail(session_id: int, db: Session = Depends(get_db)):
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    out = _to_out(s)
    out["summary"] = crud.session_summary(db, session_id)
    return out


@router.post("/sessions/{session_id}/upload")
async def upload_video(session_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    dest = session_video_path(session_id)
    data = await file.read()
    dest.write_bytes(data)
    return {"session_id": session_id, "saved": str(dest), "bytes": len(data)}


@router.post("/sessions/{session_id}/process")
async def process(
    session_id: int,
    max_frames: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """Run processing synchronously (off the event loop). Use the WebSocket
    endpoint for real-time streaming; this is for batch processing / testing."""
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    try:
        summary = await run_in_threadpool(
            process_session, session_id, None, max_frames, False
        )
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    return summary


@router.post("/sessions/{session_id}/stop")
def stop(session_id: int, db: Session = Depends(get_db)):
    """Request cancellation of a running session. Partial data is discarded
    by the worker; the session is marked 'cancelled'."""
    if not crud.get_session(db, session_id):
        raise HTTPException(404, "Session not found")
    request_cancel(session_id)
    return {"session_id": session_id, "stopping": True}


@router.get("/sessions/{session_id}/measurements", response_model=list[MeasurementOut])
def measurements(session_id: int, db: Session = Depends(get_db)):
    if not crud.get_session(db, session_id):
        raise HTTPException(404, "Session not found")
    return crud.list_measurements(db, session_id)


@router.get("/sessions/{session_id}/video")
def get_video(session_id: int, db: Session = Depends(get_db)):
    """Serve the uploaded video (FileResponse supports HTTP range requests so
    the browser <video> element can seek/stream)."""
    if not crud.get_session(db, session_id):
        raise HTTPException(404, "Session not found")
    path = session_video_path(session_id)
    if not path.exists():
        raise HTTPException(404, "Video belum diupload")
    return FileResponse(str(path), media_type="video/mp4", filename=f"session_{session_id}.mp4")


@router.get("/sessions/{session_id}/tracks")
def get_tracks(session_id: int, db: Session = Depends(get_db)):
    """Compact per-detection-frame tracks for the frontend overlay.

    Returns video fps + frame size + a list of detected frames each with the
    Kalman tracks (box + velocity) so the client can extrapolate between them.
    """
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    fps = s.video_fps or 25.0
    frames = []
    for m in crud.list_measurements(db, session_id):
        try:
            blobs = json.loads(m.tracks_json) if m.tracks_json else []
        except (TypeError, ValueError):
            blobs = []
        frames.append({
            "frame_idx": m.frame_idx,
            "t": round(m.frame_idx / fps, 4) if fps else 0.0,
            "fg_area_pct": m.fg_area_pct,
            "coverage_pct": m.coverage_pct if m.coverage_pct is not None else 0.0,
            "stone_count": m.stone_count,
            "blobs": blobs,
        })
    return {
        "session_id": session_id,
        "fps": fps,
        "width": s.frame_width,
        "height": s.frame_height,
        "stride": s.stride,
        "roi": json.loads(s.roi_json),
        "frames": frames,
    }


@router.get("/sessions/{session_id}/export.csv")
def export_csv(session_id: int, db: Session = Depends(get_db)):
    if not crud.get_session(db, session_id):
        raise HTTPException(404, "Session not found")

    # Prefer the auto-saved CSV written at completion (no DB read needed).
    saved = session_csv_path(session_id)
    if saved.exists():
        return FileResponse(str(saved), media_type="text/csv", filename=f"session_{session_id}.csv")

    # Fallback: stream from DB (e.g., legacy sessions).
    rows = crud.list_measurements(db, session_id)

    def _gen():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["frame_idx", "ts", "fg_px", "roi_px", "fg_area_pct", "coverage_pct", "stone_count", "fps", "infer_ms", "model"])
        yield buf.getvalue(); buf.seek(0); buf.truncate(0)
        for r in rows:
            writer.writerow([r.frame_idx, r.ts.isoformat(), r.fg_px, r.roi_px, r.fg_area_pct, r.coverage_pct, r.stone_count, r.fps, r.infer_ms, r.model])
            yield buf.getvalue(); buf.seek(0); buf.truncate(0)

    headers = {"Content-Disposition": f"attachment; filename=session_{session_id}.csv"}
    return StreamingResponse(_gen(), media_type="text/csv", headers=headers)


@router.get("/sessions/{session_id}/export.pdf")
def export_pdf(session_id: int, db: Session = Depends(get_db)):
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    from app.core.report import build_session_pdf
    summary = crud.session_summary(db, session_id)
    rows = crud.list_measurements(db, session_id)
    pdf = build_session_pdf(_to_out(s), summary, rows)
    headers = {"Content-Disposition": f"attachment; filename=session_{session_id}.pdf"}
    return Response(content=pdf, media_type="application/pdf", headers=headers)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    sess = crud.get_session(db, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    # Guard: a session that is still processing (running — includes a paused
    # live run) must not be deleted. The user has to Stop it first. This
    # prevents accidentally removing the video/data mid-analysis.
    if sess.status == "running":
        raise HTTPException(409, "Sesi sedang berjalan, hentikan (Stop) dulu sebelum menghapus.")
    crud.delete_session(db, session_id)
    # Best-effort cleanup of artefacts on disk.
    for p in (session_video_path(session_id), session_csv_path(session_id)):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    return Response(status_code=204)
