"""In-process store. Evidence profiles come from the verified parquet of the same run."""

from __future__ import annotations

import copy
import threading
from typing import Any

import pandas as pd

from backend.store.base import ListName, check_transition
from core.artifacts import Artifacts, ChecksumMismatch, RegistrySnapshot, utcnow

PROFILE_COLUMNS = [
    "slope_median",
    "slope_p90",
    "slope_hist",
    "relief",
    "roughness",
    "valid_fraction",
    "water_fraction",
    "built_up_fraction",
    "snow_ice_fraction",
    "vegetation_fraction",
]


class MemoryStore:
    kind = "memory"

    def __init__(self, artifacts: Artifacts):
        self.artifacts = artifacts
        self._lock = threading.Lock()
        self._searches: dict[str, dict[str, Any]] = {}
        self._by_key: dict[str, str] = {}
        self._candidates: dict[str, dict[str, Any]] = {}
        self._reviews: dict[str, list[dict[str, Any]]] = {}

    def healthy(self) -> tuple[bool, str]:
        return True, "memory store (no database)"

    def find_search(self, cache_key: str) -> str | None:
        return self._by_key.get(cache_key)

    def save_search(
        self, search_id: str, cache_key: str, request: dict[str, Any], result: dict[str, Any]
    ) -> None:
        with self._lock:
            rec = {
                "id": search_id,
                "status": "completed",
                "request": request,
                "meta": result["meta"],
                "shortlist": result["shortlist"],
                "lists": {"candidates": [], "reference_matches": []},
            }
            for name in ("candidates", "reference_matches"):
                for c in result[name]:
                    c = copy.deepcopy(c)
                    c["search_id"] = search_id
                    self._candidates[c["id"]] = c
                    rec["lists"][name].append(c["id"])
            self._searches[search_id] = rec
            self._by_key[cache_key] = search_id

    def get_search(self, search_id: str) -> dict[str, Any] | None:
        s = self._searches.get(search_id)
        if s is None:
            return None
        return {"id": s["id"], "status": s["status"], "request": s["request"], "meta": s["meta"]}

    def list_candidates(
        self, search_id: str, list_name: ListName, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        s = self._searches[search_id]
        ids = s["lists"][list_name]
        return [copy.deepcopy(self._candidates[i]) for i in ids[offset : offset + limit]], len(ids)

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        c = self._candidates.get(candidate_id)
        return copy.deepcopy(c) if c else None

    def get_shortlist(self, search_id: str) -> list[dict[str, Any]]:
        return copy.deepcopy(self._searches[search_id]["shortlist"])

    def cell_profiles(
        self, cell_ids: list[int], scale_m: int, run_id: str
    ) -> dict[int, dict[str, Any]]:
        run = self.artifacts.read_run(run_id)
        if run.region_id is None:
            return {}
        df, current = self.artifacts.read_features(run.region_id, scale_m)
        if current.id != run_id:
            raise ChecksumMismatch(f"region now points at run {current.id}, search used {run_id}")
        rows = df.loc[df["cell_id"].isin(cell_ids)]
        out: dict[int, dict[str, Any]] = {}
        for row in rows.to_dict(orient="records"):
            values: dict[str, Any] = {}
            for c in PROFILE_COLUMNS:
                v = row.get(c)
                if c == "slope_hist":
                    values[c] = None if v is None else [float(x) for x in v]
                else:
                    values[c] = None if v is None or pd.isna(v) else float(v)
            out[int(row["cell_id"])] = {
                "values": values,
                "availability": {k: v is not None for k, v in values.items()},
                "schema_version": row.get("feature_schema_version"),
                "run_id": row.get("run_id"),
                "scale_m": scale_m,
                "source_asset_ids": run.source_asset_ids,
            }
        return out

    def registry(self) -> RegistrySnapshot:
        return self.artifacts.read_registry()

    def add_review(
        self,
        candidate_id: str,
        reviewer_id: str,
        decision: str,
        note: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            c = self._candidates[candidate_id]
            prev = c["novelty_status"]
            check_transition(prev, decision)
            c["novelty_status"] = decision
            rec = {
                "id": len(self._reviews.get(candidate_id, [])) + 1,
                "candidate_id": candidate_id,
                "reviewer_id": reviewer_id,
                "decision": decision,
                "previous_status": prev,
                "novelty_status": decision,
                "note": note,
                "evidence": evidence,
                "created_at": utcnow(),
            }
            self._reviews.setdefault(candidate_id, []).append(rec)
            return rec

    def list_reviews(self, candidate_id: str) -> list[dict[str, Any]]:
        return copy.deepcopy(self._reviews.get(candidate_id, []))
