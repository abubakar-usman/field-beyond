import pytest
from shapely.geometry import box

from core.scoring import (
    absolute_tolerances,
    score_window,
    similarity,
    wasserstein_hist_deg,
)
from core.scoring.grouping import ScoredWindow, group_windows, iou, nms

BINS = [0, 2, 5, 10, 15, 20, 30, 45, 90]


def test_similarity_formula():
    assert similarity(0, 5) == 100
    assert similarity(2.5, 5) == pytest.approx(50)
    assert similarity(5, 5) == 0
    assert similarity(50, 5) == 0
    with pytest.raises(ValueError):
        similarity(1, 0)


def test_docs_example_relief_similarity_32():
    # SCORING.md: "A relief gap of 210 m on a 310 m tolerance is similarity 32".
    assert round(similarity(210, 310)) == 32


def test_wasserstein_identical_is_zero():
    h = [0.1, 0.2, 0.3, 0.1, 0.1, 0.1, 0.05, 0.05]
    assert wasserstein_hist_deg(h, h, BINS) == pytest.approx(0)


def test_wasserstein_uniform_bins_is_mean_shift():
    # Uniform on [0,2] vs uniform on [2,5]: W1 = |1 - 3.5| = 2.5 degrees.
    a = [1, 0, 0, 0, 0, 0, 0, 0]
    b = [0, 1, 0, 0, 0, 0, 0, 0]
    assert wasserstein_hist_deg(a, b, BINS) == pytest.approx(2.5)


def test_wasserstein_uses_degrees_not_bin_index():
    # Moving mass from 30-45 to 45-90 is 37.5 - 22.5... centres 37.5 -> 67.5 = 30 degrees.
    a = [0, 0, 0, 0, 0, 0, 1, 0]
    b = [0, 0, 0, 0, 0, 0, 0, 1]
    assert wasserstein_hist_deg(a, b, BINS) == pytest.approx(30.0)


def test_wasserstein_symmetric_and_crossing():
    a = [0.5, 0, 0, 0, 0, 0, 0, 0.5]
    b = [0, 0, 0, 1, 0, 0, 0, 0]
    assert wasserstein_hist_deg(a, b, BINS) == pytest.approx(wasserstein_hist_deg(b, a, BINS))
    # mean(a) = 0.5*1 + 0.5*67.5 = 34.25; mean(b) = 12.5; W1 >= |diff of means|
    assert wasserstein_hist_deg(a, b, BINS) >= abs(34.25 - 12.5) - 1e-9


def _target():
    return {
        "slope_median": 8.0,
        "slope_p90": 20.0,
        "slope_hist": [0.1, 0.2, 0.3, 0.2, 0.1, 0.05, 0.05, 0.0],
        "relief": 620.0,
        "roughness": 30.0,
        "valid_fraction": 1.0,
    }


def test_tolerance_floors(scoring):
    tol = absolute_tolerances(_target(), scoring)
    assert tol["relief"] == 310
    assert tol["roughness"] == 15
    flat = dict(_target(), relief=10.0, roughness=1.0)
    tol = absolute_tolerances(flat, scoring)
    assert tol["relief"] == 20
    assert tol["roughness"] == 2


def test_perfect_match_scores_100(scoring):
    t = _target()
    avail = {k: True for k in t}
    s = score_window(t, avail, t, absolute_tolerances(t, scoring), scoring)
    assert s.total == pytest.approx(100)
    assert s.excluded_reason is None


def test_missing_mandatory_feature_excludes(scoring):
    t = _target()
    earth = dict(t, roughness=None)
    avail = {k: v is not None for k, v in earth.items()}
    s = score_window(earth, avail, t, absolute_tolerances(t, scoring), scoring)
    assert s.total is None
    assert s.excluded_reason == "missing_mandatory_feature"
    assert s.missing == ["roughness"]


def test_availability_flag_false_excludes_even_with_value(scoring):
    t = _target()
    avail = {k: True for k in t}
    avail["relief"] = False
    s = score_window(t, avail, t, absolute_tolerances(t, scoring), scoring)
    assert s.total is None


def test_weighted_total_and_main_mismatch(scoring):
    t = _target()
    earth = dict(t, relief=410.0)  # 210 m off on a 310 m tolerance -> 32.26
    avail = {k: True for k in earth}
    s = score_window(earth, avail, t, absolute_tolerances(t, scoring), scoring)
    rel = 100 * (1 - 210 / 310)
    expected = (0.30 * 100 + 0.20 * 100 + 0.15 * 100 + 0.20 * rel + 0.15 * 100) / 1.0
    assert s.total == pytest.approx(expected)
    assert s.main_mismatch == "relief"
    assert s.components["relief"].within_tolerance


# ---------------------------------------------------------------- grouping


def _w(cell_id, score, ix, iy):
    x0, y0 = ix * 5000, iy * 5000
    return ScoredWindow(cell_id, score, box(x0, y0, x0 + 10000, y0 + 10000))


def test_iou_cardinal_and_diagonal():
    a = _w(1, 0, 0, 0).geom
    assert iou(a, _w(2, 0, 1, 0).geom) == pytest.approx(1 / 3)
    assert iou(a, _w(3, 0, 1, 1).geom) == pytest.approx(25 / 175)
    assert iou(a, _w(4, 0, 2, 0).geom) == 0


def test_docs_worked_example(scoring):
    a = _w(10, 80, 0, 0)
    d = _w(40, 75, 1, 1)  # diagonal
    b = _w(20, 70, 1, 0)  # east
    c = _w(30, 60, 0, 1)  # north
    kept = nms([a, b, c, d], scoring.grouping.nms_iou_above)
    assert [k.cell_id for k in kept] == [10, 40]
    groups = group_windows([a, b, c, d], scoring.grouping.nms_iou_above)
    assert len(groups) == 1
    assert groups[0].score == 80
    assert [m.cell_id for m in groups[0].members] == [10, 40]


def test_shared_edge_stays_separate():
    a = _w(1, 90, 0, 0)
    b = _w(2, 85, 2, 0)  # touches A's east edge, zero area overlap
    groups = group_windows([a, b], 0.3)
    assert len(groups) == 2


def test_tie_break_smaller_cell_id_first():
    a = _w(7, 50, 0, 0)
    b = _w(3, 50, 1, 0)
    kept = nms([a, b], 0.3)
    assert [k.cell_id for k in kept] == [3]
