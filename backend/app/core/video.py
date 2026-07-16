"""Video decoding + overlay rendering helpers (OpenCV)."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Iterator, Optional

import cv2
import numpy as np

# Overlay colors in BGR (OpenCV).
_PRED_COLOR_BGR = (30, 30, 220)   # red-ish foreground overlay
_ROI_COLOR_BGR = (0, 220, 220)    # yellow ROI polygon


@dataclass
class VideoInfo:
    fps: float
    frame_count: int
    width: int
    height: int


def get_video_info(path: str) -> VideoInfo:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Tidak bisa membuka video: {path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        return VideoInfo(fps=float(fps), frame_count=n, width=w, height=h)
    finally:
        cap.release()


def iter_frames(path: str, stride: int = 1, max_frames: Optional[int] = None) -> Iterator[tuple[int, np.ndarray]]:
    """Yield (frame_idx, BGR frame) every `stride` frames, up to max_frames yielded."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Tidak bisa membuka video: {path}")
    stride = max(1, int(stride))
    idx = 0
    yielded = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % stride == 0:
                yield idx, frame
                yielded += 1
                if max_frames is not None and yielded >= max_frames:
                    break
            idx += 1
    finally:
        cap.release()


def draw_overlay(frame_bgr: np.ndarray, full_mask: np.ndarray, roi_src: list, alpha: float = 0.5) -> np.ndarray:
    """Overlay the foreground mask (full-frame) + ROI polygon onto a BGR frame."""
    out = frame_bgr.copy()
    m = full_mask > 0
    if m.any():
        out[m] = ((1 - alpha) * out[m] + alpha * np.array(_PRED_COLOR_BGR)).astype(np.uint8)
    try:
        poly = np.array(roi_src, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [poly], isClosed=True, color=_ROI_COLOR_BGR, thickness=2)
    except Exception:
        pass
    return out


def encode_jpeg_b64(frame_bgr: np.ndarray, quality: int = 70, max_width: int = 960) -> str:
    """Encode a BGR frame to a base64 data URL JPEG (downscaled to save bandwidth)."""
    h, w = frame_bgr.shape[:2]
    if w > max_width:
        scale = max_width / w
        frame_bgr = cv2.resize(frame_bgr, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode()
    return f"data:image/jpeg;base64,{b64}"
