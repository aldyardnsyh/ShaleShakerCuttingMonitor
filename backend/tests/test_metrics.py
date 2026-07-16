"""Task 3 — metrics unit tests."""
import numpy as np

from app.core.metrics import compute_metrics, count_stones, fg_area


def test_fg_area_pct():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[:10, :] = 1  # 1000 of 10000 px = 10%
    fg_px, roi_px, pct = fg_area(mask)
    assert fg_px == 1000
    assert roi_px == 10000
    assert abs(pct - 10.0) < 1e-6


def test_fg_area_with_explicit_roi_px():
    mask = np.zeros((50, 50), dtype=np.uint8)
    mask[:5, :10] = 1  # 50 px
    fg_px, roi_px, pct = fg_area(mask, roi_px=500)
    assert fg_px == 50
    assert roi_px == 500
    assert abs(pct - 10.0) < 1e-6


def test_count_stones_three_blobs():
    mask = np.zeros((100, 100), dtype=np.uint8)
    # three well-separated 5x5 blobs
    mask[5:10, 5:10] = 1
    mask[5:10, 50:55] = 1
    mask[50:55, 50:55] = 1
    assert count_stones(mask, min_area=4) == 3


def test_count_stones_filters_small_noise():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:20, 10:20] = 1   # 100 px blob (kept)
    mask[80, 80] = 1          # 1 px speck (filtered)
    assert count_stones(mask, min_area=8) == 1


def test_count_stones_empty():
    mask = np.zeros((30, 30), dtype=np.uint8)
    assert count_stones(mask, min_area=8) == 0


def test_compute_metrics_bundle():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[0:10, 0:10] = 1  # 100 px = 1%
    m = compute_metrics(mask, min_area=4)
    assert m.fg_px == 100
    assert m.stone_count == 1
    assert abs(m.fg_area_pct - 1.0) < 1e-6


def test_grid_coverage_empty_and_full():
    from app.core.metrics import grid_coverage
    # empty mask -> 0% coverage
    empty = np.zeros((224, 640), dtype=np.uint8)
    cov, cols, rows, occ = grid_coverage(empty, cell_px=16, occ_fraction=0.05)
    assert cov == 0.0 and occ == 0 and cols == 40 and rows == 14
    # fully filled -> 100% coverage
    full = np.ones((224, 640), dtype=np.uint8)
    cov, cols, rows, occ = grid_coverage(full, cell_px=16, occ_fraction=0.05)
    assert cov == 100.0 and occ == cols * rows


def test_grid_coverage_single_cell():
    from app.core.metrics import grid_coverage
    mask = np.zeros((64, 64), dtype=np.uint8)
    # one fully-filled 16x16 cell out of (64/16)^2 = 16 cells -> 6.25%
    mask[0:16, 0:16] = 1
    cov, cols, rows, occ = grid_coverage(mask, cell_px=16, occ_fraction=0.05)
    assert cols == 4 and rows == 4 and occ == 1
    assert abs(cov - 6.25) < 1e-6


def test_grid_coverage_noise_filtered():
    from app.core.metrics import grid_coverage
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[0, 0] = 1  # single px in a 16x16 cell -> 1/256 < 5% -> not occupied
    cov, _, _, occ = grid_coverage(mask, cell_px=16, occ_fraction=0.05)
    assert occ == 0 and cov == 0.0
