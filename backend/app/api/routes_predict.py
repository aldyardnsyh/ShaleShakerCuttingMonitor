"""Single-image prediction endpoint (used to verify inference works end-to-end)."""
from __future__ import annotations

import io

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from app.core.inference import get_manager
from app.core.metrics import compute_metrics

router = APIRouter(tags=["predict"])


@router.post("/predict-image")
async def predict_image(
    image: UploadFile = File(...),
    model: str | None = Form(None),
    threshold: float | None = Form(None),
):
    """Run inference on a single uploaded image and return cutting metrics.

    The image is resized to the model input (224x640). For the full ROI
    pipeline the frame is warped first (see the video worker); this endpoint
    is a direct inference smoke-test.
    """
    mgr = get_manager()
    model_name = model or mgr.default_model
    try:
        info = mgr.get_info(model_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    data = await image.read()
    try:
        rgb = np.array(Image.open(io.BytesIO(data)).convert("RGB"))
    except Exception:
        raise HTTPException(status_code=400, detail="Gambar tidak valid")

    try:
        result = mgr.predict(model_name, rgb, threshold=threshold)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    metrics = compute_metrics(result.mask)
    return {
        "model": model_name,
        "display_name": info.display_name,
        "threshold": result.threshold,
        "input_h": result.input_h,
        "input_w": result.input_w,
        "infer_ms": round(result.infer_ms, 2),
        **metrics.as_dict(),
    }
