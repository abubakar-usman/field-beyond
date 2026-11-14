"""Shared pipeline helpers: run records, feature rows, parquet assembly."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.artifacts import DataStatus, RunRecord, utcnow
from core.config import GridConfig, ScoringConfig, run_config_hash
from core.features import FEATURE_SCHEMA_VERSION, TerrainProfile
from core.grid import Window, window_center_lonlat, window_lonlat_polygon
from core.provenance import git_sha


def new_run(
    kind: str,
    *,
    data_status: DataStatus,
    scoring: ScoringConfig,
    grid: GridConfig,
    region_id: str | None = None,
    target_id: str | None = None,
    scale_m: int | None = None,
    inputs: dict[str, Any] | None = None,
) -> RunRecord:
    if scoring.feature_schema_version != FEATURE_SCHEMA_VERSION:
        raise RuntimeError(
            f"scoring config expects {scoring.feature_schema_version}, code computes {FEATURE_SCHEMA_VERSION}"
        )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return RunRecord(
        id=f"{kind}-{stamp}-{uuid.uuid4().hex[:8]}",
        kind=kind,
        status="running",
        code_version=git_sha(),
        config_hash=run_config_hash(scoring.version, grid.version),
        schema_version=FEATURE_SCHEMA_VERSION,
        data_status=data_status,
        region_id=region_id,
        target_id=target_id,
        scale_m=scale_m,
        grid_version=grid.version,
        inputs=inputs or {},
    )


def feature_row(
    w: Window,
    region: Any,
    scale_m: int,
    profile: TerrainProfile,
    landcover: dict[str, float | None],
    run_id: str,
) -> dict[str, Any]:
    lon, lat = window_center_lonlat(region, w)
    minx, miny, maxx, maxy = window_lonlat_polygon(region, w).bounds
    v = profile.values
    return {
        "cell_id": w.cell_id,
        "region_id": w.region_id,
        "scale_m": scale_m,
        "center_lon": lon,
        "center_lat": lat,
        "min_lon": minx,
        "min_lat": miny,
        "max_lon": maxx,
        "max_lat": maxy,
        "slope_median": v["slope_median"],
        "slope_p90": v["slope_p90"],
        "slope_hist": v["slope_hist"],
        "relief": v["relief"],
        "roughness": v["roughness"],
        "valid_fraction": v["valid_fraction"],
        "water_fraction": landcover.get("water_fraction"),
        "built_up_fraction": landcover.get("built_up_fraction"),
        "snow_ice_fraction": landcover.get("snow_ice_fraction"),
        "vegetation_fraction": landcover.get("vegetation_fraction"),
        "feature_schema_version": profile.schema_version,
        "run_id": run_id,
    }


def rows_to_frame(rows: Iterable[dict[str, Any]], scoring: ScoringConfig) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    missing = [c for c in scoring.parquet.columns if c not in df.columns]
    if missing:
        raise RuntimeError(f"feature rows lack contract columns {missing}")
    df = df[scoring.parquet.columns]
    # Availability must match nulls: there is no fill value anywhere.
    return df.sort_values("cell_id", kind="mergesort").reset_index(drop=True)


def finish(run: RunRecord, **outputs: Any) -> RunRecord:
    run.status = "completed"
    run.finished_at = utcnow()
    run.outputs.update(outputs)
    return run
