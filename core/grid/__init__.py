"""Earth search windows on a per-region LAEA grid.

Windows are squares in the region's Lambert azimuthal equal-area projection
(`config/grids/pilot-v1.yaml`). Lower-left corners fall on multiples of the
stride measured from the LAEA origin, so a window's position never depends on
the bbox edge.

Cell ids are deterministic integers::

    cell_id = region_ordinal * 10**8 + (iy + OFFSET) * 10**4 + (ix + OFFSET)

where ``ix``/``iy`` are the stride indices of the lower-left corner and
``region_ordinal`` is the region's 1-based position in the grid file. Reordering
regions therefore needs a new grid version.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache

import shapely
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, box

from core.config import GridConfig, Region

INDEX_OFFSET = 5_000
INDEX_SPAN = 10_000
ORDINAL_FACTOR = 10**8


@dataclass(frozen=True)
class Window:
    cell_id: int
    region_id: str
    grid_version: str
    ix: int
    iy: int
    x0: float
    y0: float
    size_m: float

    @property
    def x1(self) -> float:
        return self.x0 + self.size_m

    @property
    def y1(self) -> float:
        return self.y0 + self.size_m

    @property
    def laea_box(self) -> Polygon:
        return box(self.x0, self.y0, self.x1, self.y1)


def make_cell_id(region_ordinal: int, ix: int, iy: int) -> int:
    jx, jy = ix + INDEX_OFFSET, iy + INDEX_OFFSET
    if not (0 <= jx < INDEX_SPAN and 0 <= jy < INDEX_SPAN):
        raise ValueError(f"window index out of range: ix={ix}, iy={iy}")
    if region_ordinal < 1:
        raise ValueError("region_ordinal is 1-based")
    return region_ordinal * ORDINAL_FACTOR + jy * INDEX_SPAN + jx


def parse_cell_id(cell_id: int) -> tuple[int, int, int]:
    ordinal, rest = divmod(cell_id, ORDINAL_FACTOR)
    jy, jx = divmod(rest, INDEX_SPAN)
    return ordinal, jx - INDEX_OFFSET, jy - INDEX_OFFSET


@lru_cache(maxsize=32)
def _transformers(proj: str) -> tuple[Transformer, Transformer]:
    laea = CRS.from_user_input(proj)
    wgs84 = CRS.from_epsg(4326)
    return (
        Transformer.from_crs(wgs84, laea, always_xy=True),
        Transformer.from_crs(laea, wgs84, always_xy=True),
    )


def to_laea(region: Region) -> Transformer:
    return _transformers(region.laea.proj)[0]


def to_lonlat(region: Region) -> Transformer:
    return _transformers(region.laea.proj)[1]


def _densify(poly: Polygon, step: float) -> Polygon:
    return Polygon(poly.exterior.segmentize(step).coords)


def region_laea_polygon(region: Region) -> Polygon:
    """The region's lon/lat bbox, densified and projected into its LAEA."""
    b = region.bbox
    ll = _densify(box(b.west, b.south, b.east, b.north), 0.05)
    fwd = to_laea(region)
    return shapely.transform(ll, lambda x, y: fwd.transform(x, y), interleaved=False)


def window_lonlat_polygon(region: Region, w: Window, points_per_edge: int = 8) -> Polygon:
    inv = to_lonlat(region)
    sq = _densify(w.laea_box, w.size_m / points_per_edge)
    return shapely.transform(sq, lambda x, y: inv.transform(x, y), interleaved=False)


def window_center_lonlat(region: Region, w: Window) -> tuple[float, float]:
    lon, lat = to_lonlat(region).transform(w.x0 + w.size_m / 2, w.y0 + w.size_m / 2)
    return float(lon), float(lat)


def iter_windows(grid: GridConfig, region_id: str) -> Iterator[Window]:
    """Every window that lies fully inside the region, ordered by row then column."""
    region = grid.region(region_id)
    ordinal = grid.region_ordinal(region_id)
    size, stride = float(grid.window_m), float(grid.stride_m)
    if size <= 0 or stride <= 0:
        raise ValueError("window_m and stride_m must be positive")
    poly = region_laea_polygon(region)
    xmin, ymin, xmax, ymax = poly.bounds
    kx0, kx1 = math.ceil(xmin / stride), math.floor((xmax - size) / stride)
    ky0, ky1 = math.ceil(ymin / stride), math.floor((ymax - size) / stride)
    for iy in range(ky0, ky1 + 1):
        for ix in range(kx0, kx1 + 1):
            x0, y0 = ix * stride, iy * stride
            if not poly.contains(box(x0, y0, x0 + size, y0 + size)):
                continue
            yield Window(
                cell_id=make_cell_id(ordinal, ix, iy),
                region_id=region_id,
                grid_version=grid.version,
                ix=ix,
                iy=iy,
                x0=x0,
                y0=y0,
                size_m=size,
            )


def window_from_cell_id(grid: GridConfig, cell_id: int) -> Window:
    ordinal, ix, iy = parse_cell_id(cell_id)
    region = grid.regions[ordinal - 1]
    return Window(
        cell_id=cell_id,
        region_id=region.id,
        grid_version=grid.version,
        ix=ix,
        iy=iy,
        x0=ix * float(grid.stride_m),
        y0=iy * float(grid.stride_m),
        size_m=float(grid.window_m),
    )
