"""Mask edge refinement (morphology + optional Canny edge support).

Operates on the ROI-space binary mask (224x640):
  - morphological OPEN then CLOSE: removes speckle noise + fills small holes,
    giving cleaner contours.
  - optional Canny: drops blobs that have no real image-edge support nearby
    (likely soft false positives), which can improve precision.

Note: the trained segmentation model remains the primary accuracy driver;
this is a light post-process that cleans/tightens the mask.
"""
from __future__ import annotations

import cv2
import numpy as np

_K = np.ones((3, 3), np.uint8)


def refine_mask(mask: np.ndarray, rgb: np.ndarray | None = None, use_canny: bool = True) -> np.ndarray:
    """Return a refined uint8 {0,1} mask (same shape as input)."""
    m = (mask > 0).astype(np.uint8)
    if m.sum() == 0:
        return m
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, _K)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, _K)

    if use_canny and rgb is not None:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edges_d = cv2.dilate(edges, _K, iterations=2) > 0
        n, lbl, _stats, _cent = cv2.connectedComponentsWithStats(m, connectivity=8)
        keep = np.zeros_like(m)
        for i in range(1, n):
            comp = lbl == i
            comp_d = cv2.dilate(comp.astype(np.uint8), _K, iterations=2) > 0
            # Keep the blob only if some real edge lies within/around it.
            if edges_d[comp_d].any():
                keep[comp] = 1
        m = keep
    return m
