import numpy as np
import pytest

from core.allowlist import DisallowedURL, check_url, is_allowed
from core.bodies import EARTH, MARS, MOON
from core.config import (
    load_grid,
    load_products,
    load_scoring,
    load_sources,
    load_targets,
    run_config_hash,
)
from core.grid import (
    iter_windows,
    make_cell_id,
    parse_cell_id,
    region_laea_polygon,
    window_center_lonlat,
    window_from_cell_id,
    window_lonlat_polygon,
)
from core.raster import (
    UpsamplingError,
    aligned_grid,
    assert_not_upsampling,
    build_mosaic_vrt,
    hillshade,
    source_ground_pixel_m,
)

# ---------------------------------------------------------------- config


def test_all_config_files_load():
    s = load_scoring("terrain-v1")
    g = load_grid("pilot-v1")
    t = load_targets()
    assert s.version == "terrain-v1"
    assert sum(s.weights.values()) == pytest.approx(1.0)
    assert {r.id for r in g.regions} == {"earth_atacama", "earth_sahara"}
    assert set(t) == {"mars_jezero", "moon_taurus_littrow"}
    assert load_sources().hosts
    assert {p.id for p in load_products().products} >= {"copernicus_glo30", "sldem2015"}


def test_target_scales_match_d023():
    t = load_targets()
    assert t["mars_jezero"].comparison.scale_m == 200
    assert t["moon_taurus_littrow"].comparison.scale_m == 60
    for target in t.values():
        assert target.comparison.footprint_m == load_grid().window_m


def test_product_hosts_are_allowlisted():
    for p in load_products().products:
        assert is_allowed(p.url), p.id
        if p.tile_template:
            url = p.tile_template.format(ns="N", lat=21, ew="W", lon=13)
            assert is_allowed(url), p.id


def test_config_hash_is_stable():
    assert run_config_hash() == run_config_hash()
    assert len(run_config_hash()) == 64


# ---------------------------------------------------------------- allowlist


@pytest.mark.parametrize(
    "url",
    [
        "http://earth-search.aws.element84.com/v1",  # not https
        "https://evil.example.com/x",
        "https://169.254.169.254/latest/meta-data",
        "https://user:pw@macrostrat.org/api",
        "https://macrostrat.org:8443/api",
        "https://macrostrat.org.evil.com/api",
        "https://blob.core.windows.net/",  # bare suffix, no account
        "file:///etc/passwd",
    ],
)
def test_allowlist_rejects(url):
    with pytest.raises(DisallowedURL):
        check_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://earth-search.aws.element84.com/v1/search",
        "https://MACROSTRAT.org/api/v2",
        "https://cpdataeuwest.blob.core.windows.net/x.tif",
        "https://planetarymaps.usgs.gov:443/mosaic/x.tif",
    ],
)
def test_allowlist_accepts(url):
    assert check_url(url) == url


# ---------------------------------------------------------------- grid


def test_cell_id_round_trip():
    for ordinal, ix, iy in [(1, 0, 0), (2, -40, 37), (1, 4999, -5000)]:
        assert parse_cell_id(make_cell_id(ordinal, ix, iy)) == (ordinal, ix, iy)
    with pytest.raises(ValueError):
        make_cell_id(1, 5000, 0)


@pytest.mark.parametrize("region_id", ["earth_atacama", "earth_sahara"])
def test_windows_inside_region_and_aligned(region_id):
    g = load_grid()
    region = g.region(region_id)
    poly = region_laea_polygon(region)
    ws = list(iter_windows(g, region_id))
    assert len(ws) > 1000
    ids = [w.cell_id for w in ws]
    assert len(set(ids)) == len(ids)
    for w in ws[:: max(1, len(ws) // 50)]:
        assert w.x0 % g.stride_m == 0 and w.y0 % g.stride_m == 0
        assert poly.contains(w.laea_box)
        assert window_from_cell_id(g, w.cell_id) == w
        lon, lat = window_center_lonlat(region, w)
        b = region.bbox
        assert b.west < lon < b.east and b.south < lat < b.north
        ll = window_lonlat_polygon(region, w)
        assert ll.is_valid


def test_windows_are_deterministic():
    g = load_grid()
    a = [w.cell_id for w in iter_windows(g, "earth_sahara")][:100]
    b = [w.cell_id for w in iter_windows(g, "earth_sahara")][:100]
    assert a == b


# ---------------------------------------------------------------- raster


def test_assert_not_upsampling():
    assert_not_upsampling((30.9, 28.6), (60, 60))
    assert_not_upsampling((59.2, 55.6), (60, 60))
    assert_not_upsampling((200, 200), (200, 200))
    with pytest.raises(UpsamplingError):
        assert_not_upsampling((59.2, 55.6), (59, 59))  # the 59 m Moon grid D-023 rejected
    with pytest.raises(UpsamplingError):
        assert_not_upsampling((200, 200), (60, 60))  # Mars product onto the Moon grid


def test_source_ground_pixel_geographic_is_conservative():
    one_arcsec = 1 / 3600
    dx, dy = source_ground_pixel_m(
        body=EARTH, is_geographic=True, res=(one_arcsec, one_arcsec), lat_range=(-24.5, -19.5)
    )
    assert dy == pytest.approx(30.88, abs=0.01)
    assert dx == pytest.approx(dy * np.cos(np.radians(19.5)), rel=1e-9)
    # straddling the equator uses the equator
    dx0, _ = source_ground_pixel_m(
        body=MARS, is_geographic=True, res=(0.01, 0.01), lat_range=(-1, 1)
    )
    assert dx0 == pytest.approx(MARS.radius_m * np.pi / 180 * 0.01)
    assert source_ground_pixel_m(
        body=MOON, is_geographic=False, res=(59.2, 59.2), lat_range=(0, 1)
    ) == (
        59.2,
        59.2,
    )


def test_aligned_grid_edges_are_multiples():
    g = aligned_grid("EPSG:3857", (-1234.5, 777.0, 9876.0, 5432.1), 60.0)
    assert g.x0 % 60 == 0 and g.y1 % 60 == 0
    assert g.x0 <= -1234.5 and g.x1 >= 9876.0 and g.y0 <= 777.0 and g.y1 >= 5432.1


def test_window_slices_use_pixel_centres():
    g = aligned_grid("EPSG:3857", (0, 0, 20000, 20000), 60.0)
    rs, cs = g.window_slices(5000, 5000, 15000, 15000)
    # 10 km / 60 m = 166.67: 166 or 167 centres fit depending on phase
    assert (rs.stop - rs.start) in (166, 167)
    assert (cs.stop - cs.start) in (166, 167)
    g200 = aligned_grid("EPSG:3857", (0, 0, 20000, 20000), 200.0)
    rs, cs = g200.window_slices(5000, 5000, 15000, 15000)
    assert rs.stop - rs.start == 50 and cs.stop - cs.start == 50


def test_mosaic_vrt_offsets():
    a = {
        "path": "a.tif",
        "width": 10,
        "height": 10,
        "transform": (1.0, 0, 0.0, 0, -1.0, 10.0),
        "crs_wkt": "EPSG:4326",
        "nodata": -9999.0,
        "dtype": "float32",
    }
    b = dict(a, path="b.tif", transform=(1.0, 0, 10.0, 0, -1.0, 10.0))
    xml = build_mosaic_vrt([a, b])
    assert 'rasterXSize="20"' in xml
    assert '<DstRect xOff="10" yOff="0"' in xml


def test_hillshade_range():
    dem = np.add.outer(np.arange(20.0), np.arange(20.0)) * 10
    hs = hillshade(dem, 30.0)
    assert hs.dtype == np.uint8 and hs.shape == dem.shape
