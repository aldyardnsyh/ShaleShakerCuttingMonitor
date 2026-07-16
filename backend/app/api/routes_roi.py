"""ROI preview endpoint."""
from __future__ import annotations

import base64
import io
import json

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from app.core.inference import get_manager
from app.core.metrics import fg_area
from app.core.refine import refine_mask
from app.core.roi import CROP_H, CROP_W, DEFAULT_ROI_SRC, warp_to_roi

router = APIRouter(tags=["roi"])


def _parse_roi(roi: str | None) -> list:
    if roi is None:
        return DEFAULT_ROI_SRC
    try:
        roi_src = json.loads(roi)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid roi JSON")
    if not isinstance(roi_src, list) or len(roi_src) != 4:
        raise HTTPException(status_code=400, detail="roi must be a list of 4 [x,y] points")
    return roi_src


@router.post("/roi/preview")
async def roi_preview(
    image: UploadFile = File(...),
    roi: str | None = Form(None),
):
    """Warp uploaded image to ROI and return base64 PNG."""
    roi_src = _parse_roi(roi)

    data = await image.read()
    pil_img = Image.open(io.BytesIO(data)).convert("RGB")
    arr = np.array(pil_img)

    warped = warp_to_roi(arr, roi_src)

    out_img = Image.fromarray(warped)
    buf = io.BytesIO()
    out_img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {"width": CROP_W, "height": CROP_H, "image_b64": f"data:image/png;base64,{b64}"}


@router.post("/roi/analyze")
async def roi_analyze(
    image: UploadFile = File(...),
    roi: str | None = Form(None),
    model: str | None = Form(None),
    threshold: float | None = Form(None),
    refine_edges: bool = Form(False),
):
    """Warp the reference frame to the rectified ROI, run segmentation, and
    return BOTH the rectified ROI image and the binary mask (PNG, grayscale
    0/255) plus the raw foreground area %. The frontend uses the mask to
    visualise the grid-quadrat coverage interactively (cell size / occupancy
    sliders recompute client-side, no extra round-trips), so users SEE what
    each parameter does and why coverage depends on stone size."""
    roi_src = _parse_roi(roi)

    mgr = get_manager()
    model_name = model or mgr.default_model
    try:
        mgr.get_info(model_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    data = await image.read()
    try:
        rgb = np.array(Image.open(io.BytesIO(data)).convert("RGB"))
    except Exception:
        raise HTTPException(status_code=400, detail="Gambar tidak valid")

    warped = warp_to_roi(rgb, roi_src)  # (CROP_H, CROP_W, 3)
    try:
        result = mgr.predict(model_name, warped, threshold=threshold)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    mask = result.mask
    if refine_edges:
        mask = refine_mask(result.mask, warped, use_canny=True)

    _, _, fg_pct = fg_area(mask)

    # Encode rectified ROI image.
    img_buf = io.BytesIO()
    Image.fromarray(warped).save(img_buf, format="PNG")
    img_b64 = base64.b64encode(img_buf.getvalue()).decode()

    # Encode binary mask as grayscale PNG (0/255).
    mask_u8 = (np.asarray(mask) > 0).astype(np.uint8) * 255
    mask_buf = io.BytesIO()
    Image.fromarray(mask_u8, mode="L").save(mask_buf, format="PNG")
    mask_b64 = base64.b64encode(mask_buf.getvalue()).decode()

    return {
        "width": CROP_W,
        "height": CROP_H,
        "model": model_name,
        "threshold": float(result.threshold),
        "fg_area_pct": fg_pct,
        "image_b64": f"data:image/png;base64,{img_b64}",
        "mask_b64": f"data:image/png;base64,{mask_b64}",
    }
