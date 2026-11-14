"""FastAPI application. Run: `uv run uvicorn backend.main:app --reload`."""

from __future__ import annotations

import csv
import io
import json
import secrets
from functools import lru_cache
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.schemas import RescoreRequest, ReviewRequest, SearchRequest
from backend.search.engine import SearchRefused, rescore
from backend.service import NotReady, Service
from backend.settings import Settings, get_settings
from backend.store.base import InvalidTransition, Store
from core.artifacts import ArtifactMissing, ChecksumMismatch
from core.config import load_scoring

API_VERSION = "0.1.0"
EXPORT_NOTE = (
    "Scores are configured similarity under the stated scoring version, not a probability. "
    "'not_in_checked_records' means the place is not in the registry versions listed, not a new discovery."
)


def make_store(settings: Settings) -> Store:
    if settings.store == "sql":
        from backend.store.sql import SqlStore

        return SqlStore(settings.database_url)
    from backend.store.memory import MemoryStore
    from core.artifacts import Artifacts

    return MemoryStore(Artifacts(settings.data_dir))


@lru_cache(maxsize=1)
def _default_service() -> Service:
    settings = get_settings()
    return Service(settings, make_store(settings))


def get_service() -> Service:
    return _default_service()


def _error(status: int, code: str, detail: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, **(detail or {})})


def require_demo_token(
    authorization: str | None = Header(default=None), svc: Service = Depends(get_service)
) -> None:
    token = svc.settings.demo_token
    if token is None:
        raise HTTPException(
            status_code=503, detail="reviews are disabled: DEMO_TOKEN is not set on the server"
        )
    expected = f"Bearer {token.get_secret_value()}"
    if authorization is None or not secrets.compare_digest(
        authorization.encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="missing or wrong demo token")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Earth Analog Explorer API",
        version=API_VERSION,
        description=(
            "Finds Earth windows whose terrain measurements resemble a Moon or Mars target. "
            "Scores are configured similarity (terrain-v1), not probability."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(NotReady)
    async def _not_ready(_: Request, exc: NotReady) -> JSONResponse:
        status = 404 if exc.code.startswith("unknown_") else 409
        if exc.code == "top_k_too_large":
            status = 422
        return _error(status, exc.code, exc.detail)

    @app.exception_handler(SearchRefused)
    async def _refused(_: Request, exc: SearchRefused) -> JSONResponse:
        return _error(422, exc.code, exc.detail)

    @app.exception_handler(ChecksumMismatch)
    async def _checksum(_: Request, exc: ChecksumMismatch) -> JSONResponse:
        return _error(409, "features_checksum_mismatch", {"message": str(exc)})

    @app.exception_handler(InvalidTransition)
    async def _transition(_: Request, exc: InvalidTransition) -> JSONResponse:
        return _error(409, "invalid_review_transition", {"message": str(exc)})

    # ---------------------------------------------------------------- health

    @app.get("/health")
    def health(svc: Service = Depends(get_service)) -> JSONResponse:
        ok, detail = svc.store.healthy()
        body = {
            "status": "ok" if ok else "degraded",
            "store": svc.store.kind,
            "store_detail": detail,
            "code_version": svc.code_version,
            "api_version": API_VERSION,
        }
        return JSONResponse(status_code=200 if ok else 503, content=body)

    # ---------------------------------------------------------------- catalogue

    @app.get("/targets")
    def list_targets(svc: Service = Depends(get_service)) -> list[dict[str, Any]]:
        return svc.targets()

    @app.get("/targets/{target_id}")
    def get_target(target_id: str, svc: Service = Depends(get_service)) -> dict[str, Any]:
        match = [t for t in svc.targets() if t["id"] == target_id]
        if not match:
            raise NotReady("unknown_target", {"target_id": target_id})
        out = match[0]
        if out["profile_status"] == "ready":
            prof = svc.target_profile(target_id)
            out["profile"] = {
                "values": prof.values,
                "availability": prof.availability,
                "meta": prof.meta,
                "run_id": prof.run_id,
                "schema_version": prof.schema_version,
                "crs": prof.crs,
                "footprint_wkt": prof.footprint_wkt,
                "source_asset_ids": prof.source_asset_ids,
            }
        return out

    @app.get("/targets/{target_id}/preview.png")
    def target_preview(target_id: str, svc: Service = Depends(get_service)) -> FileResponse:
        path = svc.artifacts.target_preview_path(target_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="no preview image for this target")
        return FileResponse(path, media_type="image/png")

    @app.get("/regions")
    def list_regions(svc: Service = Depends(get_service)) -> list[dict[str, Any]]:
        return svc.regions()

    @app.get("/processing-runs/{run_id}")
    def get_run(run_id: str, svc: Service = Depends(get_service)) -> dict[str, Any]:
        try:
            return svc.artifacts.read_run(run_id).to_dict()
        except ArtifactMissing as exc:
            raise HTTPException(status_code=404, detail="unknown processing run") from exc

    @app.get("/registry")
    def get_registry(svc: Service = Depends(get_service)) -> dict[str, Any]:
        snap = svc.store.registry()
        return {
            "registry_version": snap.version,
            "review_date": snap.review_date,
            "sources_checked": snap.sources_checked,
            "registry_loaded": snap.loaded,
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": e.id,
                        "geometry": e.geometry.__geo_interface__,
                        "properties": {
                            "name": e.name,
                            "source": e.source,
                            "body_target_relevance": e.body_target_relevance,
                            "boundary_note": e.boundary_note,
                        },
                    }
                    for e in snap.entries
                ],
            },
        }

    # ---------------------------------------------------------------- searches

    @app.post("/searches")
    def create_search(body: SearchRequest, svc: Service = Depends(get_service)) -> dict[str, Any]:
        search_id, meta, reused = svc.search(body.model_dump())
        return {
            "search_id": search_id,
            "status": "completed",
            "reused_cached_result": reused,
            "scoring_version": meta["scoring_version"],
            "region_id": meta["region_id"],
            "target_id": meta["target_id"],
            "scale_m": meta["scale_m"],
        }

    def _search_or_404(svc: Service, search_id: str) -> dict[str, Any]:
        try:
            s = svc.store.get_search(search_id)
        except ValueError:
            s = None
        if s is None:
            raise HTTPException(status_code=404, detail="unknown search")
        return s

    @app.get("/searches/{search_id}")
    def get_search(search_id: str, svc: Service = Depends(get_service)) -> dict[str, Any]:
        return _search_or_404(svc, search_id)

    @app.get("/searches/{search_id}/candidates")
    def get_candidates(
        search_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        svc: Service = Depends(get_service),
    ) -> dict[str, Any]:
        s = _search_or_404(svc, search_id)
        cands, n_c = svc.store.list_candidates(search_id, "candidates", offset, limit)
        refs, n_r = svc.store.list_candidates(search_id, "reference_matches", 0, 200)
        return {
            "search": {
                "id": s["id"],
                "status": s["status"],
                "request": s["request"],
                "meta": s["meta"],
            },
            "candidates": cands,
            "reference_matches": refs,
            "pagination": {"offset": offset, "limit": limit, "total": n_c},
            "reference_total": n_r,
        }

    @app.post("/searches/{search_id}/rescore")
    def rescore_search(
        search_id: str, body: RescoreRequest, svc: Service = Depends(get_service)
    ) -> dict[str, Any]:
        s = _search_or_404(svc, search_id)
        scoring = load_scoring(s["meta"]["scoring_version"])
        result = {"meta": s["meta"], "shortlist": svc.store.get_shortlist(search_id)}
        windows = rescore(result, body.weights, scoring)
        return {
            "search_id": search_id,
            "weights": body.weights,
            "note": (
                "Re-weighted the stored shortlist only. The nearest-neighbour shortlist was not rebuilt, "
                f"and these weights are not the {scoring.version} defaults."
            ),
            "windows": windows,
        }

    @app.get("/searches/{search_id}/export.{fmt}")
    def export_search(
        search_id: str, fmt: Literal["geojson", "csv"], svc: Service = Depends(get_service)
    ) -> Response:
        s = _search_or_404(svc, search_id)
        cands, _ = svc.store.list_candidates(search_id, "candidates", 0, 10_000)
        refs, _ = svc.store.list_candidates(search_id, "reference_matches", 0, 10_000)
        rows = cands + refs
        config = {"request": s["request"], "meta": s["meta"], "note": EXPORT_NOTE}
        if fmt == "geojson":
            fc = {
                "type": "FeatureCollection",
                "search_configuration": config,
                "features": [
                    {
                        "type": "Feature",
                        "id": c["id"],
                        "geometry": c["geometry"],
                        "properties": {
                            "list": c["list"],
                            "rank": c["rank"],
                            "configured_similarity": c["score"],
                            "novelty_status": c["novelty_status"],
                            "main_mismatch": c["main_mismatch"],
                            "member_cell_ids": [m["cell_id"] for m in c["members"]],
                            "explanation": c["explanation"]["text"],
                        },
                    }
                    for c in rows
                ],
            }
            return Response(
                json.dumps(fc, default=str),
                media_type="application/geo+json",
                headers={
                    "Content-Disposition": f'attachment; filename="search-{search_id}.geojson"'
                },
            )
        buf = io.StringIO()
        buf.write(f"# search_configuration: {json.dumps(config, default=str)}\n")
        w = csv.writer(buf)
        feats = list(load_scoring(s["meta"]["scoring_version"]).mandatory_features)
        w.writerow(
            [
                "list",
                "rank",
                "candidate_id",
                "configured_similarity",
                "novelty_status",
                "center_lon",
                "center_lat",
                "main_mismatch",
                *[f"{f}_earth" for f in feats if f != "slope_hist"],
                *[f"{f}_similarity" for f in feats],
                "member_cell_ids",
            ]
        )
        for c in rows:
            comps = c["components"]
            w.writerow(
                [
                    c["list"],
                    c["rank"],
                    c["id"],
                    f"{c['score']:.3f}",
                    c["novelty_status"],
                    c["center"]["lon"],
                    c["center"]["lat"],
                    c["main_mismatch"],
                    *[comps[f]["earth"] for f in feats if f != "slope_hist"],
                    *[f"{comps[f]['similarity']:.3f}" for f in feats],
                    " ".join(str(m["cell_id"]) for m in c["members"]),
                ]
            )
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="search-{search_id}.csv"'},
        )

    # ---------------------------------------------------------------- candidates

    def _candidate_or_404(svc: Service, candidate_id: str) -> dict[str, Any]:
        c = svc.store.get_candidate(candidate_id)
        if c is None:
            raise HTTPException(status_code=404, detail="unknown candidate")
        return c

    @app.get("/candidates/{candidate_id}")
    def get_candidate(candidate_id: str, svc: Service = Depends(get_service)) -> dict[str, Any]:
        return _candidate_or_404(svc, candidate_id)

    @app.get("/candidates/{candidate_id}/evidence")
    def get_evidence(candidate_id: str, svc: Service = Depends(get_service)) -> dict[str, Any]:
        c = _candidate_or_404(svc, candidate_id)
        s = _search_or_404(svc, c["search_id"])
        meta = s["meta"]
        cell_ids = [m["cell_id"] for m in c["members"]]
        profiles = svc.store.cell_profiles(
            cell_ids, meta["scale_m"], meta["provenance"]["earth_run_id"]
        )
        target = svc.target_profile(meta["target_id"])
        best = profiles.get(c["best_cell_id"])
        missing_profiles = [cid for cid in cell_ids if cid not in profiles]
        return {
            "candidate": c,
            "search": {"id": s["id"], "request": s["request"]},
            "scale": {
                "scale_m": meta["scale_m"],
                "window_m": meta["window_m"],
                "scoring_version": meta["scoring_version"],
                "feature_schema_version": meta["feature_schema_version"],
            },
            "target": {
                "id": meta["target_id"],
                "name": meta["target_name"],
                "body": meta["target_body"],
                "values": target.values,
                "run_id": target.run_id,
                "data_status": target.data_status,
                "preview_url": f"/targets/{target.target_id}/preview.png"
                if svc.artifacts.target_preview_path(target.target_id).exists()
                else None,
            },
            "earth_profile": best,
            "member_profiles": {str(k): v for k, v in profiles.items()},
            "missing_profiles": missing_profiles,
            "slope_hist_bins_deg": meta["slope_hist_bins_deg"],
            "tolerances": meta["tolerances"],
            "weights": meta["weights"],
            "unavailable_evidence": meta.get("unavailable_evidence", []),
            "novelty": {"status": c["novelty_status"], **c["novelty"]},
            "provenance": meta["provenance"],
            "data_status": meta["data_status"],
            "reviews": svc.store.list_reviews(candidate_id),
        }

    @app.post("/candidates/{candidate_id}/reviews", dependencies=[Depends(require_demo_token)])
    def add_review(
        candidate_id: str, body: ReviewRequest, svc: Service = Depends(get_service)
    ) -> dict[str, Any]:
        _candidate_or_404(svc, candidate_id)
        return svc.store.add_review(
            candidate_id, body.reviewer_id, body.decision, body.note, dict(body.evidence)
        )

    @app.get("/candidates/{candidate_id}/reviews")
    def list_reviews(
        candidate_id: str, svc: Service = Depends(get_service)
    ) -> list[dict[str, Any]]:
        _candidate_or_404(svc, candidate_id)
        return svc.store.list_reviews(candidate_id)

    return app


app = create_app()
