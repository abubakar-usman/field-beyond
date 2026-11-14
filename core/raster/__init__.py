"""Raster helpers: aligned comparison grids, the no-upsampling guard, warping, hillshade.

Every resampling call in this project goes through :func:`warp_to_grid`, which
calls :func:`assert_not_upsampling` first (CLAUDE.md rule 2, decision D-023).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

import numpy as np
from numpy.typing import NDArray

from core.bodies import Body, ground_pixel_size_m


class UpsamplingError(AssertionError):
    """Raised when an output pixel would be finer than the source ground pixel."""


def assert_not_upsampling(
    src_pixel_m: tuple[float, float], dst_pixel_m: tuple[float, float], *, rel_tol: float = 1e-9
) -> None:
    """Both output axes must be coarser than or equal to the source ground pixel."""
    for axis, s, d in zip("xy", src_pixel_m, dst_pixel_m, strict=True):
        if s <= 0 or d <= 0:
            raise ValueError(
                f"pixel sizes must be positive, got src={src_pixel_m} dst={dst_pixel_m}"
            )
        if d < s * (1 - rel_tol):
            raise UpsamplingError(
                f"{axis}-axis output pixel {d:.3f} m is finer than source ground pixel {s:.3f} m; "
                "aggregate down to a coarser grid instead"
            )


@dataclass(frozen=True)
class AlignedGrid:
    """A north-up grid whose pixel edges are multiples of ``pixel_m`` from the CRS origin."""

    crs: str
    pixel_m: float
    x0: float  # west edge
    y1: float  # north edge
    width: int
    height: int

    @property
    def x1(self) -> float:
        return self.x0 + self.width * self.pixel_m

    @property
    def y0(self) -> float:
        return self.y1 - self.height * self.pixel_m

    def transform(self) -> Any:
        from rasterio.transform import from_origin

        return from_origin(self.x0, self.y1, self.pixel_m, self.pixel_m)

    def window_slices(self, x0: float, y0: float, x1: float, y1: float) -> tuple[slice, slice]:
        """Row and column slices of the pixels whose centres fall inside a box."""
        p = self.pixel_m
        c0 = math.ceil((x0 - self.x0) / p - 0.5)
        c1 = math.floor((x1 - self.x0) / p - 0.5)
        r0 = math.ceil((self.y1 - y1) / p - 0.5)
        r1 = math.floor((self.y1 - y0) / p - 0.5)
        c0, r0 = max(c0, 0), max(r0, 0)
        c1, r1 = min(c1, self.width - 1), min(r1, self.height - 1)
        return slice(r0, r1 + 1), slice(c0, c1 + 1)


def aligned_grid(
    crs: str, bounds: tuple[float, float, float, float], pixel_m: float
) -> AlignedGrid:
    """Snap ``(xmin, ymin, xmax, ymax)`` outward to multiples of ``pixel_m``."""
    xmin, ymin, xmax, ymax = bounds
    gx0 = math.floor(xmin / pixel_m) * pixel_m
    gy0 = math.floor(ymin / pixel_m) * pixel_m
    gx1 = math.ceil(xmax / pixel_m) * pixel_m
    gy1 = math.ceil(ymax / pixel_m) * pixel_m
    return AlignedGrid(
        crs=crs,
        pixel_m=pixel_m,
        x0=gx0,
        y1=gy1,
        width=round((gx1 - gx0) / pixel_m),
        height=round((gy1 - gy0) / pixel_m),
    )


def source_ground_pixel_m(
    *,
    body: Body,
    is_geographic: bool,
    res: tuple[float, float],
    lat_range: tuple[float, float],
) -> tuple[float, float]:
    """Largest ground size (x, y) of a source pixel over a latitude range.

    For geographic sources the x size shrinks with cos(latitude); the largest
    value (nearest the equator) is the conservative one for the upsampling check.
    Projected sources are assumed to be in metres on the body already.
    """
    if not is_geographic:
        return abs(res[0]), abs(res[1])
    lo, hi = sorted(lat_range)
    nearest_equator = 0.0 if lo <= 0 <= hi else min(abs(lo), abs(hi))
    return ground_pixel_size_m(body, nearest_equator, res[0], res[1])


def build_mosaic_vrt(sources: Sequence[dict[str, Any]]) -> str:
    """VRT XML mosaicking same-resolution, same-CRS tiles.

    Each source dict has ``path``, ``width``, ``height``, ``transform`` (affine
    tuple a,b,c,d,e,f), ``crs_wkt``, ``nodata`` and ``dtype``.
    """
    if not sources:
        raise ValueError("no sources to mosaic")
    a = sources[0]["transform"]
    px, py = a[0], a[4]
    for s in sources:
        t = s["transform"]
        if not (math.isclose(t[0], px, rel_tol=1e-9) and math.isclose(t[4], py, rel_tol=1e-9)):
            raise ValueError("mosaic sources must share a resolution")
    west = min(s["transform"][2] for s in sources)
    north = max(s["transform"][5] for s in sources)
    east = max(s["transform"][2] + s["width"] * px for s in sources)
    south = min(s["transform"][5] + s["height"] * py for s in sources)
    width = round((east - west) / px)
    height = round((south - north) / py)
    nodata = sources[0].get("nodata")
    dtype = {"float32": "Float32", "float64": "Float64", "int16": "Int16", "uint8": "Byte"}[
        str(sources[0]["dtype"])
    ]
    parts = [
        f'<VRTDataset rasterXSize="{width}" rasterYSize="{height}">',
        f"<SRS>{escape(sources[0]['crs_wkt'])}</SRS>",
        f"<GeoTransform>{west!r}, {px!r}, 0, {north!r}, 0, {py!r}</GeoTransform>",
        f'<VRTRasterBand dataType="{dtype}" band="1">',
    ]
    if nodata is not None:
        parts.append(f"<NoDataValue>{nodata!r}</NoDataValue>")
    for s in sources:
        t = s["transform"]
        xoff = round((t[2] - west) / px)
        yoff = round((t[5] - north) / py)
        parts.append(
            "<ComplexSource>"
            f'<SourceFilename relativeToVRT="0">{escape(s["path"])}</SourceFilename>'
            "<SourceBand>1</SourceBand>"
            f'<SrcRect xOff="0" yOff="0" xSize="{s["width"]}" ySize="{s["height"]}"/>'
            f'<DstRect xOff="{xoff}" yOff="{yoff}" xSize="{s["width"]}" ySize="{s["height"]}"/>'
            + (f"<NODATA>{nodata!r}</NODATA>" if nodata is not None else "")
            + "</ComplexSource>"
        )
    parts.append("</VRTRasterBand></VRTDataset>")
    return "".join(parts)


def warp_to_grid(
    src: Any,
    *,
    body: Body,
    grid: AlignedGrid,
    src_crs: Any = None,
    lat_range: tuple[float, float],
) -> NDArray[np.float32]:
    """Area-weighted average of an open rasterio dataset onto an aligned grid.

    Refuses to run if the grid would upsample the source. Nodata becomes NaN.
    ``src_crs`` overrides the dataset's CRS; planetary products are pinned to
    the body's sphere this way so PROJ never routes them through an Earth datum.
    """
    from rasterio.warp import Resampling, reproject, transform_bounds
    from rasterio.windows import Window as RioWindow

    crs = src_crs if src_crs is not None else src.crs
    res = (abs(src.transform.a), abs(src.transform.e))
    src_px = source_ground_pixel_m(
        body=body, is_geographic=bool(crs.is_geographic), res=res, lat_range=lat_range
    )
    assert_not_upsampling(src_px, (grid.pixel_m, grid.pixel_m))

    # Read only the source pixels under the grid (plus a margin), then warp that array.
    left, bottom, right, top = transform_bounds(
        grid.crs, crs, grid.x0, grid.y0, grid.x1, grid.y1, densify_pts=21
    )
    win = src.window(left, bottom, right, top)
    margin = 2
    col0 = math.floor(win.col_off) - margin
    row0 = math.floor(win.row_off) - margin
    ncols = math.ceil(win.col_off + win.width) + margin - col0
    nrows = math.ceil(win.row_off + win.height) + margin - row0
    read_win = RioWindow(col0, row0, ncols, nrows)
    nodata = src.nodata
    arr = src.read(
        1, window=read_win, boundless=True, fill_value=nodata if nodata is not None else 0
    )
    arr = arr.astype(np.float32)
    if nodata is not None:
        arr[arr == nodata] = np.nan

    dst = np.full((grid.height, grid.width), np.nan, dtype=np.float32)
    reproject(
        source=arr,
        destination=dst,
        src_transform=src.window_transform(read_win),
        src_crs=crs,
        src_nodata=np.nan,
        dst_transform=grid.transform(),
        dst_crs=grid.crs,
        dst_nodata=np.nan,
        resampling=Resampling.average,
    )
    return dst


def hillshade(
    dem: NDArray[np.floating[Any]],
    pixel_m: float,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
) -> NDArray[np.uint8]:
    """Standard hillshade (0–255). NaN pixels come out as 0."""
    z = np.asarray(dem, dtype=np.float64)
    dzdy, dzdx = np.gradient(z, pixel_m)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, dzdy)
    az = math.radians(360.0 - azimuth_deg + 90.0)
    alt = math.radians(altitude_deg)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    out = np.clip(shade * 255.0, 0, 255)
    out[~np.isfinite(out)] = 0
    return out.astype(np.uint8)
