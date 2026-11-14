"""`pipeline run` and `pipeline target`: real features from real DEMs.

Earth: one parquet per region and scale (the search index) plus a run record.
Target: one profile per target at its own scale plus a hillshade preview.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from PIL import Image

from core.artifacts import Artifacts, TargetProfileRecord
from core.bodies import get_body, laea_proj
from core.config import GridConfig, ScoringConfig, TargetConfig
from core.features import compute_profile
from core.grid import iter_windows
from core.raster import hillshade
from pipeline.adapters.sources import copernicus_assets, planetary_asset, worldcover_assets
from pipeline.common import feature_row, finish, new_run, rows_to_frame
from pipeline.preprocess import (
    warp_earth_dem,
    warp_planetary,
    window_landcover,
    worldcover_block_fractions,
)

Progress = Callable[[str], None]


def run_region(
    artifacts: Artifacts,
    grid: GridConfig,
    scoring: ScoringConfig,
    region_id: str,
    scale_m: int,
    *,
    use_stac: bool = True,
    progress: Progress = print,
) -> dict[str, Any]:
    region = grid.region(region_id)
    if scale_m not in region.scales_m:
        raise ValueError(f"{region_id} is configured for scales {region.scales_m}, not {scale_m}")
    if grid.window_m % grid.stride_m:
        raise ValueError("window_m must be a whole number of strides for block land-cover counts")
    k = grid.window_m // grid.stride_m
    run = new_run(
        "earth_features",
        data_status="measured",
        scoring=scoring,
        grid=grid,
        region_id=region_id,
        scale_m=scale_m,
    )
    artifacts.write_run(run)
    try:
        windows = list(iter_windows(grid, region_id))
        progress(f"{region_id}: {len(windows)} windows at {scale_m} m")
        dem_assets = copernicus_assets(region.bbox, use_stac=use_stac)
        progress(f"  {len(dem_assets)} Copernicus tiles")
        dem, dem_grid, dem_present = warp_earth_dem(
            region, float(scale_m), dem_assets, progress=progress
        )

        blocks = sorted(
            {(w.ix + dx, w.iy + dy) for w in windows for dx in range(k) for dy in range(k)}
        )
        wc_assets = worldcover_assets(region.bbox)
        counts, wc_present = worldcover_block_fractions(
            region, grid, scoring, wc_assets, blocks, progress
        )

        rows = []
        for w in windows:
            rs, cs = dem_grid.window_slices(w.x0, w.y0, w.x1, w.y1)
            sub = dem[rs, cs]
            prof = compute_profile(sub, float(scale_m), bins_deg=scoring.slope_hist_bins_deg)
            rows.append(
                feature_row(
                    w, region, scale_m, prof, window_landcover(counts, w.ix, w.iy, k), run.id
                )
            )
        df = rows_to_frame(rows, scoring)
        assets = [*dem_present, *wc_present]
        run.source_asset_ids = [a.asset_id for a in assets]
        run.inputs.update(
            {
                "assets": [a.to_dict() for a in assets],
                "missing_assets": [
                    a.asset_id for a in [*dem_assets, *wc_assets] if a.access_meta.get("missing")
                ],
                "resampling": "area-weighted average onto LAEA grid (core.raster.warp_to_grid)",
                "landcover": "native 10 m pixel counts per stride block",
            }
        )
        finish(run, windows=len(df), grid_shape=[dem_grid.height, dem_grid.width])
        sha = artifacts.write_features(df, region_id, scale_m, run)
        progress(f"  wrote {len(df)} rows, sha256 {sha[:12]}")
        return {"run_id": run.id, "windows": len(df), "sha256": sha}
    except Exception as exc:
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        artifacts.write_run(run)
        raise


def run_target(
    artifacts: Artifacts,
    grid: GridConfig,
    scoring: ScoringConfig,
    target: TargetConfig,
    *,
    progress: Progress = print,
) -> dict[str, Any]:
    body = get_body(target.body)
    scale = target.comparison.scale_m
    run = new_run(
        "target_profile",
        data_status="measured",
        scoring=scoring,
        grid=grid,
        target_id=target.id,
        scale_m=scale,
    )
    artifacts.write_run(run)
    try:
        asset = planetary_asset(body.name.value)
        c = target.comparison
        laea = laea_proj(body, c.center_lat, c.center_lon)
        half = c.footprint_m / 2
        # Scored square: only pixels whose centres are inside the 10 km footprint.
        dem, g, info = warp_planetary(
            body,
            asset,
            laea,
            (-half, -half, half, half),
            float(scale),
            (c.center_lat - 1, c.center_lat + 1),
        )
        rs, cs = g.window_slices(-half, -half, half, half)
        prof = compute_profile(dem[rs, cs], float(scale), bins_deg=scoring.slope_hist_bins_deg)
        progress(f"{target.id}: profile {prof.values}")

        # Preview: hillshade of the wider bbox; it is not scored.
        pb = target.preview.bbox
        from pyproj import Transformer

        from core.bodies import geographic_proj

        t = Transformer.from_crs(geographic_proj(body), laea, always_xy=True)
        xs, ys = t.transform(
            [pb.west, pb.east, pb.east, pb.west], [pb.south, pb.south, pb.north, pb.north]
        )
        pdem, _, _ = warp_planetary(
            body,
            asset,
            laea,
            (min(xs), min(ys), max(xs), max(ys)),
            float(scale),
            (pb.south, pb.north),
        )
        preview = artifacts.target_preview_path(target.id)
        preview.parent.mkdir(parents=True, exist_ok=True)
        hs = hillshade(np.nan_to_num(pdem, nan=float(np.nanmean(pdem))), float(scale))
        Image.fromarray(hs).save(preview)

        rec = TargetProfileRecord(
            target_id=target.id,
            body=body.name.value,
            name=target.name,
            scale_m=scale,
            footprint_m=c.footprint_m,
            center_lat=c.center_lat,
            center_lon=c.center_lon,
            values=prof.values,
            availability=prof.availability,
            meta={
                **prof.meta,
                **info,
                "pixels": [int(rs.stop - rs.start), int(cs.stop - cs.start)],
            },
            run_id=run.id,
            schema_version=prof.schema_version,
            data_status="measured",
            crs=laea,
            footprint_wkt=f"POLYGON(({-half} {-half}, {half} {-half}, {half} {half}, {-half} {half}, {-half} {-half}))",
            preview_path=str(preview.relative_to(artifacts.root).as_posix()),
            source_asset_ids=[asset.asset_id],
        )
        run.source_asset_ids = [asset.asset_id]
        run.inputs["assets"] = [asset.to_dict()]
        finish(run)
        artifacts.write_run(run)
        artifacts.write_target_profile(rec)
        return {"run_id": run.id, "values": prof.values}
    except Exception as exc:
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        artifacts.write_run(run)
        raise
