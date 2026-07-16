"""Task 7 — WebSocket streaming test."""
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


def _make_video(path, n=4, w=1600, h=900):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (w, h))
    rng = np.random.default_rng(1)
    for _ in range(n):
        vw.write(rng.integers(0, 255, (h, w, 3), dtype=np.uint8))
    vw.release()


def test_ws_streams_frames_then_done():
    r = client.post("/api/sessions", json={
        "name": "ws-sess", "model": "bisenetv2", "threshold": 0.5,
        "roi_json": DEFAULT_ROI, "stride": 1,
    })
    sid = r.json()["id"]
    _make_video(session_video_path(sid), n=4)

    frames = []
    done = None
    with client.websocket_connect(f"/ws/sessions/{sid}?max_frames=3") as ws:
        while True:
            msg = ws.receive_json()
            if msg.get("done"):
                done = msg
                break
            frames.append(msg)

    assert len(frames) == 3
    for f in frames:
        assert "fg_area_pct" in f
        assert "coverage_pct" in f
        assert "stone_count" in f
        assert "fps" in f
        assert "server_time" in f
        assert "t" in f
        assert isinstance(f["blobs"], list)
    assert done is not None
    assert done["frames_processed"] == 3
