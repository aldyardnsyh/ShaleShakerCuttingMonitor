"""ONNX Runtime inference core.

Loads model metadata (model_meta.json) and lazily creates one ONNX Runtime
session per model with CPU-friendly threading (configurable via settings).
Designed to be light enough for a 2 vCPU / 2 GB box — no torch involved.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort

from app.config import settings

logger = logging.getLogger("app.inference")

# Fallback preprocessing constants (notebook cell 12) if meta lacks them.
_DEFAULT_MEAN = (0.485, 0.456, 0.406)
_DEFAULT_STD = (0.229, 0.224, 0.225)


@dataclass
class ModelInfo:
    name: str
    display_name: str
    onnx_file: str
    num_classes: int
    input_h: int
    input_w: int
    fg_threshold: float
    roi_src: list


@dataclass
class PredictResult:
    mask: np.ndarray          # (H, W) uint8 — 1 = foreground (stone)
    fg_prob: np.ndarray       # (H, W) float32 — foreground probability
    infer_ms: float
    input_h: int
    input_w: int
    threshold: float


def _softmax(logits: np.ndarray, axis: int = 1) -> np.ndarray:
    z = logits - logits.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


class InferenceManager:
    """Holds ONNX sessions + metadata, keyed by model name."""

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = Path(models_dir or settings.MODELS_DIR)
        self.mean = np.array(_DEFAULT_MEAN, dtype=np.float32)
        self.std = np.array(_DEFAULT_STD, dtype=np.float32)
        self.default_model = settings.DEFAULT_MODEL
        self._infos: dict[str, ModelInfo] = {}
        self._sessions: dict[str, ort.InferenceSession] = {}
        self._load_meta()

    # --- metadata ----------------------------------------------------------
    def _load_meta(self) -> None:
        meta_path = self.models_dir / "model_meta.json"
        if not meta_path.exists():
            logger.warning("model_meta.json not found at %s — inference disabled until present.", meta_path)
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.mean = np.array(meta.get("mean", _DEFAULT_MEAN), dtype=np.float32)
        self.std = np.array(meta.get("std", _DEFAULT_STD), dtype=np.float32)
        self.default_model = meta.get("default_model", settings.DEFAULT_MODEL)
        for name, m in meta.get("models", {}).items():
            self._infos[name] = ModelInfo(
                name=m["name"],
                display_name=m.get("display_name", name),
                onnx_file=m["onnx_file"],
                num_classes=int(m.get("num_classes", 2)),
                input_h=int(m.get("input_h", 224)),
                input_w=int(m.get("input_w", 640)),
                fg_threshold=float(m.get("fg_threshold", 0.5)),
                roi_src=m.get("roi_src", []),
            )
        logger.info("Loaded model meta: %s", list(self._infos))

    @property
    def model_names(self) -> list[str]:
        return list(self._infos)

    def get_info(self, name: str) -> ModelInfo:
        if name not in self._infos:
            raise KeyError(f"Model tidak dikenal atau belum dikonversi: {name}")
        return self._infos[name]

    # --- session -----------------------------------------------------------
    def _get_session(self, name: str) -> ort.InferenceSession:
        if name in self._sessions:
            return self._sessions[name]
        info = self.get_info(name)
        onnx_path = self.models_dir / info.onnx_file
        if not onnx_path.exists():
            raise FileNotFoundError(f"ONNX file tidak ditemukan: {onnx_path}")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = settings.ORT_INTRA_OP_THREADS
        opts.inter_op_num_threads = settings.ORT_INTER_OP_THREADS
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self._sessions[name] = sess
        logger.info("ONNX session ready: %s (%s)", name, onnx_path.name)
        self._warmup(name)
        return sess

    def _warmup(self, name: str) -> None:
        info = self.get_info(name)
        dummy = np.zeros((1, 3, info.input_h, info.input_w), dtype=np.float32)
        try:
            self._sessions[name].run(None, {"input": dummy})
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Warmup failed for %s: %s", name, e)

    # --- preprocessing -----------------------------------------------------
    def preprocess(self, rgb: np.ndarray, info: ModelInfo) -> np.ndarray:
        """RGB HxWx3 uint8 -> normalised NCHW float32 at the model input size."""
        if rgb.shape[0] != info.input_h or rgb.shape[1] != info.input_w:
            rgb = cv2.resize(rgb, (info.input_w, info.input_h), interpolation=cv2.INTER_LINEAR)
        x = rgb.astype(np.float32) / 255.0
        x = (x - self.mean) / self.std
        x = np.transpose(x, (2, 0, 1))[None, ...]  # NCHW
        return np.ascontiguousarray(x, dtype=np.float32)

    # --- inference ---------------------------------------------------------
    def predict(self, name: str, rgb: np.ndarray, threshold: Optional[float] = None) -> PredictResult:
        """Run inference on an already-ROI-rectified RGB image.

        Returns a foreground mask + probability at the model input resolution.
        """
        info = self.get_info(name)
        thr = info.fg_threshold if threshold is None else float(threshold)
        sess = self._get_session(name)
        x = self.preprocess(rgb, info)

        t0 = time.perf_counter()
        logits = sess.run(["logits"], {"input": x})[0]  # (1, C, H, W)
        infer_ms = (time.perf_counter() - t0) * 1000.0

        prob = _softmax(logits, axis=1)[0]              # (C, H, W)
        fg_prob = prob[1] if prob.shape[0] > 1 else prob[0]
        mask = (fg_prob >= thr).astype(np.uint8)
        return PredictResult(
            mask=mask, fg_prob=fg_prob.astype(np.float32), infer_ms=infer_ms,
            input_h=info.input_h, input_w=info.input_w, threshold=thr,
        )


@lru_cache
def get_manager() -> InferenceManager:
    """Process-wide singleton inference manager."""
    return InferenceManager()
