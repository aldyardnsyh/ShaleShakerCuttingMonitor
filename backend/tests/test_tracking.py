"""Tracking — Kalman multi-object tracker tests."""
import numpy as np

from app.core.tracking import MultiObjectTracker, mask_to_boxes, iou


def test_iou_basic():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0


def test_mask_to_boxes_counts_blobs():
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[10:30, 10:30] = 1
    mask[100:130, 100:140] = 1
    boxes = mask_to_boxes(mask, min_area=10)
    assert len(boxes) == 2


def test_track_velocity_for_moving_box():
    """A box moving right at +5 px/step yields a positive vx in det_vels."""
    tr = MultiObjectTracker(iou_threshold=0.05, max_age=5, min_hits=2)
    vels = []
    x = 50
    for _ in range(8):
        dv = tr.update([(x, 50, 20, 20)])
        x += 5
        if dv:
            vels.append(dv[0])
    assert vels, "expected velocity output"
    assert vels[-1][0] > 0.5  # learned rightward velocity


def test_update_empty_detections():
    tr = MultiObjectTracker(iou_threshold=0.1, max_age=2, min_hits=1)
    for _ in range(3):
        tr.update([(50, 50, 20, 20)])
    assert tr.update([]) == []
