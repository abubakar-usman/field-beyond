"""One search: filter -> shortlist -> score -> group -> novelty -> explain.

Pure with respect to its inputs (features dataframe, target profile, registry
snapshot, configs), so it runs the same in the API, in tests and in the
benchmark.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from shapely.geometry import mapping
from shapely.ops import unary_union

from backend.search.explain import explain
from backend.search.filter import eligibility
from backend.search.novelty import NoveltyChecker
from backend.search.retrieve import IndexStats, shortlist
from core.artifacts import RegistrySnapshot, RunRecord, TargetProfileRecord, utcnow
from core.config import GridConfig, ScoringConfig, TargetConfig, load_target
from core.grid import window_center_lonlat, window_from_cell_id, window_lonlat_polygon
from core.provenance import stable_json_hash
from core.scoring import WindowScore, absolute_tolerances, missing_mandatory, score_window
from core.scoring.grouping import Group, ScoredWindow, group_windows

FLAG_COLUMNS = [
    "valid_fraction",
    "water_fraction",
    "built_up_fraction",
    "snow_ice_fraction",
    "vegetation_fraction",
]
OPTIONAL_GROUPS_NOT_IN_V1 = {
    "geology": "Geology",
    "thermal": "Thermal",
    "mineralogy": "Mineralogy",
    "illumination": "Illumination",
}


class SearchRefused(Exception):
    def __init__(self, code: str, detail: dict[str, Any]):
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class SearchParams:
    target_id: str
    region_id: str
    top_k: int
    scoring_version: str
    purpose: str = "exposed_terrain"
    exclude_documented_analogs: bool = True
    optional_feature_groups: list[str] = field(default_factory=list)
    weights: dict[str, float] | None = None


def _row_values(
    row: Mapping[Any, Any], cfg: ScoringConfig
) -> tuple[dict[str, Any], dict[str, bool]]:
    vals: dict[str, Any] = {}
    avail: dict[str, bool] = {}
    for f in cfg.mandatory_features:
        v: Any = row.get(f)
        if f == cfg.histogram_feature:
            ok = (
                v is not None
                and not (isinstance(v, float) and np.isnan(v))
                and len(v) == cfg.n_hist_bins
            )
            vals[f] = [float(x) for x in v] if ok else None
        else:
            ok = v is not None and not pd.isna(v)
            vals[f] = float(v) if ok else None
        avail[f] = bool(ok)
    return vals, avail


def cache_key(
    params: SearchParams, target: TargetProfileRecord, run: RunRecord, registry: RegistrySnapshot
) -> str:
    return stable_json_hash(
        {
            "target_profile": [target.target_id, target.run_id, target.scale_m],
            "earth_features": [run.id, run.features_sha256],
            "filters": [params.region_id, params.purpose, params.exclude_documented_analogs],
            "scoring_version": params.scoring_version,
            "top_k": params.top_k,
            "weights": params.weights,
            "registry": [registry.version, registry.review_date],
            "optional": sorted(params.optional_feature_groups),
        }
    )


def _components_dict(ws: WindowScore) -> dict[str, dict[str, Any]]:
    return {f: c.to_dict() for f, c in ws.components.items()}


def run_search(
    params: SearchParams,
    *,
    target: TargetProfileRecord,
    features: pd.DataFrame,
    run: RunRecord,
    registry: RegistrySnapshot,
    scoring: ScoringConfig,
    grid: GridConfig,
    target_config: TargetConfig | None = None,
) -> dict[str, Any]:
    """Return a JSON-serialisable result: meta, candidates, reference_matches, shortlist."""
    if params.scoring_version != scoring.version:
        raise SearchRefused("scoring_version_mismatch", {"requested": params.scoring_version})
    if params.purpose != scoring.purpose:
        raise SearchRefused(
            "unknown_purpose", {"purpose": params.purpose, "supported": [scoring.purpose]}
        )
    if run.grid_version != grid.version:
        raise SearchRefused(
            "grid_version_mismatch", {"run": run.grid_version, "config": grid.version}
        )
    if run.scale_m != target.scale_m:
        raise SearchRefused(
            "scale_mismatch", {"features_scale_m": run.scale_m, "target_scale_m": target.scale_m}
        )
    if run.schema_version != target.schema_version:
        raise SearchRefused(
            "feature_schema_mismatch",
            {"earth": run.schema_version, "target": target.schema_version},
        )
    target_missing = missing_mandatory(target.values, target.availability, scoring)
    if target_missing:
        raise SearchRefused("target_profile_incomplete", {"missing": target_missing})

    weights = dict(params.weights) if params.weights else dict(scoring.weights)
    if set(weights) != set(scoring.mandatory_features) or any(w < 0 for w in weights.values()):
        raise SearchRefused("bad_weights", {"expected_keys": scoring.mandatory_features})
    tolerances = absolute_tolerances(target.values, scoring)
    region = grid.region(params.region_id)
    tcfg = target_config or load_target(params.target_id)

    df = features.loc[features["region_id"] == params.region_id].copy()
    reasons = eligibility(df, scoring)
    eligible = df.loc[reasons == ""]
    short, stats = shortlist(eligible, target.values, scoring, params.top_k)

    scored: list[tuple[ScoredWindow, WindowScore, dict[Any, Any]]] = []
    shortlist_rows: list[dict[str, Any]] = []
    excluded_missing = 0
    for row in short.to_dict(orient="records"):
        vals, avail = _row_values(row, scoring)
        ws = score_window(vals, avail, target.values, tolerances, scoring, weights)
        if ws.total is None:
            excluded_missing += 1
            continue
        w = window_from_cell_id(grid, int(row["cell_id"]))
        scored.append((ScoredWindow(int(row["cell_id"]), ws.total, w.laea_box), ws, row))
        shortlist_rows.append(
            {
                "cell_id": int(row["cell_id"]),
                "values": vals,
                "flags": {
                    c: (None if pd.isna(row.get(c)) else float(row[c])) for c in FLAG_COLUMNS
                },
                "retrieval_distance": float(row["retrieval_distance"]),
                "score": ws.total,
            }
        )

    by_cell = {sw.cell_id: (ws, row) for sw, ws, row in scored}
    groups = group_windows([sw for sw, _, _ in scored], scoring.grouping.nms_iou_above)
    checker = NoveltyChecker(registry)
    registry_info = checker.describe()

    unavailable = [
        f"{OPTIONAL_GROUPS_NOT_IN_V1.get(g, g.title())} (not part of {scoring.version})"
        for g in params.optional_feature_groups
    ]

    def build(group: Group) -> dict[str, Any]:
        best = group.best
        ws, row = by_cell[best.cell_id]
        members_ll = []
        for m in group.members:
            w = window_from_cell_id(grid, m.cell_id)
            poly = window_lonlat_polygon(region, w)
            members_ll.append((m, poly))
        geom_ll = unary_union([p for _, p in members_ll])
        nov = checker.check(geom_ll)
        comps = _components_dict(ws)
        lon, lat = window_center_lonlat(region, window_from_cell_id(grid, best.cell_id))
        return {
            "id": str(uuid.uuid4()),
            "score": group.score,
            "best_cell_id": best.cell_id,
            "center": {"lon": lon, "lat": lat},
            "geometry": mapping(geom_ll),
            "members": [
                {"cell_id": m.cell_id, "score": m.score, "geometry": mapping(p)}
                for m, p in members_ll
            ],
            "components": comps,
            "main_mismatch": ws.main_mismatch,
            "flags": {c: (None if pd.isna(row.get(c)) else float(row[c])) for c in FLAG_COLUMNS},
            "novelty_status": nov.status,
            "novelty": {**registry_info, "matched": nov.matched},
            "explanation": explain(
                comps,
                ws.main_mismatch,
                scale_m=target.scale_m,
                window_m=grid.window_m,
                target_name=tcfg.name,
                unavailable=unavailable,
                scoring_version=scoring.version,
            ),
        }

    built = [build(g) for g in groups]
    documented = [c for c in built if c["novelty_status"] == "documented_analog"]
    if params.exclude_documented_analogs and scoring.novelty.exclude_documented_from_candidates:
        candidates = [c for c in built if c["novelty_status"] != "documented_analog"]
    else:
        candidates = list(built)
    candidates = candidates[: params.top_k]
    for i, c in enumerate(candidates, 1):
        c["rank"] = i
        c["list"] = "candidates"
    references = []
    for i, c in enumerate(documented, 1):
        ref = dict(c, id=str(uuid.uuid4())) if c in candidates else c
        ref["rank"] = i
        ref["list"] = "reference_matches"
        references.append(ref)

    data_status = (
        "synthetic" if "synthetic" in (run.data_status, target.data_status) else "measured"
    )
    meta = {
        "target_id": params.target_id,
        "target_name": tcfg.name,
        "target_body": tcfg.body.value,
        "region_id": params.region_id,
        "region_name": region.name,
        "scale_m": target.scale_m,
        "window_m": grid.window_m,
        "purpose": params.purpose,
        "top_k": params.top_k,
        "scoring_version": scoring.version,
        "feature_schema_version": run.schema_version,
        "weights": weights,
        "weights_are_default": weights == dict(scoring.weights),
        "tolerances": tolerances,
        "slope_hist_bins_deg": scoring.slope_hist_bins_deg,
        "target_values": target.values,
        "index_stats": stats.to_dict(),
        "counts": {
            "windows_in_region": len(df),
            "eligible": len(eligible),
            "ineligible_by_reason": {
                k: int(v) for k, v in reasons[reasons != ""].value_counts().items()
            },
            "shortlist": len(short),
            "excluded_missing_mandatory": excluded_missing,
            "scored": len(scored),
            "groups": len(groups),
        },
        "registry": registry_info,
        "provenance": {
            "earth_run_id": run.id,
            "earth_features_sha256": run.features_sha256,
            "earth_code_version": run.code_version,
            "earth_config_hash": run.config_hash,
            "target_run_id": target.run_id,
            "target_source_asset_ids": target.source_asset_ids,
            "earth_source_asset_ids": run.source_asset_ids,
            "grid_version": grid.version,
        },
        "data_status": data_status,
        "unavailable_evidence": unavailable,
        "created_at": utcnow(),
    }
    return {
        "meta": meta,
        "candidates": candidates,
        "reference_matches": references,
        "shortlist": shortlist_rows,
    }


def rescore(
    result: Mapping[str, Any], weights: Mapping[str, float], scoring: ScoringConfig
) -> list[dict[str, Any]]:
    """Re-weight the stored shortlist without a new nearest-neighbour search (D-020).

    Returns windows (not regrouped candidates) ordered by the new score.
    """
    if set(weights) != set(scoring.mandatory_features) or any(w < 0 for w in weights.values()):
        raise SearchRefused("bad_weights", {"expected_keys": scoring.mandatory_features})
    meta = result["meta"]
    target = meta["target_values"]
    tol = meta["tolerances"]
    out = []
    for row in result["shortlist"]:
        avail = {k: v is not None for k, v in row["values"].items()}
        ws = score_window(row["values"], avail, target, tol, scoring, weights)
        if ws.total is not None:
            out.append(
                {"cell_id": row["cell_id"], "score": ws.total, "main_mismatch": ws.main_mismatch}
            )
    out.sort(key=lambda r: (-r["score"], r["cell_id"]))
    return out


__all__ = ["IndexStats", "SearchParams", "SearchRefused", "cache_key", "rescore", "run_search"]
