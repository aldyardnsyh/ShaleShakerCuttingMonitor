"""ROI perspective warp utilities."""
from __future__ import annotations

import cv2
import numpy as np

DEFAULT_ROI_SRC = [[760, 650], [1300, 614], [1315, 795], [780, 845]]
CROP_W = 640
CROP_H = 224


def get_transforms(
    roi_src: list, out_w: int = CROP_W, out_h: int = CROP_H
) -> tuple[np.ndarray, np.ndarray]:
    """Return (M, M_inv) perspective transform matrices (float32 3x3)."""
    if len(roi_src) != 4:
        raise ValueError("roi_src must have exactly 4 points")
    src = np.array(roi_src, dtype=np.float32)
    dst = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(src, dst)
    M_inv = cv2.getPerspectiveTransform(dst, src)
    return M, M_inv


def warp_to_roi(
    image_bgr_or_rgb: np.ndarray,
    roi_src: list = DEFAULT_ROI_SRC,
    out_w: int = CROP_W,
    out_h: int = CROP_H,
) -> np.ndarray:
    """Warp full image to rectified ROI crop (INTER_LINEAR)."""
    M, _ = get_transforms(roi_src, out_w, out_h)
    return cv2.warpPerspective(image_bgr_or_rgb, M, (out_w, out_h), flags=cv2.INTER_LINEAR)


def warp_mask_to_full(
    mask: np.ndarray, roi_src: list, full_w: int, full_h: int
) -> np.ndarray:
    """Inverse-warp a mask from ROI space back to full image space (INTER_NEAREST, uint8)."""
    _, M_inv = get_transforms(roi_src, mask.shape[1], mask.shape[0])
    return cv2.warpPerspective(
        mask.astype(np.uint8), M_inv, (full_w, full_h), flags=cv2.INTER_NEAREST
    )


def roi_bbox(roi_src: list) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) integer bounding box of the ROI polygon."""
    pts = np.array(roi_src)
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    return int(x0), int(y0), int(x1), int(y1)
