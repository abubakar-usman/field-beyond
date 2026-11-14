"""Planetary body constants and coordinate reference systems.

Every distance, pixel size and slope must use the radius of the body the data
belongs to. Earth, Moon and Mars coordinates are never mixed (CLAUDE.md rule 3).

Moon and Mars are treated as spheres (IAU 2015 ocentric definitions). Earth
geometry is stored in EPSG:4326 (WGS84); for great-circle distances and ground
pixel sizes on Earth we use the IUGG mean radius, which is within 0.3% of the
ellipsoid everywhere and is only used for checks such as the no-upsampling
assertion. Earth reprojection itself goes through pyproj with the WGS84 datum.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from pyproj import CRS


class BodyName(StrEnum):
    EARTH = "earth"
    MOON = "moon"
    MARS = "mars"


@dataclass(frozen=True)
class Body:
    name: BodyName
    radius_m: float
    """Sphere radius used for distances and ground pixel sizes."""
    geographic_crs: str
    """Authority code of the body's geographic (lon/lat) CRS."""
    laea_datum: str
    """PROJ fragment defining the figure of the body for projected CRSs."""

    def crs(self) -> CRS:
        return CRS.from_user_input(self.geographic_crs)


EARTH = Body(
    name=BodyName.EARTH,
    radius_m=6_371_008.8,  # IUGG mean radius
    geographic_crs="EPSG:4326",
    laea_datum="+datum=WGS84",
)
MOON = Body(
    name=BodyName.MOON,
    radius_m=1_737_400.0,  # IAU 2015 sphere
    geographic_crs="IAU_2015:30100",
    laea_datum="+R=1737400",
)
MARS = Body(
    name=BodyName.MARS,
    radius_m=3_396_190.0,  # IAU 2015 sphere
    geographic_crs="IAU_2015:49900",
    laea_datum="+R=3396190",
)

BODIES: dict[BodyName, Body] = {b.name: b for b in (EARTH, MOON, MARS)}


def get_body(name: str | BodyName) -> Body:
    try:
        return BODIES[BodyName(name)]
    except ValueError as exc:
        raise ValueError(
            f"unknown body {name!r}; expected one of {[b.value for b in BodyName]}"
        ) from exc


def great_circle_distance_m(
    body: Body, lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Haversine distance on the body's sphere, in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * body.radius_m * math.asin(min(1.0, math.sqrt(a)))


def metres_per_degree(body: Body, lat_deg: float) -> tuple[float, float]:
    """Ground length of one degree at a latitude: (along longitude, along latitude)."""
    per_deg_lat = body.radius_m * math.pi / 180.0
    per_deg_lon = per_deg_lat * math.cos(math.radians(lat_deg))
    return per_deg_lon, per_deg_lat


def ground_pixel_size_m(
    body: Body, lat_deg: float, dlon_deg: float, dlat_deg: float
) -> tuple[float, float]:
    """Ground size (x, y) in metres of a geographic pixel at a latitude."""
    mx, my = metres_per_degree(body, lat_deg)
    return abs(dlon_deg) * mx, abs(dlat_deg) * my


def laea_proj(body: Body, lat_0: float, lon_0: float) -> str:
    """Lambert azimuthal equal-area projection centred on a point, on the body's own figure."""
    return (
        f"+proj=laea +lat_0={lat_0} +lon_0={lon_0} +x_0=0 +y_0=0 "
        f"{body.laea_datum} +units=m +no_defs +type=crs"
    )


def geographic_proj(body: Body) -> str:
    """Geographic lon/lat CRS as a PROJ string on the same figure as :func:`laea_proj`.

    Moon and Mars use the IAU sphere so a transform between this and the LAEA
    never routes through an Earth datum.
    """
    return f"+proj=longlat {body.laea_datum} +no_defs +type=crs"


def laea_point_distance_m(body: Body, angular_distance_rad: float) -> float:
    """Radial distance from the LAEA centre of a point at a given angular distance (sphere)."""
    return 2 * body.radius_m * math.sin(angular_distance_rad / 2)
