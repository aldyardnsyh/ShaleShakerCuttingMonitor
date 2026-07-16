"""Models list endpoint."""
from __future__ import annotations

import json

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["models"])

_DEFAULT_MODELS = [
    {
        "name": "mobilevit",
        "display_name": "MobileViT",
        "fg_threshold": 0.65,
        "input_h": 224,
        "input_w": 640,
    },
    {
        "name": "bisenetv2",
        "display_name": "BiSeNetV2",
        "fg_threshold": 0.50,
        "input_h": 224,
        "input_w": 640,
    },
]


@router.get("/models")
def list_models():
    meta_path = settings.MODELS_DIR / "model_meta.json"
    if meta_path.exists():
        data = json.loads(meta_path.read_text())
        raw = data.get("models", _DEFAULT_MODELS)
        models = list(raw.values()) if isinstance(raw, dict) else raw
    else:
        models = _DEFAULT_MODELS
    return {"models": models, "default_model": settings.DEFAULT_MODEL}
