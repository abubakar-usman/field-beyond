"""Terrain features (terrain-features-v1).

Pure functions with the signature ``(dem, pixel_size_m, mask) -> value | None``.
The same code runs for Earth windows and planetary targets: there are no
body-specific branches here. The caller passes the true ground pixel size in
metres on the correct body (see core.bodies and core.raster).

``None`` means "not computable". It is never replaced by 0 or a fill value
(CLAUDE.md rule 4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.floating[Any]]
BoolArray = NDArray[np.bool_]

FEATURE_SCHEMA_VERSION = "terrain-features-v1"


def _effective_mask(dem: FloatArray, mask: BoolArray | None) -> BoolArray:
    finite = np.isfinite(dem)
    return finite if mask is None else (finite & mask.astype(bool))


def _masked_dem(dem: FloatArray, mask: BoolArray | None) -> FloatArray:
    m = _effective_mask(dem, mask)
    out = np.array(dem, dtype=np.float64, copy=True)
    out[~m] = np.nan
    return out


def horn_slope_deg(
    dem: FloatArray, pixel_size_m: float, mask: BoolArray | None = None
) -> FloatArray:
    """Slope in degrees by Horn (1981) on a square-pixel grid.

    Edge pixels, and any pixel with a masked or non-finite neighbour, are NaN.
    """
    if pixel_size_m <= 0:
        raise ValueError("pixel_size_m must be positive")
    z = _masked_dem(dem, mask)
    out = np.full(z.shape, np.nan)
    if z.shape[0] < 3 or z.shape[1] < 3:
        return out
    a = z[:-2, :-2]
    b = z[:-2, 1:-1]
    c = z[:-2, 2:]
    d = z[1:-1, :-2]
    f = z[1:-1, 2:]
    g = z[2:, :-2]
    h = z[2:, 1:-1]
    i = z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pixel_size_m)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * pixel_size_m)
    out[1:-1, 1:-1] = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    return out


def _valid_slopes(slope: FloatArray) -> FloatArray:
    return slope[np.isfinite(slope)]


def slope_median(
    dem: FloatArray, pixel_size_m: float, mask: BoolArray | None = None
) -> float | None:
    s = _valid_slopes(horn_slope_deg(dem, pixel_size_m, mask))
    return float(np.median(s)) if s.size else None


def slope_p90(dem: FloatArray, pixel_size_m: float, mask: BoolArray | None = None) -> float | None:
    s = _valid_slopes(horn_slope_deg(dem, pixel_size_m, mask))
    return float(np.percentile(s, 90)) if s.size else None


def slope_hist(
    dem: FloatArray,
    pixel_size_m: float,
    mask: BoolArray | None = None,
    *,
    bins_deg: Sequence[float],
) -> list[float] | None:
    """Fraction of valid slope pixels per bin. The last bin includes its upper edge."""
    s = _valid_slopes(horn_slope_deg(dem, pixel_size_m, mask))
    if not s.size:
        return None
    counts, _ = np.histogram(s, bins=np.asarray(bins_deg, dtype=float))
    return [float(c) / float(s.size) for c in counts]


def relief(dem: FloatArray, pixel_size_m: float, mask: BoolArray | None = None) -> float | None:
    """95th minus 5th percentile elevation, metres. ``pixel_size_m`` is unused but kept for the shared signature."""
    del pixel_size_m
    z = _masked_dem(dem, mask)
    v = z[np.isfinite(z)]
    if v.size < 2:
        return None
    p5, p95 = np.percentile(v, [5, 95])
    return float(p95 - p5)


def roughness(dem: FloatArray, pixel_size_m: float, mask: BoolArray | None = None) -> float | None:
    """Standard deviation (ddof=0) of residuals after a least-squares plane fit, metres.

    The plane is fitted in metric coordinates over every valid pixel of the
    window, so the declared scale is the window size at this pixel size.
    """
    z = _masked_dem(dem, mask)
    rows, cols = np.nonzero(np.isfinite(z))
    if rows.size < 4:
        return None
    values = z[rows, cols]
    # Centre coordinates and values so the 2x2 normal equations are well conditioned.
    x = cols.astype(float) * pixel_size_m
    y = rows.astype(float) * pixel_size_m
    x -= x.mean()
    y -= y.mean()
    zc = values - values.mean()
    sxx, syy, sxy = float(x @ x), float(y @ y), float(x @ y)
    det = sxx * syy - sxy * sxy
    if det <= 1e-12 * max(sxx * syy, 1e-300):
        return None  # valid pixels are collinear: no unique plane
    sxz, syz = float(x @ zc), float(y @ zc)
    a = (syy * sxz - sxy * syz) / det
    b = (sxx * syz - sxy * sxz) / det
    resid = zc - a * x - b * y
    return float(np.sqrt(np.mean(resid * resid)))


def valid_fraction(dem: FloatArray, mask: BoolArray | None = None) -> float:
    m = _effective_mask(dem, mask)
    return float(m.mean()) if m.size else 0.0


# ---------------------------------------------------------------- profile


@dataclass
class TerrainProfile:
    values: dict[str, Any]
    availability: dict[str, bool]
    pixel_size_m: float
    schema_version: str = FEATURE_SCHEMA_VERSION
    meta: dict[str, Any] = field(default_factory=dict)


def compute_profile(
    dem: FloatArray,
    pixel_size_m: float,
    mask: BoolArray | None = None,
    *,
    bins_deg: Sequence[float],
) -> TerrainProfile:
    """All terrain-v1 features for one window. Availability matches ``None`` exactly."""
    slope = horn_slope_deg(dem, pixel_size_m, mask)
    s = _valid_slopes(slope)
    if s.size:
        counts, _ = np.histogram(s, bins=np.asarray(bins_deg, dtype=float))
        hist: list[float] | None = [float(c) / float(s.size) for c in counts]
        med: float | None = float(np.median(s))
        p90: float | None = float(np.percentile(s, 90))
    else:
        hist, med, p90 = None, None, None
    values: dict[str, Any] = {
        "slope_median": med,
        "slope_p90": p90,
        "slope_hist": hist,
        "relief": relief(dem, pixel_size_m, mask),
        "roughness": roughness(dem, pixel_size_m, mask),
        "valid_fraction": valid_fraction(dem, mask),
    }
    availability = {k: v is not None for k, v in values.items()}
    return TerrainProfile(
        values=values,
        availability=availability,
        pixel_size_m=pixel_size_m,
        meta={
            "slope_method": "horn_1981",
            "roughness_scale_m": float(max(dem.shape) * pixel_size_m),
            "slope_hist_bins_deg": list(bins_deg),
        },
    )
