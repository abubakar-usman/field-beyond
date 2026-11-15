"""On-disk layout of pipeline outputs, shared by the pipeline (writer) and the API (reader).

::

    <data_dir>/processed/
      runs/<run_id>.json                          processing run record (provenance)
      regions/<region_id>/features-<scale>m.parquet   search index (D-019)
      regions/<region_id>/current-<scale>m.json        {"run_id": ...}
      targets/<target_id>/profile-<scale>m.json        target feature profile
      targets/<target_id>/preview.png                  hillshade of the preview bbox
      registry/registry.geojson                        known-analog registry snapshot
      gazetteer/catalog.json                           IAU names that can become targets

The parquet SHA-256 lives on the run record, not in the file. Reading a region
re-hashes the file and refuses a mismatch.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from core.provenance import sha256_file

DataStatus = Literal["synthetic", "measured"]


class ArtifactMissing(FileNotFoundError):
    pass


class ChecksumMismatch(RuntimeError):
    pass


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _write_json(path: Path, obj: Any) -> None:
    _atomic_write_text(path, json.dumps(obj, indent=2, sort_keys=True, default=str))


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise ArtifactMissing(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- records


@dataclass
class RunRecord:
    id: str
    kind: str  # earth_features | target_profile | registry_import | seed_fake
    status: Literal["running", "completed", "failed"]
    code_version: str
    config_hash: str
    schema_version: str
    data_status: DataStatus
    started_at: str = field(default_factory=utcnow)
    finished_at: str | None = None
    region_id: str | None = None
    target_id: str | None = None
    scale_m: int | None = None
    grid_version: str | None = None
    features_path: str | None = None
    features_sha256: str | None = None
    source_asset_ids: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunRecord:
        return cls(**d)


@dataclass
class TargetProfileRecord:
    target_id: str
    body: str
    name: str
    scale_m: int
    footprint_m: int
    center_lat: float
    center_lon: float
    values: dict[str, Any]
    availability: dict[str, bool]
    meta: dict[str, Any]
    run_id: str
    schema_version: str
    data_status: DataStatus
    crs: str
    footprint_wkt: str
    preview_path: str | None = None
    source_asset_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TargetProfileRecord:
        return cls(**d)


@dataclass
class RegistryEntry:
    id: str
    name: str
    geometry: BaseGeometry
    body_target_relevance: list[str]
    citations: list[dict[str, Any]]
    source: str
    boundary_note: str = ""


@dataclass
class RegistrySnapshot:
    version: str
    review_date: str
    sources_checked: list[str]
    entries: list[RegistryEntry]

    @property
    def loaded(self) -> bool:
        return bool(self.sources_checked)

    @classmethod
    def empty(cls) -> RegistrySnapshot:
        return cls(version="none", review_date="", sources_checked=[], entries=[])


# ---------------------------------------------------------------- store


class Artifacts:
    def __init__(self, data_dir: str | Path):
        self.root = Path(data_dir) / "processed"

    # paths
    def run_path(self, run_id: str) -> Path:
        return self.root / "runs" / f"{run_id}.json"

    def features_path(self, region_id: str, scale_m: int) -> Path:
        return self.root / "regions" / region_id / f"features-{scale_m}m.parquet"

    def current_path(self, region_id: str, scale_m: int) -> Path:
        return self.root / "regions" / region_id / f"current-{scale_m}m.json"

    def target_profile_path(self, target_id: str, scale_m: int) -> Path:
        return self.root / "targets" / target_id / f"profile-{scale_m}m.json"

    def target_preview_path(self, target_id: str) -> Path:
        return self.root / "targets" / target_id / "preview.png"

    def registry_path(self) -> Path:
        return self.root / "registry" / "registry.geojson"

    def write_gazetteer_catalog(self, catalog: dict[str, Any]) -> None:
        _write_json(self.gazetteer_catalog_path(), catalog)

    def read_gazetteer_catalog(self) -> dict[str, Any] | None:
        path = self.gazetteer_catalog_path()
        if not path.exists():
            return None
        return _read_json(path)

    def gazetteer_catalog_path(self) -> Path:
        return self.root / "gazetteer" / "catalog.json"

    def gazetteer_raw_path(self, body: str) -> Path:
        return self.root / "gazetteer" / f"{body}_nomenclature_center_pts.zip"

    # runs
    def write_run(self, run: RunRecord) -> None:
        _write_json(self.run_path(run.id), run.to_dict())

    def read_run(self, run_id: str) -> RunRecord:
        return RunRecord.from_dict(_read_json(self.run_path(run_id)))

    def list_runs(self) -> list[RunRecord]:
        d = self.root / "runs"
        if not d.exists():
            return []
        return [RunRecord.from_dict(_read_json(p)) for p in sorted(d.glob("*.json"))]

    # features
    def write_features(self, df: pd.DataFrame, region_id: str, scale_m: int, run: RunRecord) -> str:
        """Write the parquet, hash it, and point the region at this run. Returns the SHA-256."""
        path = self.features_path(region_id, scale_m)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".parquet.tmp")
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
        sha = sha256_file(path)
        run.features_path = str(path.relative_to(self.root).as_posix())
        run.features_sha256 = sha
        self.write_run(run)
        _write_json(self.current_path(region_id, scale_m), {"run_id": run.id})
        return sha

    def current_run(self, region_id: str, scale_m: int) -> RunRecord:
        ptr = _read_json(self.current_path(region_id, scale_m))
        return self.read_run(ptr["run_id"])

    def read_features(self, region_id: str, scale_m: int) -> tuple[pd.DataFrame, RunRecord]:
        """The search index for one region and scale, verified against its run (D-019)."""
        try:
            run = self.current_run(region_id, scale_m)
        except ArtifactMissing as exc:
            raise ArtifactMissing(f"no features for {region_id} at {scale_m} m") from exc
        path = self.features_path(region_id, scale_m)
        if not path.exists():
            raise ArtifactMissing(str(path))
        actual = sha256_file(path)
        if run.status != "completed" or actual != run.features_sha256:
            raise ChecksumMismatch(
                f"{path.name} SHA-256 {actual[:12]} does not match run {run.id} "
                f"({(run.features_sha256 or 'none')[:12]}, status {run.status})"
            )
        return pd.read_parquet(path), run

    # targets
    def write_target_profile(self, rec: TargetProfileRecord) -> None:
        _write_json(self.target_profile_path(rec.target_id, rec.scale_m), rec.to_dict())

    def read_target_profile(self, target_id: str, scale_m: int) -> TargetProfileRecord:
        return TargetProfileRecord.from_dict(
            _read_json(self.target_profile_path(target_id, scale_m))
        )

    # registry
    def write_registry(self, snap: RegistrySnapshot) -> None:
        fc = {
            "type": "FeatureCollection",
            "registry": {
                "version": snap.version,
                "review_date": snap.review_date,
                "sources_checked": snap.sources_checked,
            },
            "features": [
                {
                    "type": "Feature",
                    "id": e.id,
                    "geometry": mapping(e.geometry),
                    "properties": {
                        "name": e.name,
                        "body_target_relevance": e.body_target_relevance,
                        "citations": e.citations,
                        "source": e.source,
                        "boundary_note": e.boundary_note,
                    },
                }
                for e in snap.entries
            ],
        }
        _write_json(self.registry_path(), fc)

    def read_registry(self) -> RegistrySnapshot:
        path = self.registry_path()
        if not path.exists():
            return RegistrySnapshot.empty()
        fc = _read_json(path)
        meta = fc.get("registry", {})
        return RegistrySnapshot(
            version=meta.get("version", "unknown"),
            review_date=meta.get("review_date", ""),
            sources_checked=list(meta.get("sources_checked", [])),
            entries=[
                RegistryEntry(
                    id=str(f["id"]),
                    name=f["properties"]["name"],
                    geometry=shape(f["geometry"]),
                    body_target_relevance=list(f["properties"].get("body_target_relevance", [])),
                    citations=list(f["properties"].get("citations", [])),
                    source=f["properties"].get("source", ""),
                    boundary_note=f["properties"].get("boundary_note", ""),
                )
                for f in fc.get("features", [])
            ],
        )
