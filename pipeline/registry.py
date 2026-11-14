"""Import known-analog records (USGS "Known Terrestrial Analog Sites" first).

The dataset's exact format is checked in the data audit. This importer takes
either GeoJSON (points or polygons) or CSV with latitude/longitude columns.
Points are buffered into circles of a stated radius, and that assumption is
written into every entry's ``boundary_note``.

Nothing is invented: every entry comes from the file given.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import shapely
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from core.artifacts import Artifacts, RegistryEntry, RegistrySnapshot


def geodesic_buffer(lon: float, lat: float, radius_m: float) -> BaseGeometry:
    """Circle on Earth via a local azimuthal equidistant projection."""
    aeqd = CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")
    to_ll = Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True)
    circle = Point(0, 0).buffer(radius_m, quad_segs=16)
    return shapely.transform(circle, lambda x, y: to_ll.transform(x, y), interleaved=False)


def relevance_tokens(text: str | None) -> list[str]:
    if not text:
        return []
    return sorted({t for t in re.split(r"[^a-z0-9_]+", text.lower()) if t})


def _entry(
    i: int,
    props: dict[str, Any],
    geom: BaseGeometry,
    *,
    name_col: str,
    relevance_cols: list[str],
    ref_cols: list[str],
    id_col: str | None,
    source: str,
    buffer_m: float,
) -> RegistryEntry:
    note = ""
    if geom.geom_type == "Point":
        p = geom
        geom = geodesic_buffer(p.x, p.y, buffer_m)
        note = f"point record buffered to a {buffer_m / 1000:g} km radius circle (assumption, not a mapped boundary)"
    rel: list[str] = []
    for c in relevance_cols:
        rel.extend(relevance_tokens(str(props.get(c, "") or "")))
    citations = [{"field": c, "value": props[c]} for c in ref_cols if props.get(c)]
    ext_id = str(props.get(id_col)) if id_col and props.get(id_col) else f"{source}:{i}"
    return RegistryEntry(
        id=ext_id,
        name=str(props.get(name_col) or f"record {i}"),
        geometry=geom,
        body_target_relevance=sorted(set(rel)),
        citations=citations,
        source=source,
        boundary_note=note,
    )


def import_registry(
    artifacts: Artifacts,
    path: Path,
    *,
    source: str,
    version: str,
    review_date: str,
    name_col: str = "name",
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    relevance_cols: list[str] | None = None,
    ref_cols: list[str] | None = None,
    id_col: str | None = None,
    buffer_m: float = 10_000.0,
    append: bool = True,
) -> RegistrySnapshot:
    relevance_cols = relevance_cols or []
    ref_cols = ref_cols or []
    entries: list[RegistryEntry] = []
    kw = dict(
        name_col=name_col,
        relevance_cols=relevance_cols,
        ref_cols=ref_cols,
        id_col=id_col,
        source=source,
        buffer_m=buffer_m,
    )
    if path.suffix.lower() in (".geojson", ".json"):
        fc = json.loads(path.read_text(encoding="utf-8"))
        for i, f in enumerate(fc.get("features", [])):
            if not f.get("geometry"):
                continue
            entries.append(_entry(i, f.get("properties") or {}, shape(f["geometry"]), **kw))  # type: ignore[arg-type]
    else:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            for i, row in enumerate(csv.DictReader(fh)):
                try:
                    lat, lon = float(row[lat_col]), float(row[lon_col])
                except (KeyError, ValueError):
                    continue  # a record without coordinates cannot be checked spatially
                entries.append(_entry(i, row, Point(lon, lat), **kw))  # type: ignore[arg-type]
    existing = artifacts.read_registry() if append else RegistrySnapshot.empty()
    kept = [e for e in existing.entries if e.source != source]
    sources = sorted({*[s for s in existing.sources_checked if s != source], source})
    snap = RegistrySnapshot(
        version=version if not kept else f"{existing.version}+{version}",
        review_date=max(review_date, existing.review_date or ""),
        sources_checked=sources,
        entries=[*kept, *entries],
    )
    artifacts.write_registry(snap)
    return snap
