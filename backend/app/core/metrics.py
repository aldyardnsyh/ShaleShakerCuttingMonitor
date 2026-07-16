"""Cutting metrics derived from a foreground segmentation mask.

- fg_area_pct : percentage of ROI pixels classified as cutting (foreground).
- stone_count : number of distinct cutting blobs (connected components),
                filtered by a minimum area to suppress speckle noise.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np

from app.config import settings


@dataclass
class Metrics:
    fg_px: int
    roi_px: int
    fg_area_pct: float
    stone_count: int
    coverage_pct: float = 0.0
    grid_cols: int = 0
    grid_rows: int = 0
    occupied_cells: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def fg_area(mask: np.ndarray, roi_px: int | None = None) -> tuple[int, int, float]:
    """Return (fg_px, roi_px, fg_area_pct)."""
    binary = (mask > 0)
    fg_px = int(binary.sum())
    total = int(roi_px) if roi_px is not None else int(binary.size)
    pct = (fg_px / total * 100.0) if total > 0 else 0.0
    return fg_px, total, round(pct, 4)


def count_stones(mask: np.ndarray, min_area: int | None = None) -> int:
    """Count connected foreground components with area >= min_area."""
    if min_area is None:
        min_area = settings.MIN_STONE_AREA
    binary = (mask > 0).astype(np.uint8)
    if binary.sum() == 0:
        return 0
    # connectivity=8; label 0 is background.
    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    count = 0
    for label in range(1, num_labels):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            count += 1
    return count


def compute_metrics(mask: np.ndarray, roi_px: int | None = None, min_area: int | None = None,
                    cell_px: int | None = None, occ_fraction: float | None = None) -> Metrics:
    fg_px, total, pct = fg_area(mask, roi_px)
    stones = count_stones(mask, min_area)
    cov_pct, cols, rows, occupied = grid_coverage(mask, cell_px, occ_fraction)
    return Metrics(
        fg_px=fg_px, roi_px=total, fg_area_pct=pct, stone_count=stones,
        coverage_pct=cov_pct, grid_cols=cols, grid_rows=rows, occupied_cells=occupied,
    )


def grid_coverage(mask: np.ndarray, cell_px: int | None = None,
                  occ_fraction: float | None = None) -> tuple[float, int, int, int]:
    """Grid-quadrat percent cover (research-grounded).

    The (already perspective-rectified) ROI mask is partitioned into square
    cells of size `cell_px` (~ average stone footprint). A cell counts as
    "occupied" when its foreground pixel fraction >= `occ_fraction`.

        coverage_pct = occupied_cells / total_cells * 100

    This estimates the share of the shale-shaker surface covered by cuttings
    (spatial spread), and is more robust to blob shape than raw pixel %.
    Reference: quadrat-grid / point-intercept percent-cover methods.

    Returns (coverage_pct, n_cols, n_rows, occupied_cells).
    """
    if cell_px is None:
        cell_px = settings.GRID_CELL_PX
    if occ_fraction is None:
        occ_fraction = settings.GRID_OCC_FRACTION
    cell_px = max(1, int(cell_px))

    h, w = mask.shape[:2]
    n_rows, n_cols = h // cell_px, w // cell_px
    if n_rows == 0 or n_cols == 0:
        return 0.0, n_cols, n_rows, 0

    binary = (mask > 0).astype(np.int32)
    # Crop to a whole number of cells, then block-reduce to per-cell fg counts.
    cropped = binary[: n_rows * cell_px, : n_cols * cell_px]
    blocks = cropped.reshape(n_rows, cell_px, n_cols, cell_px)
    cell_counts = blocks.sum(axis=(1, 3))  # (n_rows, n_cols)

    min_px = max(1, int(occ_fraction * cell_px * cell_px))
    occupied = int((cell_counts >= min_px).sum())
    total = n_rows * n_cols
    coverage = occupied / total * 100.0 if total > 0 else 0.0
    return round(coverage, 4), n_cols, n_rows, occupied



def mask_to_polygons(mask: np.ndarray, min_area: int = 20, epsilon_frac: float = 0.01,
                     max_polys: int = 120) -> list[list[list[int]]]:
    """Simplified external contour polygons of the foreground mask.

    Returns a list of polygons; each polygon is a list of [x, y] integer points
    (in the mask's coordinate space). Used to draw a clean translucent mask
    overlay on the client (no IDs/labels). Small blobs are dropped and contours
    are simplified to keep the payload light.
    """
    binary = (mask > 0).astype(np.uint8)
    if binary.sum() == 0:
        return []
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Largest blobs first so we keep the most significant cuttings if capped.
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    polys: list[list[list[int]]] = []
    for c in contours:
        if cv2.contourArea(c) < min_area:
            continue
        eps = max(1.0, epsilon_frac * cv2.arcLength(c, True))
        approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(approx) >= 3:
            polys.append(approx.astype(int).tolist())
        if len(polys) >= max_polys:
            break
    return polys



def mask_to_blobs(mask: np.ndarray, min_area: int = 20, epsilon_frac: float = 0.01,
                  max_blobs: int = 120) -> list[tuple]:
    """Return aligned (polygon, bbox) per foreground blob.

    polygon = list of [x, y] points (simplified contour); bbox = (x, y, w, h).
    Used so each drawn mask polygon can be motion-compensated by its tracked
    velocity (bbox feeds the Kalman tracker).
    """
    binary = (mask > 0).astype(np.uint8)
    if binary.sum() == 0:
        return []
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    out: list[tuple] = []
    for c in contours:
        if cv2.contourArea(c) < min_area:
            continue
        eps = max(1.0, epsilon_frac * cv2.arcLength(c, True))
        approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        x, y, w, h = cv2.boundingRect(c)
        out.append((approx.astype(int).tolist(), (int(x), int(y), int(w), int(h))))
        if len(out) >= max_blobs:
            break
    return out
