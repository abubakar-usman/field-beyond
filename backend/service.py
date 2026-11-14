"""Glue between the API, the pipeline artifacts, the store and the search engine."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from backend.search.engine import SearchParams, cache_key, run_search
from backend.settings import Settings
from backend.store.base import Store
from core.artifacts import ArtifactMissing, Artifacts, RunRecord, TargetProfileRecord
from core.config import (
    GridConfig,
    ScoringConfig,
    load_grid,
    load_scoring,
    load_target,
    load_targets,
)
from core.provenance import git_sha


class NotReady(Exception):
    def __init__(self, code: str, detail: dict[str, Any]):
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class _CachedFeatures:
    run_id: str
    mtime_ns: int
    df: pd.DataFrame
    run: RunRecord


class Service:
    def __init__(self, settings: Settings, store: Store, grid_version: str = "pilot-v1"):
        self.settings = settings
        self.store = store
        self.artifacts = Artifacts(settings.data_dir)
        self.grid: GridConfig = load_grid(grid_version)
        self.code_version = git_sha()
        self._features: dict[tuple[str, int], _CachedFeatures] = {}
        self._lock = threading.Lock()

    # -------------------------------------------------- inputs

    def scoring(self, version: str) -> ScoringConfig:
        try:
            return load_scoring(version)
        except FileNotFoundError as exc:
            raise NotReady("unknown_scoring_version", {"scoring_version": version}) from exc

    def target_profile(self, target_id: str) -> TargetProfileRecord:
        t = load_target(target_id)
        try:
            return self.artifacts.read_target_profile(target_id, t.comparison.scale_m)
        except ArtifactMissing as exc:
            raise NotReady(
                "target_not_ready", {"target_id": target_id, "scale_m": t.comparison.scale_m}
            ) from exc

    def features(self, region_id: str, scale_m: int) -> tuple[pd.DataFrame, RunRecord]:
        """Verified parquet for one region and scale, re-hashed whenever the file changes."""
        path: Path = self.artifacts.features_path(region_id, scale_m)
        try:
            mtime = path.stat().st_mtime_ns
            current = self.artifacts.current_run(region_id, scale_m)
        except (FileNotFoundError, ArtifactMissing) as exc:
            raise NotReady(
                "features_not_ready", {"region_id": region_id, "scale_m": scale_m}
            ) from exc
        key = (region_id, scale_m)
        with self._lock:
            cached = self._features.get(key)
            if cached and cached.mtime_ns == mtime and cached.run_id == current.id:
                return cached.df, cached.run
            df, run = self.artifacts.read_features(region_id, scale_m)  # raises ChecksumMismatch
            self._features[key] = _CachedFeatures(run.id, mtime, df, run)
            return df, run

    # -------------------------------------------------- catalogue

    def targets(self) -> list[dict[str, Any]]:
        out = []
        for t in load_targets().values():
            try:
                prof = self.artifacts.read_target_profile(t.id, t.comparison.scale_m)
                status, data_status = "ready", prof.data_status
                preview = self.artifacts.target_preview_path(t.id).exists()
            except ArtifactMissing:
                status, data_status, preview = "not_ready", None, False
            out.append(
                {
                    "id": t.id,
                    "body": t.body.value,
                    "name": t.name,
                    "comparison": t.comparison.model_dump(),
                    "preview": {
                        "bbox": t.preview.bbox.model_dump(),
                        "note": t.preview.note.strip(),
                    },
                    "preview_url": f"/targets/{t.id}/preview.png" if preview else None,
                    "profile_status": status,
                    "data_status": data_status,
                }
            )
        return out

    def regions(self) -> list[dict[str, Any]]:
        out = []
        for r in self.grid.regions:
            scales = {}
            for s in r.scales_m:
                try:
                    run = self.artifacts.current_run(r.id, s)
                    scales[str(s)] = {
                        "status": "ready" if run.status == "completed" else run.status,
                        "run_id": run.id,
                        "data_status": run.data_status,
                        "windows": run.outputs.get("windows"),
                    }
                except ArtifactMissing:
                    scales[str(s)] = {"status": "not_ready"}
            out.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "role": r.role,
                    "description": r.description.strip(),
                    "bbox": r.bbox.model_dump(),
                    "scales": scales,
                    "window_m": self.grid.window_m,
                    "stride_m": self.grid.stride_m,
                }
            )
        return out

    # -------------------------------------------------- search

    def search(self, req: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
        """Run (or reuse) a search. Returns (search_id, meta, reused)."""
        scoring = self.scoring(req["scoring_version"])
        try:
            self.grid.region(req["region_id"])
        except KeyError as exc:
            raise NotReady("unknown_region", {"region_id": req["region_id"]}) from exc
        try:
            load_target(req["target_id"])
        except KeyError as exc:
            raise NotReady("unknown_target", {"target_id": req["target_id"]}) from exc
        target = self.target_profile(req["target_id"])
        try:
            df, run = self.features(req["region_id"], target.scale_m)
        except NotReady as exc:
            exc.detail.setdefault("target_id", req["target_id"])
            raise
        top_k = req.get("top_k") or scoring.retrieval.top_k_default
        if top_k > self.settings.max_top_k:
            raise NotReady("top_k_too_large", {"max_top_k": self.settings.max_top_k})
        params = SearchParams(
            target_id=req["target_id"],
            region_id=req["region_id"],
            top_k=top_k,
            scoring_version=scoring.version,
            purpose=req.get("purpose", scoring.purpose),
            exclude_documented_analogs=req.get("exclude_documented_analogs", True),
            optional_feature_groups=list(req.get("optional_feature_groups", [])),
        )
        registry = self.store.registry()
        key = cache_key(params, target, run, registry)
        existing = self.store.find_search(key)
        if existing:
            found = self.store.get_search(existing)
            if found:
                return existing, found["meta"], True
        result = run_search(
            params,
            target=target,
            features=df,
            run=run,
            registry=registry,
            scoring=scoring,
            grid=self.grid,
        )
        result["meta"]["api_code_version"] = self.code_version
        result["meta"]["cache_key"] = key
        search_id = str(uuid.uuid4())
        self.store.save_search(search_id, key, {**req, "top_k": top_k}, result)
        return search_id, result["meta"], False
