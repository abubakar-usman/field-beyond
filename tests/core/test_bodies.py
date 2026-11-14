import math

import pytest
from pyproj import CRS, Transformer

from core.bodies import (
    BODIES,
    EARTH,
    MARS,
    MOON,
    geographic_proj,
    get_body,
    great_circle_distance_m,
    ground_pixel_size_m,
    laea_point_distance_m,
    laea_proj,
    metres_per_degree,
)


@pytest.mark.parametrize("body", list(BODIES.values()), ids=lambda b: b.name.value)
def test_one_degree_of_latitude_uses_body_radius(body):
    d = great_circle_distance_m(body, 0, 0, 1, 0)
    assert d == pytest.approx(body.radius_m * math.pi / 180, rel=1e-12)


@pytest.mark.parametrize("body", list(BODIES.values()), ids=lambda b: b.name.value)
def test_quarter_meridian(body):
    assert great_circle_distance_m(body, 0, 0, 90, 0) == pytest.approx(body.radius_m * math.pi / 2)


def test_bodies_give_different_distances():
    d = {b.name: great_circle_distance_m(b, 10, 10, 11, 11) for b in BODIES.values()}
    assert d["moon"] < d["mars"] < d["earth"]
    assert d["mars"] / d["moon"] == pytest.approx(MARS.radius_m / MOON.radius_m, rel=1e-12)


@pytest.mark.parametrize("body", [MOON, MARS], ids=lambda b: b.name.value)
def test_planetary_crs_radius_matches_constant(body):
    crs = CRS.from_user_input(body.geographic_crs)
    assert crs.ellipsoid.semi_major_metre == body.radius_m
    assert crs.ellipsoid.semi_minor_metre == body.radius_m
    assert "WGS" not in crs.to_wkt()


def test_earth_crs_is_wgs84():
    assert CRS.from_user_input(EARTH.geographic_crs).to_epsg() == 4326


@pytest.mark.parametrize("body", list(BODIES.values()), ids=lambda b: b.name.value)
def test_metres_per_degree_shrinks_with_latitude(body):
    lon0, lat0 = metres_per_degree(body, 0)
    lon60, lat60 = metres_per_degree(body, 60)
    assert lat0 == lat60
    assert lon60 == pytest.approx(lon0 / 2)


def test_sldem_pixel_near_taurus_littrow_is_finer_than_60m():
    # 512 px/deg at 20.19 N; D-023 picks 60 m because the latitude axis is ~59.2 m.
    dx, dy = ground_pixel_size_m(MOON, 20.1911, 1 / 512, 1 / 512)
    assert dy == pytest.approx(59.22, abs=0.01)
    assert dx == pytest.approx(55.6, abs=0.1)
    assert max(dx, dy) < 60


@pytest.mark.parametrize("body", [MOON, MARS], ids=lambda b: b.name.value)
def test_laea_on_body_sphere_is_radially_exact(body):
    # A point 1 degree north of the LAEA centre sits at 2R sin(c/2) from the origin.
    proj = laea_proj(body, 18.0, 77.0)
    t = Transformer.from_crs(geographic_proj(body), proj, always_xy=True)
    x, y = t.transform(77.0, 19.0)
    assert x == pytest.approx(0, abs=1e-6)
    assert y == pytest.approx(laea_point_distance_m(body, math.radians(1)), rel=1e-9)


def test_laea_uses_wrong_radius_detectably():
    tm = Transformer.from_crs(geographic_proj(MOON), laea_proj(MOON, 0, 0), always_xy=True)
    t_mars = Transformer.from_crs(geographic_proj(MARS), laea_proj(MARS, 0, 0), always_xy=True)
    _, ym = tm.transform(0, 1)
    _, y_mars = t_mars.transform(0, 1)
    assert y_mars / ym == pytest.approx(MARS.radius_m / MOON.radius_m, rel=1e-9)


def test_get_body():
    assert get_body("mars") is MARS
    with pytest.raises(ValueError):
        get_body("venus")
