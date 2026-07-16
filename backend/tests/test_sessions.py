"""Task 6 — session create / process / measurements / CSV export tests."""
import tempfile
import os

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.database import init_db
from app.main import app
from app.workers.processor import session_video_path

_HAS_MODELS = (settings.MODELS_DIR / "model_meta.json").exists()
pytestmark = pytest.mark.skipif(not _HAS_MODELS, reason="ONNX models not converted yet")

init_db()
client = TestClient(app)

DEFAULT_ROI = [[760, 650], [1300, 614], [1315, 795], [780, 845]]


def _make_video(path, n=5, w=1600, h=900):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(path), fourcc, 10.0, (w, h))
    rng = np.random.default_rng(0)
    for _ in range(n):
        frame = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
        vw.write(frame)
    vw.release()


def _create_session():
    r = client.post("/api/sessions", json={
        "name": "test-sess",
        "model": "bisenetv2",
        "threshold": 0.5,
        "roi_json": DEFAULT_ROI,
        "stride": 1,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_process_creates_measurements_and_csv():
    sid = _create_session()
    _make_video(session_video_path(sid), n=5)

    # process a subset
    r = client.post(f"/api/sessions/{sid}/process", params={"max_frames": 3})
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["frames_processed"] == 3
    assert summary["status"] == "done"

    # measurements persisted
    r = client.get(f"/api/sessions/{sid}/measurements")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 3
    for row in rows:
        assert 0.0 <= row["fg_area_pct"] <= 100.0
        assert row["stone_count"] >= 0
        assert "ts" in row

    # detail summary present
    r = client.get(f"/api/sessions/{sid}")
    assert r.status_code == 200
    assert r.json()["summary"]["frames"] == 3

    # CSV export
    r = client.get(f"/api/sessions/{sid}/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.text.strip().splitlines()
    assert text[0].split(",")[0] == "frame_idx"
    assert len(text) == 1 + 3  # header + 3 rows

    # CSV is auto-saved to disk on completion (no per-frame DB writes).
    from app.workers.processor import session_csv_path
    assert session_csv_path(sid).exists()


def test_upload_endpoint_saves_file():
    sid = _create_session()
    # build a tiny in-memory mp4 by writing then reading bytes
    tmp_path = session_video_path(sid)
    _make_video(tmp_path, n=2)
    payload = tmp_path.read_bytes()
    tmp_path.unlink()  # remove so upload recreates it

    r = client.post(
        f"/api/sessions/{sid}/upload",
        files={"file": ("clip.mp4", payload, "video/mp4")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["bytes"] == len(payload)
    assert session_video_path(sid).exists()


def test_stop_discards_data():
    """A cancelled run must not persist measurements and is marked cancelled."""
    from app.workers.processor import request_cancel

    sid = _create_session()
    _make_video(session_video_path(sid), n=6)

    # Pre-set cancellation; the worker stops on the first frame and discards data.
    request_cancel(sid)
    r = client.post(f"/api/sessions/{sid}/process", params={"max_frames": 5})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"

    # No measurements saved.
    r = client.get(f"/api/sessions/{sid}/measurements")
    assert r.status_code == 200 and r.json() == []

    # Session marked cancelled.
    assert client.get(f"/api/sessions/{sid}").json()["status"] == "cancelled"


def test_stop_endpoint_exists():
    sid = _create_session()
    r = client.post(f"/api/sessions/{sid}/stop")
    assert r.status_code == 200
    assert r.json()["stopping"] is True


def test_pdf_export_and_delete():
    sid = _create_session()
    _make_video(session_video_path(sid), n=5)
    client.post(f"/api/sessions/{sid}/process", params={"max_frames": 3})

    # PDF export
    r = client.get(f"/api/sessions/{sid}/export.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"

    # Delete session -> 204, then gone
    r = client.delete(f"/api/sessions/{sid}")
    assert r.status_code == 204
    assert client.get(f"/api/sessions/{sid}").status_code == 404
    assert not session_video_path(sid).exists()
    sid = _create_session()
    _make_video(session_video_path(sid), n=6)
    r = client.post(f"/api/sessions/{sid}/process", params={"max_frames": 4})
    assert r.status_code == 200, r.text

    # video metadata captured on the session
    s = client.get(f"/api/sessions/{sid}").json()
    assert s["video_fps"] and s["frame_width"] == 1600 and s["frame_height"] == 900

    # tracks endpoint shape
    r = client.get(f"/api/sessions/{sid}/tracks")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fps"] and body["width"] == 1600
    assert len(body["frames"]) == 4
    fr = body["frames"][0]
    assert "t" in fr and "blobs" in fr and isinstance(fr["blobs"], list)
    assert "coverage_pct" in fr

    # video stream served
    r = client.get(f"/api/sessions/{sid}/video")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
