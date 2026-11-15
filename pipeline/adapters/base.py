"""Adapter plumbing: allowlisted remote access, retries, source-asset records."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from core.allowlist import check_url
from core.provenance import sha256_file

# GDAL settings for reading public cloud-optimised GeoTIFFs over HTTPS without credentials.
GDAL_ENV: dict[str, str | int] = {
    "AWS_NO_SIGN_REQUEST": "YES",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    # .LBL/.IMG: SLDEM2015 tiles on NASA PGDA are raw PDS images with a detached label.
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.TIF,.LBL,.IMG,.lbl,.img",
    "GDAL_HTTP_MAX_RETRY": "5",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "VSI_CACHE": "TRUE",
    "GDAL_CACHEMAX": 1024,
}


@dataclass
class AssetRef:
    """One remote file the pipeline reads. Becomes a `source_assets` row."""

    product_id: str
    provider: str
    body: str
    key: str
    url: str
    resolution_m: float
    source_version: str
    footprint: dict[str, float] | None = None  # lon/lat bbox (Earth) or body lon/lat bbox
    sha256: str | None = None
    access_meta: dict[str, Any] = field(default_factory=dict)
    height_unit_m: float = 1.0  # metres per stored height unit

    @property
    def asset_id(self) -> str:
        return f"{self.product_id}:{self.key}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def retry[T](fn: Callable[[], T], *, attempts: int = 5, base_delay: float = 1.0) -> T:
    """Call ``fn`` with exponential backoff on network errors and 5xx/429."""
    for i in range(attempts):
        try:
            return fn()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in (
                429,
                500,
                502,
                503,
                504,
            )
            if not retryable or i == attempts - 1:
                raise
            time.sleep(base_delay * 2**i)
    raise AssertionError("unreachable")


def http_client() -> httpx.Client:
    # Redirects are not followed: a redirect target would bypass the allowlist.
    return httpx.Client(
        timeout=60, follow_redirects=False, headers={"User-Agent": "earth-analog-explorer/0.1"}
    )


def fetch(url: str, dest: Path) -> str:
    """Download an allowlisted URL to ``dest``; returns the SHA-256."""
    check_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    def _do() -> None:
        with http_client() as c, c.stream("GET", url) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)

    retry(_do)
    os.replace(tmp, dest)
    return sha256_file(dest)


def vsicurl(url: str) -> str:
    """GDAL path for an allowlisted remote file (read with HTTP range requests)."""
    check_url(url)
    return f"/vsicurl/{url}"


@contextmanager
def gdal_env() -> Iterator[None]:
    import rasterio

    with rasterio.Env(**GDAL_ENV):
        yield
