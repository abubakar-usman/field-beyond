"""PostGIS store. Feature profiles and the registry are loaded by `pipeline load-db`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import CandidateMatch, FeatureProfile, KnownAnalog, ReviewRecord, SearchJob
from backend.store.base import ListName, check_transition
from core.artifacts import RegistryEntry, RegistrySnapshot


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True, future=True)


def _candidate_row(search_id: uuid.UUID, c: dict[str, Any]) -> CandidateMatch:
    return CandidateMatch(
        id=uuid.UUID(c["id"]),
        search_id=search_id,
        result_list=c["list"],
        rank=c["rank"],
        region_geom=from_shape(shape(c["geometry"]), srid=4326),
        member_cell_ids=[m["cell_id"] for m in c["members"]],
        member_scores={
            str(m["cell_id"]): {"score": m["score"], "geometry": m["geometry"]}
            for m in c["members"]
        },
        component_scores={
            "components": c["components"],
            "main_mismatch": c["main_mismatch"],
            "best_cell_id": c["best_cell_id"],
            "flags": c["flags"],
            "center": c["center"],
        },
        total_score=c["score"],
        novelty_status=c["novelty_status"],
        novelty=c["novelty"],
        explanation=c["explanation"],
    )


def _candidate_dict(row: CandidateMatch) -> dict[str, Any]:
    cs = row.component_scores
    return {
        "id": str(row.id),
        "search_id": str(row.search_id),
        "list": row.result_list,
        "rank": row.rank,
        "score": row.total_score,
        "best_cell_id": cs["best_cell_id"],
        "center": cs["center"],
        "geometry": to_shape(row.region_geom).__geo_interface__,
        "members": [
            {
                "cell_id": cid,
                "score": row.member_scores[str(cid)]["score"],
                "geometry": row.member_scores[str(cid)]["geometry"],
            }
            for cid in row.member_cell_ids
        ],
        "components": cs["components"],
        "main_mismatch": cs["main_mismatch"],
        "flags": cs["flags"],
        "novelty_status": row.novelty_status,
        "novelty": row.novelty,
        "explanation": row.explanation,
    }


class SqlStore:
    kind = "sql"

    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def healthy(self) -> tuple[bool, str]:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            return True, f"database ok (schema {version})"
        except Exception as exc:  # health check reports, never raises
            return False, f"database unavailable: {type(exc).__name__}"

    def find_search(self, cache_key: str) -> str | None:
        with self.Session() as s:
            row = s.scalars(
                select(SearchJob.id)
                .where(SearchJob.cache_key == cache_key, SearchJob.status == "completed")
                .order_by(SearchJob.created_at.desc())
            ).first()
            return str(row) if row else None

    def save_search(
        self, search_id: str, cache_key: str, request: dict[str, Any], result: dict[str, Any]
    ) -> None:
        sid = uuid.UUID(search_id)
        meta = dict(result["meta"])
        with self.Session.begin() as s:
            s.add(
                SearchJob(
                    id=sid,
                    cache_key=cache_key,
                    request=request,
                    scoring_version=meta["scoring_version"],
                    status="completed",
                    progress=1.0,
                    result_meta={"meta": meta, "shortlist": result["shortlist"]},
                    earth_run_id=None,  # run rows exist only after `pipeline load-db`; the id is in meta
                    finished_at=datetime.now(UTC),
                )
            )
            s.flush()
            for name in ("candidates", "reference_matches"):
                for c in result[name]:
                    s.add(_candidate_row(sid, c))

    def get_search(self, search_id: str) -> dict[str, Any] | None:
        with self.Session() as s:
            row = s.get(SearchJob, uuid.UUID(search_id))
            if row is None:
                return None
            return {
                "id": str(row.id),
                "status": row.status,
                "request": row.request,
                "meta": row.result_meta["meta"],
            }

    def list_candidates(
        self, search_id: str, list_name: ListName, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        sid = uuid.UUID(search_id)
        with self.Session() as s:
            where = (CandidateMatch.search_id == sid, CandidateMatch.result_list == list_name)
            total = s.scalar(select(func.count()).select_from(CandidateMatch).where(*where)) or 0
            rows = s.scalars(
                select(CandidateMatch)
                .where(*where)
                .order_by(CandidateMatch.rank)
                .offset(offset)
                .limit(limit)
            ).all()
            return [_candidate_dict(r) for r in rows], int(total)

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        try:
            cid = uuid.UUID(candidate_id)
        except ValueError:
            return None
        with self.Session() as s:
            row = s.get(CandidateMatch, cid)
            return _candidate_dict(row) if row else None

    def get_shortlist(self, search_id: str) -> list[dict[str, Any]]:
        with self.Session() as s:
            row = s.get(SearchJob, uuid.UUID(search_id))
            return list(row.result_meta.get("shortlist", [])) if row else []

    def cell_profiles(
        self, cell_ids: list[int], scale_m: int, run_id: str
    ) -> dict[int, dict[str, Any]]:
        with self.Session() as s:
            rows = s.scalars(
                select(FeatureProfile).where(
                    FeatureProfile.owner_type == "cell",
                    FeatureProfile.cell_id.in_(cell_ids),
                    FeatureProfile.scale_m == scale_m,
                    FeatureProfile.run_id == run_id,
                )
            ).all()
            return {
                int(r.cell_id): {  # type: ignore[arg-type]
                    "values": r.values,
                    "availability": r.availability,
                    "schema_version": r.schema_version,
                    "run_id": r.run_id,
                    "scale_m": r.scale_m,
                    "source_asset_ids": [str(x) for x in r.source_asset_ids],
                }
                for r in rows
            }

    def registry(self) -> RegistrySnapshot:
        with self.Session() as s:
            rows = s.scalars(select(KnownAnalog).order_by(KnownAnalog.id)).all()
        if not rows:
            return RegistrySnapshot.empty()
        versions = sorted({r.registry_version for r in rows})
        return RegistrySnapshot(
            version="+".join(versions),
            review_date=max(r.review_date for r in rows).isoformat(),
            sources_checked=sorted({r.source for r in rows}),
            entries=[
                RegistryEntry(
                    id=r.external_id or str(r.id),
                    name=r.name,
                    geometry=to_shape(r.boundary),
                    body_target_relevance=list(r.body_target_relevance),
                    citations=list(r.citations),
                    source=r.source,
                    boundary_note=r.boundary_note,
                )
                for r in rows
            ],
        )

    def add_review(
        self,
        candidate_id: str,
        reviewer_id: str,
        decision: str,
        note: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        cid = uuid.UUID(candidate_id)
        with self.Session.begin() as s:
            cand = s.get(CandidateMatch, cid, with_for_update=True)
            if cand is None:
                raise KeyError(candidate_id)
            prev = cand.novelty_status
            check_transition(prev, decision)
            cand.novelty_status = decision
            rec = ReviewRecord(
                candidate_id=cid,
                reviewer_id=reviewer_id,
                decision=decision,
                previous_status=prev,
                novelty_status=decision,
                note=note,
                evidence=evidence,
            )
            s.add(rec)
            s.flush()
            return _review_dict(rec)

    def list_reviews(self, candidate_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as s:
            rows = s.scalars(
                select(ReviewRecord)
                .where(ReviewRecord.candidate_id == uuid.UUID(candidate_id))
                .order_by(ReviewRecord.id)
            ).all()
            return [_review_dict(r) for r in rows]


def _review_dict(r: ReviewRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "candidate_id": str(r.candidate_id),
        "reviewer_id": r.reviewer_id,
        "decision": r.decision,
        "previous_status": r.previous_status,
        "novelty_status": r.novelty_status,
        "note": r.note,
        "evidence": r.evidence,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
