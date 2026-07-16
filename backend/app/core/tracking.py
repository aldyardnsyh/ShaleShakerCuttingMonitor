"""Kalman-based multi-object tracker for cuttings (SORT-style, lightweight).

Each stone blob (bbox from connected components, in FULL-FRAME pixel coords)
is tracked with a constant-velocity Kalman filter on its centroid. This:
  - stabilises stone_count (no per-frame flicker),
  - yields per-stone velocity (vx, vy in px/frame) so the frontend can
    extrapolate positions on frames where heavy inference was skipped,
    making the overlay move smoothly between detections.

No external deps beyond numpy + OpenCV (cv2.KalmanFilter).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


def iou(a: tuple, b: tuple) -> float:
    """IoU of two (x, y, w, h) boxes."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2, bx2, by2 = ax + aw, ay + ah, bx + bw, by + bh
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


class _KalmanBox:
    """Constant-velocity Kalman filter on the box centroid; keeps last w,h."""

    _next_id = 1

    def __init__(self, bbox: tuple):
        x, y, w, h = bbox
        cx, cy = x + w / 2.0, y + h / 2.0
        kf = cv2.KalmanFilter(4, 2)
        kf.transitionMatrix = np.array(
            [[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32
        )
        kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        # Position drifts slowly but velocity must adapt quickly to real motion,
        # so give the velocity states a larger process noise. Trusting the
        # measurement (lower noise) makes the estimate follow the stone closely.
        kf.processNoiseCov = np.diag([1e-2, 1e-2, 5e-1, 5e-1]).astype(np.float32)
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.5
        kf.errorCovPost = np.eye(4, dtype=np.float32)
        kf.statePost = np.array([[cx], [cy], [0], [0]], np.float32)
        self.kf = kf
        self.w, self.h = float(w), float(h)
        self.id = _KalmanBox._next_id
        _KalmanBox._next_id += 1
        self.hits = 1
        self.misses = 0
        self.age = 0

    def predict(self) -> tuple:
        p = self.kf.predict()
        self.age += 1
        return float(p[0, 0]), float(p[1, 0])

    def update(self, bbox: tuple) -> None:
        x, y, w, h = bbox
        cx, cy = x + w / 2.0, y + h / 2.0
        self.kf.correct(np.array([[cx], [cy]], np.float32))
        self.w, self.h = float(w), float(h)
        self.hits += 1
        self.misses = 0

    @property
    def state(self) -> tuple:
        s = self.kf.statePost
        return float(s[0, 0]), float(s[1, 0]), float(s[2, 0]), float(s[3, 0])  # cx, cy, vx, vy

    def centroid(self) -> tuple:
        s = self.kf.statePost
        return float(s[0, 0]), float(s[1, 0])

    def bbox(self) -> tuple:
        cx, cy, _, _ = self.state
        return cx - self.w / 2.0, cy - self.h / 2.0, self.w, self.h


@dataclass
class TrackOut:
    id: int
    x: float
    y: float
    w: float
    h: float
    vx: float
    vy: float


class MultiObjectTracker:
    def __init__(self, iou_threshold: float = 0.1, max_age: int = 15,
                 min_hits: int = 2, dist_gate: float = 90.0):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.dist_gate = dist_gate
        self.tracks: list[_KalmanBox] = []

    def update(self, detections: list[tuple]) -> list[tuple]:
        """Advance one step and return per-detection velocity (vx, vy) in
        px/step, aligned to the input `detections` order. No IDs are exposed —
        the velocity is used purely to motion-compensate the mask on the client.

        Association is two-pass: first greedy IoU (tight overlap), then a
        centroid-distance gate fallback so small/fast stones that do NOT overlap
        between strided detections still get matched → their motion is captured
        instead of collapsing to velocity 0.
        """
        for t in self.tracks:
            t.predict()

        unmatched_dets = set(range(len(detections)))
        det_track: dict[int, _KalmanBox] = {}
        matched_tracks: set[int] = set()

        # Detection centroids (for distance fallback).
        det_centroids = [(dx + dw / 2.0, dy + dh / 2.0) for (dx, dy, dw, dh) in detections]

        # --- Pass 1: greedy IoU matching (predicted bbox vs detections). ---
        pairs = []
        for ti, t in enumerate(self.tracks):
            tb = t.bbox()
            for di in unmatched_dets:
                score = iou(tb, detections[di])
                if score >= self.iou_threshold:
                    pairs.append((score, ti, di))
        pairs.sort(reverse=True)
        for score, ti, di in pairs:
            if ti in matched_tracks or di not in unmatched_dets:
                continue
            self.tracks[ti].update(detections[di])
            matched_tracks.add(ti)
            unmatched_dets.discard(di)
            det_track[di] = self.tracks[ti]

        # --- Pass 2: centroid-distance gate for whatever is still unmatched. ---
        dpairs = []
        for ti, t in enumerate(self.tracks):
            if ti in matched_tracks:
                continue
            tcx, tcy = t.centroid()
            # Per-track adaptive gate (bigger stones may move farther).
            gate = max(self.dist_gate, 1.5 * max(t.w, t.h))
            for di in unmatched_dets:
                dcx, dcy = det_centroids[di]
                dist = ((tcx - dcx) ** 2 + (tcy - dcy) ** 2) ** 0.5
                if dist <= gate:
                    dpairs.append((dist, ti, di))
        dpairs.sort()  # nearest first
        for dist, ti, di in dpairs:
            if ti in matched_tracks or di not in unmatched_dets:
                continue
            self.tracks[ti].update(detections[di])
            matched_tracks.add(ti)
            unmatched_dets.discard(di)
            det_track[di] = self.tracks[ti]

        # Age unmatched tracks; create new tracks for unmatched detections.
        for ti, t in enumerate(self.tracks):
            if ti not in matched_tracks:
                t.misses += 1
        for di in list(unmatched_dets):
            nt = _KalmanBox(detections[di])
            self.tracks.append(nt)
            det_track[di] = nt

        # Per-detection velocity (before culling, so mapping stays valid).
        det_vels: list[tuple] = []
        for di in range(len(detections)):
            tk = det_track.get(di)
            if tk is None:
                det_vels.append((0.0, 0.0))
            else:
                _, _, vx, vy = tk.state
                det_vels.append((vx, vy))

        # Cull dead tracks.
        self.tracks = [t for t in self.tracks if t.misses <= self.max_age]
        return det_vels


def mask_to_boxes(mask: np.ndarray, min_area: int = 20) -> list[tuple]:
    """Connected-component bounding boxes (x, y, w, h) for a binary mask."""
    binary = (mask > 0).astype(np.uint8)
    if binary.sum() == 0:
        return []
    n, _labels, stats, _cent = cv2.connectedComponentsWithStats(binary, connectivity=8)
    boxes = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])
            boxes.append((x, y, w, h))
    return boxes
