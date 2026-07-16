"""Tests for ROI perspective warp utilities and endpoint."""
from __future__ import annotations

import io

import cv2
import numpy as np
import pytest
from PIL import Image

from app.core.roi import (
    CROP_H,
    CROP_W,
    DEFAULT_ROI_SRC,
    get_transforms,
    warp_mask_to_full,
    warp_to_roi,
)


def test_get_transforms_maps_corners():
    """M should map src corners to dst corners within 1e-3."""
    M, _ = get_transforms(DEFAULT_ROI_SRC)
    src = np.array(DEFAULT_ROI_SRC, dtype=np.float32).reshape(1, -1, 2)
    dst_expected = np.array(
        [[0, 0], [CROP_W - 1, 0], [CROP_W - 1, CROP_H - 1], [0, CROP_H - 1]],
        dtype=np.float32,
    )
    dst_actual = cv2.perspectiveTransform(src, M).reshape(-1, 2)
    np.testing.assert_allclose(dst_actual, dst_expected, atol=1e-3)


def test_get_transforms_validation():
    with pytest.raises(ValueError):
        get_transforms([[0, 0], [1, 1]])


def test_roundtrip_warp():
    """Warp to ROI then inverse-warp mask back; ROI region should be mostly set."""
    full = np.zeros((900, 1600, 3), dtype=np.uint8)
    full[:] = 128
    warped = warp_to_roi(full, DEFAULT_ROI_SRC)
    assert warped.shape == (CROP_H, CROP_W, 3)

    mask = np.ones((CROP_H, CROP_W), dtype=np.uint8) * 255
    full_mask = warp_mask_to_full(mask, DEFAULT_ROI_SRC, 1600, 900)
    assert full_mask.shape == (900, 1600)

    # Check the ROI bounding box region is mostly filled
    from app.core.roi import roi_bbox
    x0, y0, x1, y1 = roi_bbox(DEFAULT_ROI_SRC)
    roi_region = full_mask[y0:y1, x0:x1]
    assert roi_region.mean() > 100  # mostly set (255 where filled)


def test_roi_preview_endpoint():
    """POST /api/roi/preview returns 200 with base64 PNG."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes_roi import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    # Build a small PNG in memory
    img = Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = client.post("/api/roi/preview", files={"image": ("test.png", buf, "image/png")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["width"] == 640
    assert data["height"] == 224
    assert data["image_b64"].startswith("data:image/png;base64,")
