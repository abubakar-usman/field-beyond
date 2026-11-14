"""`pipeline load-db`: copy pipeline artifacts into PostGIS (the evidence store).

Idempotent: rows that already exist are left alone. Run after every `pipeline
run`, `pipeline target` or `pipeline import-registry` when the API uses the
SQL store.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from geoalchemy2.shape import from_shape
from shapely import wkt as shp_wkt
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.db.models import (
    EarthCell,
    FeatureProfile,
    KnownAnalog,
    PlanetaryTarget,
    ProcessingRun,
)
from backend.store.sql import make_engine
from core.artifacts import Artifacts
from core.config import GridConfig, load_targets
from core.grid import window_from_cell_id, window_lonlat_polygon

Progress = Callable[[str], None]
PROFILE_KEYS = ["slope_median", "slope_p90", "slope_hist", "relief", "roughness", "valid_fraction"]
LANDCOVER_KEYS = ["water_fraction", "built_up_fraction", "snow_ice_fraction", "vegetation_fraction"]


def load_all(
    artifacts: Artifacts, grid: GridConfig, database_url: str, progress: Progress = print
) -> None:
    engine = make_engine(database_url)
    with Session(engine) as s, s.begin():
        for run in artifacts.list_runs():
            s.execute(
                insert(ProcessingRun)
                .values(
                    id=run.id,
                    kind=run.kind,
                    inputs=run.inputs,
                    outputs=run.outputs,
                    features_sha256=run.features_sha256,
                    data_status=run.data_status,
                    code_version=run.code_version,
                    config_hash=run.config_hash,
                    schema_version=run.schema_version,
                    status=run.status,
                    error=run.error,
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        progress("runs loaded")

        for t in load_targets().values():
            try:
                prof = artifacts.read_target_profile(t.id, t.comparison.scale_m)
            except FileNotFoundError:
                continue
            s.execute(
                insert(PlanetaryTarget)
                .values(
                    id=t.id,
                    body=t.body.value,
                    name=t.name,
                    boundary_wkt=prof.footprint_wkt,
                    crs=prof.crs,
                    description=t.preview.note.strip(),
                    preview_uri=prof.preview_path,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            s.execute(
                insert(FeatureProfile)
                .values(
                    owner_type="target",
                    target_id=t.id,
                    schema_version=prof.schema_version,
                    scale_m=prof.scale_m,
                    values=prof.values,
                    availability=prof.availability,
                    source_asset_ids=[],
                    run_id=prof.run_id,
                )
                .on_conflict_do_nothing(constraint="uq_feature_profiles")
            )
        progress("targets loaded")

        for region in grid.regions:
            for scale in region.scales_m:
                try:
                    df, run = artifacts.read_features(region.id, scale)
                except FileNotFoundError:
                    continue
                known = set(
                    s.scalars(select(EarthCell.id).where(EarthCell.region_id == region.id)).all()
                )
                new_cells = []
                for cid in df["cell_id"].astype(int):
                    if cid in known:
                        continue
                    w = window_from_cell_id(grid, cid)
                    new_cells.append(
                        {
                            "id": cid,
                            "region_id": region.id,
                            "grid_version": grid.version,
                            "boundary": from_shape(window_lonlat_polygon(region, w), srid=4326),
                            "footprint_m": grid.window_m,
                        }
                    )
                if new_cells:
                    s.execute(insert(EarthCell), new_cells)
                profiles = []
                for row in df.to_dict(orient="records"):
                    values = {k: row[k] for k in PROFILE_KEYS + LANDCOVER_KEYS}
                    values["slope_hist"] = (
                        None
                        if values["slope_hist"] is None
                        else [float(x) for x in values["slope_hist"]]
                    )
                    values = {
                        k: (None if v is not None and not isinstance(v, list) and v != v else v)
                        for k, v in values.items()
                    }
                    profiles.append(
                        {
                            "owner_type": "cell",
                            "cell_id": int(row["cell_id"]),
                            "schema_version": row["feature_schema_version"],
                            "scale_m": scale,
                            "values": values,
                            "availability": {k: v is not None for k, v in values.items()},
                            "source_asset_ids": [],
                            "run_id": run.id,
                        }
                    )
                for i in range(0, len(profiles), 2000):
                    s.execute(
                        insert(FeatureProfile)
                        .values(profiles[i : i + 2000])
                        .on_conflict_do_nothing(constraint="uq_feature_profiles")
                    )
                progress(
                    f"{region.id} {scale} m: {len(new_cells)} new cells, {len(profiles)} profiles"
                )

        snap = artifacts.read_registry()
        if snap.loaded:
            s.execute(delete(KnownAnalog))
            for e in snap.entries:
                s.add(
                    KnownAnalog(
                        external_id=e.id,
                        name=e.name,
                        boundary=from_shape(shp_wkt.loads(e.geometry.wkt), srid=4326),
                        body_target_relevance=e.body_target_relevance,
                        citations=e.citations,
                        source=e.source,
                        registry_version=snap.version,
                        review_date=date.fromisoformat(snap.review_date),
                        boundary_note=e.boundary_note,
                    )
                )
            progress(f"registry loaded: {len(snap.entries)} entries ({snap.version})")
