"""Turn IAU gazetteer rows into target configs.

The scored footprint stays 10 km at the feature center (D-018). The gazetteer
extent is only the preview box. Curated files in ``config/targets/`` win when
an id would collide.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from core.bodies import get_body, metres_per_degree
from core.config import (
    BBox,
    BodyName,
    Comparison,
    GazetteerConfig,
    GazetteerFile,
    Preview,
    TargetConfig,
)

_SLUG = re.compile(r"[^a-z0-9]+")


def descriptor(type_field: str) -> str:
    """'Crater, craters' -> 'Crater'."""
    return type_field.split(",", 1)[0].strip()


def to_east_180(lon: float) -> float:
    """Gazetteer longitudes are 0–360 east. Target configs use −180–180."""
    x = lon % 360.0
    if x > 180.0:
        x -= 360.0
    return x


def _slug(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in folded if not unicodedata.combining(c))
    return _SLUG.sub("_", ascii_text.lower()).strip("_")


def _display_name(name: str, type_field: str) -> str:
    """Append the descriptor only when the name does not already carry it or its plural."""
    terms = [part.strip().lower() for part in type_field.split(",") if part.strip()]
    if any(term and term in name.lower() for term in terms):
        return name
    return f"{name} {descriptor(type_field).lower()}"


def _preview_bbox(
    body: BodyName,
    center_lat: float,
    center_lon: float,
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
    diameter_km: float,
    footprint_m: int,
) -> BBox:
    west, east = to_east_180(min_lon), to_east_180(max_lon)
    south, north = min_lat, max_lat
    crosses = west >= east or (east - west) > 180
    degenerate = not (south < north) or crosses
    if degenerate:
        figure = get_body(body)
        per_lon, per_lat = metres_per_degree(figure, center_lat)
        half_m = max(diameter_km * 1000.0 / 2.0, footprint_m / 2.0)
        dlat = half_m / per_lat
        dlon = half_m / per_lon if per_lon > 1.0 else 1.0
        west, east = center_lon - dlon, center_lon + dlon
        south, north = center_lat - dlat, center_lat + dlat
    south = max(-90.0, south)
    north = min(90.0, north)
    if west <= -180:
        west = -180.0
    if east >= 180:
        east = 180.0
    if not (west < east and south < north):
        # Last resort: a small box around the center that still validates.
        west, east = center_lon - 0.05, center_lon + 0.05
        south, north = max(-90.0, center_lat - 0.05), min(90.0, center_lat + 0.05)
    return BBox(west=west, south=south, east=east, north=north)


def _number(row: dict[str, str], key: str) -> float | None:
    raw = row.get(key, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def select_features(
    rows: list[dict[str, str]],
    body_file: GazetteerFile,
    cfg: GazetteerConfig,
    *,
    reserved_ids: set[str],
    source_url: str,
    source_sha256: str,
) -> list[dict[str, Any]]:
    """Keep adopted names inside the configured type, size and latitude bounds."""
    allowed = set(cfg.feature_types)
    used = set(reserved_ids)
    kept: list[dict[str, Any]] = []
    for row in rows:
        if "Adopted" not in row.get("approval", ""):
            continue
        kind = descriptor(row.get("type", ""))
        if kind not in allowed:
            continue
        diameter = _number(row, "diameter")
        lat = _number(row, "center_lat")
        lon = _number(row, "center_lon")
        if diameter is None or lat is None or lon is None:
            continue
        if not (cfg.diameter_km_min <= diameter <= cfg.diameter_km_max):
            continue
        if not (body_file.lat_min <= lat <= body_file.lat_max):
            continue
        clean = row.get("clean_name") or row.get("name") or ""
        label = row.get("name") or clean
        if not clean or not label:
            continue
        base = f"{body_file.body.value}_{_slug(clean)}_{_slug(kind)}"
        if not base or base.endswith("_"):
            continue
        # A curated yaml target keeps its id. A second gazetteer name with the same slug gets a suffix.
        if base in reserved_ids:
            continue
        feature_id = base
        n = 2
        while feature_id in used:
            feature_id = f"{base}_{n}"
            n += 1
        used.add(feature_id)
        center_lon = to_east_180(lon)
        min_lon = _number(row, "min_lon")
        max_lon = _number(row, "max_lon")
        min_lat = _number(row, "min_lat")
        max_lat = _number(row, "max_lat")
        if None in (min_lon, max_lon, min_lat, max_lat):
            min_lon = max_lon = lon
            min_lat = max_lat = lat
        assert min_lon is not None and max_lon is not None
        assert min_lat is not None and max_lat is not None
        bbox = _preview_bbox(
            body_file.body,
            lat,
            center_lon,
            min_lon,
            max_lon,
            min_lat,
            max_lat,
            diameter,
            cfg.footprint_m,
        )
        name = _display_name(label, row.get("type", kind))
        note = (
            f"IAU-adopted {kind.lower()} from the USGS Gazetteer of Planetary Nomenclature. "
            f"Diameter {diameter:.1f} km. The scored profile is the {cfg.footprint_m // 1000} km "
            "square at this center, not the whole landform."
        )
        kept.append(
            {
                "id": feature_id,
                "body": body_file.body.value,
                "name": name,
                "feature_type": kind,
                "diameter_km": diameter,
                "center_lat": lat,
                "center_lon": center_lon,
                "scale_m": body_file.scale_m,
                "footprint_m": cfg.footprint_m,
                "preview_bbox": bbox.model_dump(),
                "note": note,
                "gazetteer_link": row.get("link", ""),
                "approval": row.get("approval", ""),
                "source_url": source_url,
                "source_sha256": source_sha256,
                "origin": "iau_gazetteer",
            }
        )
    kept.sort(key=lambda r: (r["body"], r["name"].lower(), r["id"]))
    return kept


def feature_to_target(row: dict[str, Any]) -> TargetConfig:
    bbox = row["preview_bbox"]
    return TargetConfig(
        id=row["id"],
        body=BodyName(row["body"]),
        name=row["name"],
        comparison=Comparison(
            center_lat=row["center_lat"],
            center_lon=row["center_lon"],
            footprint_m=row["footprint_m"],
            scale_m=row["scale_m"],
        ),
        preview=Preview(
            bbox=BBox(**bbox),
            note=row["note"],
        ),
    )


def find_feature(catalog: dict[str, Any] | None, target_id: str) -> dict[str, Any] | None:
    if not catalog:
        return None
    for row in catalog.get("targets", []):
        if row.get("id") == target_id:
            return row
    return None
