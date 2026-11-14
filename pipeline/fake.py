"""`pipeline seed-fake`: synthetic features so the API and map work before real data.

Every output is marked ``data_status = "synthetic"`` and the UI shows that.
Terrain is generated as fractal noise per window and then measured with the
real feature code, so values are internally consistent (the histogram matches
the slopes). Land cover fractions are invented. Nothing here is a measurement.
No registry entries are invented.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from core.artifacts import Artifacts, TargetProfileRecord
from core.bodies import get_body, laea_proj
from core.config import GridConfig, ScoringConfig, TargetConfig
from core.features import compute_profile
from core.grid import iter_windows
from core.raster import hillshade
from pipeline.common import feature_row, finish, new_run, rows_to_frame


def fractal_dem(n: int, rng: np.random.Generator, beta: float = 3.2) -> NDArray[np.float64]:
    """Unit-std fractal surface (power spectrum ~ 1/f^beta)."""
    noise = rng.normal(size=(n, n))
    f = np.fft.fft2(noise)
    ky = np.fft.fftfreq(n)[:, None]
    kx = np.fft.fftfreq(n)[None, :]
    k = np.hypot(kx, ky)
    k[0, 0] = 1.0
    field = np.real(np.fft.ifft2(f / k ** (beta / 2)))
    field -= field.mean()
    sd = field.std()
    return field / sd if sd > 0 else field


def _ruggedness(ix: int, iy: int, seed: int) -> float:
    """Smooth 0..1 field over window indices so neighbouring windows look alike."""
    rng = np.random.default_rng(seed)
    total = 0.0
    for _ in range(5):
        kx, ky = rng.uniform(0.01, 0.08, 2)
        ph = rng.uniform(0, 2 * math.pi)
        total += math.sin(kx * ix + ky * iy + ph)
    return float(np.clip(0.5 + total / 6, 0, 1))


def synthetic_window_dem(
    cell_id: int, ix: int, iy: int, n: int, pixel_m: float, seed: int
) -> tuple[NDArray[np.float64], float]:
    r = _ruggedness(ix, iy, seed)
    rng = np.random.default_rng(cell_id)
    amp = 3 + 260 * r**2
    yy, xx = np.mgrid[0:n, 0:n] * pixel_m
    tilt = math.tan(math.radians(rng.uniform(0, 1.5 + 3 * r)))
    az = rng.uniform(0, 2 * math.pi)
    m = 1 << (n - 1).bit_length()  # FFT-friendly size, then crop (167 is prime)
    dem = 500 + amp * fractal_dem(m, rng)[:n, :n] + tilt * (xx * math.cos(az) + yy * math.sin(az))
    return dem, r


def seed_region(
    artifacts: Artifacts,
    grid: GridConfig,
    scoring: ScoringConfig,
    region_id: str,
    scale_m: int,
    *,
    seed: int = 7,
    max_windows: int | None = None,
) -> dict[str, Any]:
    region = grid.region(region_id)
    run = new_run(
        "seed_fake",
        data_status="synthetic",
        scoring=scoring,
        grid=grid,
        region_id=region_id,
        scale_m=scale_m,
        inputs={"seed": seed, "generator": "fractal_dem beta=3.2", "max_windows": max_windows},
    )
    n = round(grid.window_m / scale_m)
    rows = []
    windows = list(iter_windows(grid, region_id))
    if max_windows is not None:
        windows = windows[:max_windows]
    for w in windows:
        dem, r = synthetic_window_dem(w.cell_id, w.ix, w.iy, n, float(scale_m), seed)
        rng = np.random.default_rng(w.cell_id + 1)
        mask = np.ones(dem.shape, dtype=bool)
        if rng.random() < 0.04:  # a few windows with data gaps
            mask[: int(n * rng.uniform(0.1, 0.4)), :] = False
        prof = compute_profile(dem, float(scale_m), mask, bins_deg=scoring.slope_hist_bins_deg)
        lc: dict[str, float | None] = {
            "water_fraction": float(rng.uniform(0.06, 0.4))
            if rng.random() < 0.03
            else float(rng.uniform(0, 0.01)),
            "built_up_fraction": float(rng.uniform(0.03, 0.2)) if rng.random() < 0.02 else 0.0,
            "snow_ice_fraction": float(rng.uniform(0, 0.3))
            if r > 0.85 and rng.random() < 0.3
            else 0.0,
            "vegetation_fraction": float(rng.uniform(0, 0.15) * (1 - r)),
        }
        rows.append(feature_row(w, region, scale_m, prof, lc, run.id))
    df = rows_to_frame(rows, scoring)
    finish(run, windows=len(df))
    sha = artifacts.write_features(df, region_id, scale_m, run)
    return {"run_id": run.id, "windows": len(df), "sha256": sha}


SYNTHETIC_TARGET_AMPLITUDE_M = {"mars": 90.0, "moon": 420.0}


def seed_target(
    artifacts: Artifacts,
    grid: GridConfig,
    scoring: ScoringConfig,
    target: TargetConfig,
    *,
    seed: int = 11,
) -> dict[str, Any]:
    scale = target.comparison.scale_m
    run = new_run(
        "seed_fake",
        data_status="synthetic",
        scoring=scoring,
        grid=grid,
        target_id=target.id,
        scale_m=scale,
        inputs={"seed": seed, "generator": "fractal_dem beta=3.2"},
    )
    n = round(target.comparison.footprint_m / scale)
    rng = np.random.default_rng(seed + sum(map(ord, target.id)))
    amp = SYNTHETIC_TARGET_AMPLITUDE_M[target.body.value]
    dem = 0.0 + amp * fractal_dem(n, rng)
    prof = compute_profile(dem, float(scale), bins_deg=scoring.slope_hist_bins_deg)
    body = get_body(target.body)
    half = target.comparison.footprint_m / 2
    rec = TargetProfileRecord(
        target_id=target.id,
        body=target.body.value,
        name=target.name,
        scale_m=scale,
        footprint_m=target.comparison.footprint_m,
        center_lat=target.comparison.center_lat,
        center_lon=target.comparison.center_lon,
        values=prof.values,
        availability=prof.availability,
        meta=prof.meta,
        run_id=run.id,
        schema_version=prof.schema_version,
        data_status="synthetic",
        crs=laea_proj(body, target.comparison.center_lat, target.comparison.center_lon),
        footprint_wkt=f"POLYGON(({-half} {-half}, {half} {-half}, {half} {half}, {-half} {half}, {-half} {-half}))",
    )
    preview = artifacts.target_preview_path(target.id)
    preview.parent.mkdir(parents=True, exist_ok=True)
    img = (
        Image.fromarray(hillshade(dem, float(scale)))
        .convert("RGB")
        .resize((512, 512), Image.Resampling.NEAREST)
    )
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 512, 22), fill=(0, 0, 0))
    draw.text((6, 5), "SYNTHETIC TERRAIN - NOT A REAL DEM", fill=(255, 200, 0))
    img.save(preview)
    rec.preview_path = str(preview.relative_to(artifacts.root).as_posix())
    finish(run, footprint_px=n)
    artifacts.write_run(run)
    artifacts.write_target_profile(rec)
    return {"run_id": run.id, "values": prof.values}
