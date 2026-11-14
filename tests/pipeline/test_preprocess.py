"""Real rasterio warps on small synthetic GeoTIFFs (no network)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

import pipeline.preprocess as pre
from core.bodies import (
    EARTH,
    MARS,
    MOON,
    geographic_proj,
    ground_pixel_size_m,
    laea_proj,
    metres_per_degree,
)
from core.config import load_grid, load_scoring
from core.features import slope_median
from core.raster import UpsamplingError
from pipeline.adapters.base import AssetRef


@pytest.fixture(autouse=True)
def _local_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests read local files; production reads allowlisted https via /vsicurl/.
    monkeypatch.setattr(pre, "vsicurl", lambda url: url)


def _write_geotiff(
    path: Path,
    arr: np.ndarray,
    west: float,
    north: float,
    res: float,
    crs: str,
    nodata: float | int | None = None,
) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=arr.shape[1],
        height=arr.shape[0],
        count=1,
        dtype=arr.dtype,
        crs=crs,
        transform=from_origin(west, north, res, res),
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)


def _plane_geographic(
    body, lat_c: float, lon_c: float, half_deg: float, res: float, angle: float
) -> tuple[np.ndarray, float, float]:
    n = round(2 * half_deg / res)
    west, north = lon_c - half_deg, lat_c + half_deg
    lats = north - (np.arange(n) + 0.5) * res
    _, m_lat = metres_per_degree(body, 0)
    # Plane rising northward: z = tan(angle) * north-distance in metres on this body.
    z = math.tan(math.radians(angle)) * (lats - lat_c) * m_lat
    return np.repeat(z[:, None], n, axis=1).astype(np.float32), west, north


def test_earth_tile_warp_preserves_slope(tmp_path: Path):
    grid_cfg = load_grid()
    region = grid_cfg.region("earth_atacama")
    arr, west, north = _plane_geographic(EARTH, -22.0, -68.0, 0.15, 1 / 3600, 6.0)
    tif = tmp_path / "dem.tif"
    _write_geotiff(tif, arr, west, north, 1 / 3600, "EPSG:4326", nodata=-32767.0)
    asset = AssetRef("copernicus_glo30", "copernicus", "earth", "dem.tif", str(tif), 30, "test")
    # Warp only a small area around the LAEA origin.
    small = region.model_copy(
        update={
            "bbox": region.bbox.model_copy(
                update={"west": -68.1, "east": -67.9, "south": -22.1, "north": -21.9}
            )
        }
    )
    dem, g, present = pre.warp_earth_dem(small, 200.0, [asset])
    assert present == [asset]
    assert g.x0 % 200 == 0 and g.y1 % 200 == 0
    rs, cs = g.window_slices(-5000, -5000, 5000, 5000)
    sub = dem[rs, cs]
    assert np.isfinite(sub).all()
    # Ellipsoid vs sphere and LAEA scale add a few hundredths of a degree at most.
    assert slope_median(sub, 200.0) == pytest.approx(6.0, abs=0.1)


@pytest.mark.parametrize(("body", "scale"), [(MARS, 200.0), (MOON, 60.0)], ids=["mars", "moon"])
def test_planetary_warp_on_body_sphere(tmp_path: Path, body, scale):
    res = 1 / 512 if body is MARS else 1 / 2048  # finer than the comparison grid on both axes
    arr, west, north = _plane_geographic(body, 18.4, 77.45, 0.3 if body is MARS else 0.12, res, 9.0)
    tif = tmp_path / f"{body.name}.tif"
    _write_geotiff(tif, arr, west, north, res, geographic_proj(body), nodata=-99999.0)
    asset = AssetRef("p", "p", body.name.value, tif.name, str(tif), scale, "test")
    laea = laea_proj(body, 18.4, 77.45)
    dem, g, _ = pre.warp_planetary(
        body, asset, laea, (-5000, -5000, 5000, 5000), scale, (18.0, 18.8)
    )
    rs, cs = g.window_slices(-5000, -5000, 5000, 5000)
    assert slope_median(dem[rs, cs], scale) == pytest.approx(9.0, abs=0.1)


def test_planetary_warp_refuses_upsampling(tmp_path: Path):
    res = 1 / 128  # ~463 m on Mars: coarser than a 200 m grid
    arr, west, north = _plane_geographic(MARS, 18.4, 77.45, 0.5, res, 5.0)
    tif = tmp_path / "coarse.tif"
    _write_geotiff(tif, arr, west, north, res, geographic_proj(MARS))
    asset = AssetRef("p", "p", "mars", tif.name, str(tif), 463, "test")
    with pytest.raises(UpsamplingError):
        pre.warp_planetary(
            MARS, asset, laea_proj(MARS, 18.4, 77.45), (-5000, -5000, 5000, 5000), 200.0, (18, 19)
        )


def test_projected_product_on_wrong_radius_is_rejected(tmp_path: Path):
    arr = np.zeros((100, 100), dtype=np.float32)
    tif = tmp_path / "eqc_moon.tif"
    _write_geotiff(tif, arr, 0, 10000, 100, "+proj=eqc +R=1737400 +units=m +no_defs")
    asset = AssetRef("p", "p", "mars", tif.name, str(tif), 100, "test")
    with pytest.raises(RuntimeError, match="radius"):
        pre.warp_planetary(
            MARS, asset, laea_proj(MARS, 0, 0), (-1000, -1000, 1000, 1000), 200.0, (-1, 1)
        )


def test_worldcover_counts_native_pixels_per_block(tmp_path: Path):
    grid_cfg = load_grid()
    scoring = load_scoring()
    region = grid_cfg.region("earth_atacama")
    res = 1 / 12000  # WorldCover posting
    west, north = -68.0, -21.9
    n_x, n_y = 1200, 1200  # 0.1° x 0.1°
    lons = west + (np.arange(n_x) + 0.5) * res
    classes = np.where(lons < -67.976, 80, 60).astype(np.uint8)  # water west of -67.976
    arr = np.repeat(classes[None, :], n_y, axis=0)
    tif = tmp_path / "wc.tif"
    _write_geotiff(tif, arr, west, north, res, "EPSG:4326", nodata=0)
    asset = AssetRef("esa_worldcover_2021", "esa", "earth", tif.name, str(tif), 10, "test")
    counts, _ = pre.worldcover_block_fractions(region, grid_cfg, scoring, [asset], [(0, 0)])
    c = counts[(0, 0)]
    # Block (0,0) spans ~5 km east of -68°; at 22°S, 5 km ≈ 0.0485°. Water covers -68.0 .. -67.976.
    expected = 0.024 / (5000 / metres_per_degree(EARTH, -22)[0])
    assert c["water"] / (c["total"] - c["nodata"]) == pytest.approx(expected, abs=0.01)
    dx, dy = ground_pixel_size_m(EARTH, -22, res, res)
    assert c["total"] == pytest.approx(
        5000 * 5000 / (dx * dy), rel=0.02
    )  # every native pixel, counted once
    lc = pre.window_landcover({(0, 0): c, (1, 0): c, (0, 1): c, (1, 1): c}, 0, 0, 2)
    assert lc["water_fraction"] == pytest.approx(c["water"] / (c["total"] - c["nodata"]))
    assert (
        pre.window_landcover({(0, 0): c}, 0, 0, 2)["water_fraction"] is None
    )  # missing block -> unknown
