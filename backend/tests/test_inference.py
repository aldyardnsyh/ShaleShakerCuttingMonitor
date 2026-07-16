"""Task 3 — inference core + /predict-image endpoint tests.

These require the exported ONNX models + model_meta.json. If they're absent
(e.g. CI without the conversion step) the tests are skipped rather than failing.
"""
import io

import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.core.inference import get_manager

_HAS_MODELS = (settings.MODELS_DIR / "model_meta.json").exists()
pytestmark = pytest.mark.skipif(not _HAS_MODELS, reason="ONNX models not converted yet")


def _png_bytes(w=320, h=120):
    arr = (np.random.default_rng(1).integers(0, 255, (h, w, 3))).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_manager_loads_models():
    mgr = get_manager()
    assert "mobilevit" in mgr.model_names
    assert "bisenetv2" in mgr.model_names


def test_predict_shapes_and_range():
    mgr = get_manager()
    rgb = np.random.default_rng(0).integers(0, 255, (120, 320, 3)).astype(np.uint8)
    res = mgr.predict("mobilevit", rgb)
    assert res.mask.shape == (res.input_h, res.input_w) == (224, 640)
    assert res.mask.dtype == np.uint8
    assert set(np.unique(res.mask)).issubset({0, 1})
    assert res.infer_ms > 0


def test_predict_image_endpoint():
    # Import here so the skip applies before app import touches models.
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/predict-image",
        files={"image": ("frame.png", _png_bytes(), "image/png")},
        data={"model": "bisenetv2"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model"] == "bisenetv2"
    assert 0.0 <= body["fg_area_pct"] <= 100.0
    assert body["stone_count"] >= 0
    assert body["infer_ms"] > 0
    assert body["input_h"] == 224 and body["input_w"] == 640
