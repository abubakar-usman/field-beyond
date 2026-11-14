"""Body-aware preprocessing.

Earth: Copernicus tiles (geographic, ~30 m) -> area-weighted average onto the
region's LAEA comparison grid (200 m or 60 m). WorldCover is counted at native
10 m per stride block, so a window's fraction is the sum of its blocks.

Planetary: the product is read around the target and averaged onto a local
LAEA on the body's own sphere. Every warp goes through core.raster.warp_to_grid,
which refuses to upsample.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from core.bodies import EARTH, Body, geographic_proj
from core.config import GridConfig, Region, ScoringConfig
from core.grid import region_laea_polygon
from core.raster import AlignedGrid, aligned_grid, build_mosaic_vrt, warp_to_grid
from pipeline.adapters.base import AssetRef, gdal_env, vsicurl

Progress = Callable[[str], None]


def _noop(_: str) -> None:
    return None


def open_mosaic(
    assets: Sequence[AssetRef], progress: Progress = _noop
) -> tuple[str, list[AssetRef]]:
    """VRT XML over the assets that exist. Missing tiles (ocean, unpublished) are skipped and reported."""
    import rasterio
    from rasterio.errors import RasterioIOError

    sources, present = [], []
    for a in assets:
        try:
            with rasterio.open(vsicurl(a.url)) as ds:
                t = ds.transform
                sources.append(
                    {
                        "path": vsicurl(a.url),
                        "width": ds.width,
                        "height": ds.height,
                        "transform": (t.a, t.b, t.c, t.d, t.e, t.f),
                        "crs_wkt": ds.crs.to_wkt(),
                        "nodata": ds.nodata,
                        "dtype": ds.dtypes[0],
                    }
                )
                a.access_meta.update(
                    {"width": ds.width, "height": ds.height, "crs": ds.crs.to_string()}
                )
                present.append(a)
        except RasterioIOError:
            progress(f"  missing tile (skipped): {a.key}")
            a.access_meta["missing"] = True
    if not sources:
        raise RuntimeError("no source tiles could be opened")
    # Copernicus tiles above 50° change longitude spacing; mosaicking assumes one resolution.
    return build_mosaic_vrt(sources), present


def region_grid(region: Region, pixel_m: float) -> AlignedGrid:
    return aligned_grid(region.laea.proj, region_laea_polygon(region).bounds, pixel_m)


def warp_earth_dem(
    region: Region,
    pixel_m: float,
    dem_assets: Sequence[AssetRef],
    chunk_px: int = 2048,
    progress: Progress = _noop,
) -> tuple[NDArray[np.float32], AlignedGrid, list[AssetRef]]:
    """Copernicus mosaic averaged onto the region LAEA grid, chunk by chunk."""
    import rasterio

    grid = region_grid(region, pixel_m)
    out = np.full((grid.height, grid.width), np.nan, dtype=np.float32)
    lat_range = (region.bbox.south, region.bbox.north)
    with gdal_env():
        vrt, present = open_mosaic(dem_assets, progress)
        with rasterio.open(vrt) as src:
            for r0 in range(0, grid.height, chunk_px):
                for c0 in range(0, grid.width, chunk_px):
                    h = min(chunk_px, grid.height - r0)
                    w = min(chunk_px, grid.width - c0)
                    sub = AlignedGrid(
                        grid.crs, grid.pixel_m, grid.x0 + c0 * pixel_m, grid.y1 - r0 * pixel_m, w, h
                    )
                    out[r0 : r0 + h, c0 : c0 + w] = warp_to_grid(
                        src, body=EARTH, grid=sub, lat_range=lat_range
                    )
                    progress(f"  warped rows {r0}-{r0 + h} cols {c0}-{c0 + w}")
    return out, grid, present


def worldcover_block_fractions(
    region: Region,
    grid_cfg: GridConfig,
    scoring: ScoringConfig,
    wc_assets: Sequence[AssetRef],
    block_ids: Sequence[tuple[int, int]],
    progress: Progress = _noop,
) -> tuple[dict[tuple[int, int], dict[str, int]], list[AssetRef]]:
    """Native-10 m class counts per stride block (bx, by) in the region LAEA.

    A pixel counts toward a block when its centre, projected into the LAEA,
    falls inside the block square. No resampling of land cover happens.
    """
    import rasterio
    from pyproj import Transformer
    from rasterio.windows import Window as RioWindow
    from rasterio.windows import from_bounds

    wc = scoring.worldcover
    groups = {
        "water": set(wc.water_classes),
        "built_up": set(wc.built_up_classes),
        "snow_ice": set(wc.snow_ice_classes),
        "vegetation": set(wc.vegetation_classes),
    }
    stride = float(grid_cfg.stride_m)
    inv = Transformer.from_crs(region.laea.proj, "EPSG:4326", always_xy=True)
    fwd = Transformer.from_crs("EPSG:4326", region.laea.proj, always_xy=True)
    counts: dict[tuple[int, int], dict[str, int]] = {}
    with gdal_env():
        vrt, present = open_mosaic(wc_assets, progress)
        with rasterio.open(vrt) as src:
            for n, (bx, by) in enumerate(block_ids):
                x0, y0 = bx * stride, by * stride
                xs = np.array([x0, x0 + stride, x0 + stride, x0])
                ys = np.array([y0, y0, y0 + stride, y0 + stride])
                lons, lats = inv.transform(xs, ys)
                fw = from_bounds(min(lons), min(lats), max(lons), max(lats), src.transform)
                c0, r0 = math.floor(fw.col_off), math.floor(fw.row_off)
                win = RioWindow(
                    c0,
                    r0,
                    math.ceil(fw.col_off + fw.width) - c0,
                    math.ceil(fw.row_off + fw.height) - r0,
                )
                arr = src.read(1, window=win, boundless=True, fill_value=0)
                t = src.window_transform(win)
                rows, cols = np.indices(arr.shape)
                plon = t.c + (cols + 0.5) * t.a
                plat = t.f + (rows + 0.5) * t.e
                px, py = fwd.transform(plon.ravel(), plat.ravel())
                inside = (px >= x0) & (px < x0 + stride) & (py >= y0) & (py < y0 + stride)
                vals = arr.ravel()[inside]
                c = {"total": int(inside.sum()), "nodata": int((vals == 0).sum())}
                for g, classes in groups.items():
                    c[g] = int(np.isin(vals, list(classes)).sum())
                counts[(bx, by)] = c
                if n % 500 == 0:
                    progress(f"  worldcover blocks {n}/{len(block_ids)}")
    return counts, present


def window_landcover(
    counts: dict[tuple[int, int], dict[str, int]], ix: int, iy: int, k: int
) -> dict[str, float | None]:
    """Fractions for a window made of k×k stride blocks. None when any block has no valid pixels."""
    tot: dict[str, int] = {
        "total": 0,
        "nodata": 0,
        "water": 0,
        "built_up": 0,
        "snow_ice": 0,
        "vegetation": 0,
    }
    for dy in range(k):
        for dx in range(k):
            c = counts.get((ix + dx, iy + dy))
            if c is None:
                return dict.fromkeys(
                    (
                        "water_fraction",
                        "built_up_fraction",
                        "snow_ice_fraction",
                        "vegetation_fraction",
                    )
                )
            for key in tot:
                tot[key] += c[key]
    valid = tot["total"] - tot["nodata"]
    if valid <= 0:
        return dict.fromkeys(
            ("water_fraction", "built_up_fraction", "snow_ice_fraction", "vegetation_fraction")
        )
    return {
        "water_fraction": tot["water"] / valid,
        "built_up_fraction": tot["built_up"] / valid,
        "snow_ice_fraction": tot["snow_ice"] / valid,
        "vegetation_fraction": tot["vegetation"] / valid,
    }


def warp_planetary(
    body: Body,
    asset: AssetRef,
    laea: str,
    bounds: tuple[float, float, float, float],
    pixel_m: float,
    lat_range: tuple[float, float],
) -> tuple[NDArray[np.float32], AlignedGrid, dict[str, Any]]:
    """Read the planetary product around a target and average it onto a body-sphere LAEA.

    The product's geographic CRS is pinned to the body's IAU sphere so PROJ
    never routes the transform through an Earth datum. A projected product
    must already be on a sphere of the body's radius.
    """
    import rasterio
    from rasterio.crs import CRS as RIO_CRS

    grid = aligned_grid(laea, bounds, pixel_m)
    with gdal_env(), rasterio.open(vsicurl(asset.url)) as src:
        crs = src.crs
        info: dict[str, Any] = {"product_crs": crs.to_string() if crs else None}
        if crs is None or crs.is_geographic:
            src_crs = RIO_CRS.from_string(geographic_proj(body))
        else:
            from pyproj import CRS

            ell = CRS.from_user_input(crs.to_wkt()).ellipsoid
            if ell is None or not math.isclose(ell.semi_major_metre, body.radius_m, rel_tol=1e-4):
                raise RuntimeError(
                    f"{asset.key} is projected on radius {getattr(ell, 'semi_major_metre', None)}, "
                    f"expected {body.name} radius {body.radius_m}"
                )
            src_crs = crs
        arr = warp_to_grid(src, body=body, grid=grid, src_crs=src_crs, lat_range=lat_range)
        info["product_res"] = (abs(src.transform.a), abs(src.transform.e))
    return arr, grid, info
