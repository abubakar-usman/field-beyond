"""Synthetic-DEM tests with analytically known answers, on Earth, Moon and Mars.

Each test builds the DEM on the body's own ground: the pixel size comes from an
angular spacing converted with that body's radius, so a radius mix-up shows up
as a wrong slope.
"""

import math

import numpy as np
import pytest

from core.bodies import MARS, MOON, metres_per_degree
from core.features import (
    compute_profile,
    horn_slope_deg,
    relief,
    roughness,
    slope_hist,
    slope_median,
    slope_p90,
    valid_fraction,
)

BINS = [0, 2, 5, 10, 15, 20, 30, 45, 90]
N = 50  # 10 km window at 200 m


def _xy(n: int, px: float) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    return xx * px, yy * px


def _pixel_from_body(body, scale_m: float) -> float:
    """Ground pixel built from an angular spacing on this body (round-trips to scale_m)."""
    _, m_per_deg_lat = metres_per_degree(body, 0.0)
    dlat = scale_m / m_per_deg_lat
    return dlat * m_per_deg_lat


def test_flat(body_scale):
    _, px = body_scale
    dem = np.full((N, N), 1234.5)
    p = compute_profile(dem, px, bins_deg=BINS)
    assert p.values["slope_median"] == pytest.approx(0)
    assert p.values["slope_p90"] == pytest.approx(0)
    assert p.values["slope_hist"][0] == pytest.approx(1)
    assert p.values["relief"] == pytest.approx(0)
    assert p.values["roughness"] == pytest.approx(0, abs=1e-6)
    assert p.values["valid_fraction"] == 1.0


@pytest.mark.parametrize("angle", [3.0, 12.5, 33.0])
def test_tilted_plane_exact_slope(body_scale, angle):
    body, scale = body_scale
    px = _pixel_from_body(body, scale)
    x, y = _xy(N, px)
    # tilt along a diagonal direction to exercise both gradient axes
    az = math.radians(30)
    dem = math.tan(math.radians(angle)) * (x * math.cos(az) + y * math.sin(az))
    s = horn_slope_deg(dem, px)
    inner = s[1:-1, 1:-1]
    assert np.allclose(inner, angle, atol=1e-9)
    assert slope_median(dem, px) == pytest.approx(angle, abs=1e-9)
    assert slope_p90(dem, px) == pytest.approx(angle, abs=1e-9)
    assert roughness(dem, px) == pytest.approx(0, abs=1e-6)
    h = slope_hist(dem, px, bins_deg=BINS)
    k = int(np.searchsorted(BINS, angle, side="right") - 1)
    assert h[k] == pytest.approx(1.0)


def test_wrong_body_radius_gives_wrong_slope():
    # Same angular DEM spacing, but slope computed with the other body's pixel size.
    dlat = 1 / 512
    px_moon = dlat * metres_per_degree(MOON, 0)[1]
    px_mars = dlat * metres_per_degree(MARS, 0)[1]
    x, _ = _xy(N, px_moon)
    dem = math.tan(math.radians(10)) * x
    right = slope_median(dem, px_moon)
    wrong = slope_median(dem, px_mars)
    assert right == pytest.approx(10, abs=1e-9)
    assert wrong < 6  # ~5.2 degrees: off by the radius ratio


def test_cone(body_scale):
    _, px = body_scale
    x, y = _xy(N, px)
    c = (N - 1) / 2 * px
    r = np.hypot(x - c, y - c)
    k = math.tan(math.radians(20))
    dem = 5000 - k * r
    # Away from the apex, Horn's slope on a cone equals the generator slope.
    s = horn_slope_deg(dem, px)
    ring = (r > 3 * px) & np.isfinite(s)
    assert np.median(s[ring]) == pytest.approx(20, abs=0.3)
    assert slope_median(dem, px) == pytest.approx(20, abs=0.5)


def test_relief_of_linear_ramp(body_scale):
    _, px = body_scale
    x, _ = _xy(N, px)
    dem = 2.0 * x / px  # 0..98 m in 2 m steps, each value on N pixels
    expected = np.percentile(dem, 95) - np.percentile(dem, 5)
    assert relief(dem, px) == pytest.approx(expected)
    assert relief(dem, px) == pytest.approx(0.9 * 98, abs=2.0)


def test_roughness_recovers_noise_sigma(body_scale):
    body, scale = body_scale
    px = _pixel_from_body(body, scale)
    rng = np.random.default_rng(42)
    x, y = _xy(120, px)
    sigma = 7.5
    dem = 0.1 * x - 0.05 * y + 300 + rng.normal(0, sigma, size=x.shape)
    assert roughness(dem, px) == pytest.approx(sigma, rel=0.03)


def test_mask_and_nan_handling(body_scale):
    _, px = body_scale
    x, _ = _xy(N, px)
    dem = math.tan(math.radians(8)) * x
    dem[10:20, 10:20] = np.nan
    mask = np.ones_like(dem, dtype=bool)
    mask[:, :5] = False
    p = compute_profile(dem, px, mask, bins_deg=BINS)
    assert p.values["slope_median"] == pytest.approx(8, abs=1e-9)
    assert p.values["valid_fraction"] == pytest.approx(1 - (100 + 5 * N) / N**2)
    assert valid_fraction(dem, mask) == p.values["valid_fraction"]


def test_all_missing_returns_none_not_zero(body_scale):
    _, px = body_scale
    dem = np.full((N, N), np.nan)
    p = compute_profile(dem, px, bins_deg=BINS)
    for key in ("slope_median", "slope_p90", "slope_hist", "relief", "roughness"):
        assert p.values[key] is None
        assert p.availability[key] is False
    assert p.values["valid_fraction"] == 0.0


def test_histogram_sums_to_one(body_scale):
    _, px = body_scale
    rng = np.random.default_rng(0)
    dem = np.cumsum(rng.normal(0, 30, size=(N, N)), axis=1)
    h = slope_hist(dem, px, bins_deg=BINS)
    assert sum(h) == pytest.approx(1.0)
    assert len(h) == len(BINS) - 1


def test_bad_pixel_size():
    with pytest.raises(ValueError):
        horn_slope_deg(np.zeros((5, 5)), 0)
