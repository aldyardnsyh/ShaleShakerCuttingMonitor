"""Application configuration.

Centralised settings read from environment variables (with sane defaults
tuned for a constrained 2 vCPU / 2 GB VPS). Import `settings` everywhere.
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache


# Project layout anchors -------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent            # backend/app
BACKEND_DIR = APP_DIR.parent                          # backend
PROJECT_ROOT = BACKEND_DIR.parent                     # shale-shaker-dashboard


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Settings:
    """Runtime settings. Values resolve from env at import time."""

    # --- General -------------------------------------------------------------
    APP_NAME: str = "Shale Shaker Cutting Dashboard"
    APP_VERSION: str = "0.1.0"
    # IANA timezone used to stamp server time on websocket/measurement payloads.
    TIMEZONE: str = os.getenv("APP_TIMEZONE", "Asia/Jakarta")

    # --- Paths ---------------------------------------------------------------
    # Directory that holds the exported ONNX models + model_meta.json.
    MODELS_DIR: Path = Path(os.getenv("MODELS_DIR", str(PROJECT_ROOT / "ml" / "onnx")))
    # Built frontend (Next.js static export) is copied here in Docker builds.
    STATIC_DIR: Path = Path(os.getenv("STATIC_DIR", str(APP_DIR / "static")))
    # Writable data dir (sqlite db + uploaded videos). Mounted as a volume.
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
    # Pre-loaded demo/test videos for quick evaluation (read-only, mounted in Docker).
    SOURCE_VIDEOS_DIR: Path = Path(os.getenv("SOURCE_VIDEOS_DIR", str(PROJECT_ROOT / "data" / "source_videos")))
    # Auto-cleanup: delete video files of completed sessions older than this.
    CLEANUP_RETENTION_DAYS: int = _get_int("CLEANUP_RETENTION_DAYS", 3)

    # --- Database ------------------------------------------------------------
    @property
    def DATABASE_URL(self) -> str:
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.DATA_DIR / 'app.db').as_posix()}"

    @property
    def UPLOAD_DIR(self) -> Path:
        d = self.DATA_DIR / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def EXPORTS_DIR(self) -> Path:
        d = self.DATA_DIR / "exports"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # --- Inference (CPU-friendly defaults) -----------------------------------
    # ONNX Runtime intra-op threads. Default = available CPUs (capped at 4)
    # so local/multi-core boxes run faster; the VPS overrides to 2 via env.
    ORT_INTRA_OP_THREADS: int = _get_int("ORT_INTRA_OP_THREADS", min((os.cpu_count() or 2), 4))
    ORT_INTER_OP_THREADS: int = _get_int("ORT_INTER_OP_THREADS", 1)
    # Default model + per-frame processing stride for video.
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "mobilevit")
    DEFAULT_STRIDE: int = _get_int("DEFAULT_STRIDE", 3)
    # Minimum connected-component area (px, in 224x640 ROI space) to count a stone.
    MIN_STONE_AREA: int = _get_int("MIN_STONE_AREA", 8)
    # Grid-quadrat coverage metric (rectified ROI space 224x640).
    # GRID_CELL_PX ~ average stone footprint; a cell counts as occupied when
    # its foreground fraction >= GRID_OCC_FRACTION.
    GRID_CELL_PX: int = _get_int("GRID_CELL_PX", 16)
    GRID_OCC_FRACTION: float = float(os.getenv("GRID_OCC_FRACTION", "0.05"))
    # Mask edge refinement (morphology + optional Canny) default for new sessions.
    REFINE_EDGES: bool = _get_bool("REFINE_EDGES", True)
    # Tracking (full-frame space): min blob area + Kalman tracker lifecycle.
    TRACK_MIN_AREA: int = _get_int("TRACK_MIN_AREA", 30)
    TRACK_MAX_AGE: int = _get_int("TRACK_MAX_AGE", 15)
    TRACK_MIN_HITS: int = _get_int("TRACK_MIN_HITS", 2)
    TRACK_IOU: float = float(os.getenv("TRACK_IOU", "0.1"))
    # Centroid-distance association gate (full-frame px). Used as a fallback when
    # boxes don't overlap (small/fast stones across a large stride) so motion is
    # still captured. Effective gate = max(this, 1.5*max(w,h)).
    TRACK_DIST_GATE: float = float(os.getenv("TRACK_DIST_GATE", "90"))

    # --- CORS ----------------------------------------------------------------
    # Comma separated origins. "*" by default (internal-only deployment).
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
    ]


@lru_cache
def get_settings() -> "Settings":
    return Settings()


settings = get_settings()
