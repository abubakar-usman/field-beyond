"""Discovery for each product in `config/products-v1.yaml`.

- Copernicus DEM GLO-30: Earth Search STAC, falling back to deterministic 1° tile names.
- ESA WorldCover 2021: deterministic 3° tile names on the public bucket.
- SLDEM2015 / MOLA–HRSC blend: one large GeoTIFF each, read by range requests.
"""

from __future__ import annotations

import math
from typing import Any

import httpx

from core.allowlist import check_url
from core.config import BBox, Product, load_products
from pipeline.adapters.base import AssetRef, http_client, retry


def _ns(lat: int) -> str:
    return "N" if lat >= 0 else "S"


def _ew(lon: int) -> str:
    return "E" if lon >= 0 else "W"


def tile_corners(bbox: BBox, size_deg: int) -> list[tuple[int, int]]:
    """Lower-left corners of every ``size_deg`` tile touching the bbox."""
    lat0 = math.floor(bbox.south / size_deg) * size_deg
    lon0 = math.floor(bbox.west / size_deg) * size_deg
    out = []
    lat = lat0
    while lat < bbox.north:
        lon = lon0
        while lon < bbox.east:
            out.append((lat, lon))
            lon += size_deg
        lat += size_deg
    return out


def _tile_url(p: Product, lat: int, lon: int) -> str:
    assert p.tile_template
    return p.tile_template.format(ns=_ns(lat), lat=abs(lat), ew=_ew(lon), lon=abs(lon))


def s3_to_https(href: str, region: str = "eu-central-1") -> str:
    if href.startswith("s3://"):
        bucket, _, key = href[5:].partition("/")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return href


def copernicus_assets(bbox: BBox, use_stac: bool = True) -> list[AssetRef]:
    p = load_products().product("copernicus_glo30")
    urls: dict[str, dict[str, Any]] = {}
    if use_stac:
        try:
            urls = _stac_search(p, bbox)
        except Exception:  # STAC down: fall back to deterministic names below
            urls = {}
    if not urls:
        for lat, lon in tile_corners(bbox, p.tile_size_deg or 1):
            u = _tile_url(p, lat, lon)
            urls[u] = {"tile": f"{lat},{lon}", "discovery": "tile_template"}
    return [
        AssetRef(
            product_id=p.id,
            provider=p.provider,
            body="earth",
            key=u.rsplit("/", 1)[-1],
            url=check_url(u),
            resolution_m=p.resolution_m,
            source_version=p.version,
            access_meta=meta,
        )
        for u, meta in sorted(urls.items())
    ]


def _stac_search(p: Product, bbox: BBox) -> dict[str, dict[str, Any]]:
    url = check_url(p.url.rstrip("/") + "/search")
    body: dict[str, Any] = {
        "collections": [p.collection],
        "bbox": [bbox.west, bbox.south, bbox.east, bbox.north],
        "limit": 200,
    }
    out: dict[str, dict[str, Any]] = {}
    with http_client() as c:
        for _ in range(50):  # page limit
            page_body = dict(body)

            def _post(b: dict[str, Any] = page_body) -> httpx.Response:
                return c.post(url, json=b)

            r = retry(_post)
            r.raise_for_status()
            data = r.json()
            for item in data.get("features", []):
                assets: dict[str, Any] = item.get("assets", {})
                first: dict[str, Any] = assets.get("data") or next(iter(assets.values()), {})
                href = first.get("href")
                if href:
                    out[s3_to_https(href)] = {"stac_item": item.get("id"), "discovery": "stac"}
            nxt = next((link for link in data.get("links", []) if link.get("rel") == "next"), None)
            if not nxt:
                break
            if nxt.get("body"):
                body = nxt["body"]
            else:
                break
    return out


def worldcover_assets(bbox: BBox) -> list[AssetRef]:
    p = load_products().product("esa_worldcover_2021")
    return [
        AssetRef(
            product_id=p.id,
            provider=p.provider,
            body="earth",
            key=_tile_url(p, lat, lon).rsplit("/", 1)[-1],
            url=check_url(_tile_url(p, lat, lon)),
            resolution_m=p.resolution_m,
            source_version=p.version,
            access_meta={"tile": f"{lat},{lon}"},
        )
        for lat, lon in tile_corners(bbox, p.tile_size_deg or 3)
    ]


PLANETARY_PRODUCT = {"mars": "mola_hrsc_blend_v2", "moon": "sldem2015"}


def planetary_asset(body: str) -> AssetRef:
    p = load_products().product(PLANETARY_PRODUCT[body])
    return AssetRef(
        product_id=p.id,
        provider=p.provider,
        body=body,
        key=p.url.rsplit("/", 1)[-1],
        url=check_url(p.url),
        resolution_m=p.resolution_m,
        source_version=p.version,
        access_meta={"access": "http_range_requests"},
    )
