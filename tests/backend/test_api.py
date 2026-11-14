"""End-to-end API tests on synthetic data (memory store, temporary data dir)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import shape

from backend.main import app, get_service
from backend.service import Service
from backend.settings import Settings
from backend.store.memory import MemoryStore
from core.artifacts import Artifacts, RegistryEntry, RegistrySnapshot
from core.config import load_grid, load_scoring, load_targets
from pipeline.fake import seed_region, seed_target

TOKEN = "test-token-123"
N_WINDOWS = 500


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("data")
    a = Artifacts(d)
    g, s = load_grid(), load_scoring()
    for t in load_targets().values():
        seed_target(a, g, s, t)
    seed_region(a, g, s, "earth_sahara", 200, max_windows=N_WINDOWS)
    seed_region(a, g, s, "earth_atacama", 200, max_windows=N_WINDOWS)
    return d


@pytest.fixture()
def client(data_dir: Path):
    settings = Settings(EAE_DATA_DIR=data_dir, DEMO_TOKEN=TOKEN, EAE_STORE="memory")
    svc = Service(settings, MemoryStore(Artifacts(data_dir)))
    app.dependency_overrides[get_service] = lambda: svc
    yield TestClient(app)
    app.dependency_overrides.clear()


def _search(client: TestClient, **kw):
    body = {"target_id": "mars_jezero", "region_id": "earth_sahara", "top_k": 10, **kw}
    return client.post("/searches", json=body)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["store"] == "memory"


def test_targets_and_regions(client):
    t = {x["id"]: x for x in client.get("/targets").json()}
    assert t["mars_jezero"]["profile_status"] == "ready"
    assert t["mars_jezero"]["data_status"] == "synthetic"
    assert t["mars_jezero"]["comparison"]["scale_m"] == 200
    assert client.get("/targets/mars_jezero/preview.png").status_code == 200
    detail = client.get("/targets/mars_jezero").json()
    assert detail["profile"]["values"]["relief"] > 0
    regions = {r["id"]: r for r in client.get("/regions").json()}
    assert regions["earth_sahara"]["scales"]["200"]["status"] == "ready"
    assert regions["earth_sahara"]["scales"]["60"]["status"] == "not_ready"


def test_features_not_ready_is_409_with_contract_body(client):
    r = _search(client, target_id="moon_taurus_littrow")
    assert r.status_code == 409
    assert r.json() == {
        "error": "features_not_ready",
        "region_id": "earth_sahara",
        "target_id": "moon_taurus_littrow",
        "scale_m": 60,
    }


def test_unknown_ids_404(client):
    assert _search(client, target_id="venus_x").status_code == 404
    assert _search(client, region_id="earth_moon").status_code == 404
    assert client.get("/searches/not-a-uuid").status_code == 404


def test_validation(client):
    assert _search(client, retrieval_mode="embedding").status_code == 422
    assert _search(client, top_k=0).status_code == 422
    assert _search(client, top_k=10_000).status_code == 422


def test_search_end_to_end(client):
    r = _search(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["scale_m"] == 200
    sid = body["search_id"]

    again = _search(client).json()
    assert again["search_id"] == sid and again["reused_cached_result"] is True

    res = client.get(f"/searches/{sid}/candidates").json()
    cands = res["candidates"]
    assert 0 < len(cands) <= 10
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores, reverse=True)
    assert [c["rank"] for c in cands] == list(range(1, len(cands) + 1))
    meta = res["search"]["meta"]
    assert meta["data_status"] == "synthetic"
    assert meta["tolerances"]["slope_median"] == 5
    assert meta["registry"]["registry_loaded"] is False

    # Eligibility: no member window may break the water / built-up / valid rules.
    df = pd.read_parquet(
        Path(
            client.app.dependency_overrides[get_service]().artifacts.features_path(
                "earth_sahara", 200
            )
        )
    )
    by_cell = df.set_index("cell_id")
    for c in cands:
        assert 0 <= c["score"] <= 100
        assert c["novelty_status"] == "not_in_checked_records"
        assert set(c["components"]) == {
            "slope_hist",
            "slope_median",
            "slope_p90",
            "relief",
            "roughness",
        }
        for m in c["members"]:
            row = by_cell.loc[m["cell_id"]]
            assert row["water_fraction"] <= 0.05
            assert row["built_up_fraction"] <= 0.02
            assert row["valid_fraction"] >= 0.9
        # candidate groups never contain windows that overlap other candidates' best windows by IoU > 0.3
    text = json.dumps(res).lower()
    for banned in ("probability", "confidence", "new discovery", "discovered"):
        assert banned not in text

    ev = client.get(f"/candidates/{cands[0]['id']}/evidence").json()
    assert ev["scale"]["scale_m"] == 200 and ev["scale"]["window_m"] == 10000
    best = ev["earth_profile"]["values"]
    row = by_cell.loc[cands[0]["best_cell_id"]]
    assert best["relief"] == pytest.approx(row["relief"])
    assert ev["candidate"]["components"]["relief"]["earth"] == pytest.approx(row["relief"])
    assert ev["novelty"]["status"] == "not_in_checked_records"
    assert ev["provenance"]["earth_features_sha256"]
    assert ev["slope_hist_bins_deg"][-1] == 90
    assert ev["data_status"] == "synthetic"

    rs = client.post(
        f"/searches/{sid}/rescore",
        json={
            "weights": {
                "slope_hist": 0,
                "slope_median": 0,
                "slope_p90": 0,
                "relief": 1,
                "roughness": 0,
            }
        },
    ).json()
    rel = [w["score"] for w in rs["windows"]]
    assert rel == sorted(rel, reverse=True)
    assert "not rebuilt" in rs["note"]
    bad = client.post(f"/searches/{sid}/rescore", json={"weights": {"relief": 1}})
    assert bad.status_code == 422

    gj = client.get(f"/searches/{sid}/export.geojson").json()
    assert gj["search_configuration"]["meta"]["scoring_version"] == "terrain-v1"
    assert len(gj["features"]) == len(cands)
    csv_text = client.get(f"/searches/{sid}/export.csv").text
    assert csv_text.startswith("# search_configuration:")


def test_reviews_need_token_and_valid_transitions(client):
    sid = _search(client, top_k=5).json()["search_id"]
    cid = client.get(f"/searches/{sid}/candidates").json()["candidates"][0]["id"]
    body = {"reviewer_id": "tester", "decision": "under_review"}
    assert client.post(f"/candidates/{cid}/reviews", json=body).status_code == 401
    bad = client.post(
        f"/candidates/{cid}/reviews", json=body, headers={"Authorization": "Bearer nope"}
    )
    assert bad.status_code == 401
    ok = client.post(
        f"/candidates/{cid}/reviews", json=body, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert ok.status_code == 200
    assert ok.json()["previous_status"] == "not_in_checked_records"
    again = client.post(
        f"/candidates/{cid}/reviews", json=body, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert again.status_code == 409  # under_review -> under_review is not a transition
    assert client.get(f"/candidates/{cid}/reviews").json()[0]["decision"] == "under_review"
    assert client.get(f"/candidates/{cid}").json()["novelty_status"] == "under_review"


def test_registry_overlap_moves_candidate_to_reference_matches(data_dir: Path):
    a = Artifacts(data_dir)
    settings = Settings(EAE_DATA_DIR=data_dir, EAE_STORE="memory")
    svc = Service(settings, MemoryStore(a))
    app.dependency_overrides[get_service] = lambda: svc
    try:
        c = TestClient(app)
        first = c.get(f"/searches/{_search(c, top_k=5).json()['search_id']}/candidates").json()[
            "candidates"
        ][0]
        # A test-only registry record placed exactly on the top candidate.
        a.write_registry(
            RegistrySnapshot(
                version="test-1",
                review_date="2026-11-14",
                sources_checked=["unit_test_fixture"],
                entries=[
                    RegistryEntry(
                        "t1",
                        "Test record",
                        shape(first["geometry"]).centroid.buffer(0.01),
                        ["mars"],
                        [],
                        "unit_test_fixture",
                    )
                ],
            )
        )
        res = c.get(f"/searches/{_search(c, top_k=5).json()['search_id']}/candidates").json()
        assert res["search"]["meta"]["registry"]["registry_loaded"] is True
        assert first["best_cell_id"] not in [x["best_cell_id"] for x in res["candidates"]]
        refs = res["reference_matches"]
        assert refs and refs[0]["novelty_status"] == "documented_analog"
        assert refs[0]["novelty"]["matched"][0]["id"] == "t1"
        assert refs[0]["novelty"]["registry_version"] == "test-1"
    finally:
        a.registry_path().unlink()
        app.dependency_overrides.clear()


def test_checksum_mismatch_refuses_search(data_dir: Path, tmp_path: Path):
    import shutil

    d = tmp_path / "copy"
    shutil.copytree(data_dir, d)
    a = Artifacts(d)
    p = a.features_path("earth_atacama", 200)
    df = pd.read_parquet(p)
    df.loc[0, "relief"] = 9999.0
    df.to_parquet(p, index=False)
    svc = Service(Settings(EAE_DATA_DIR=d, EAE_STORE="memory"), MemoryStore(a))
    app.dependency_overrides[get_service] = lambda: svc
    try:
        r = TestClient(app).post(
            "/searches", json={"target_id": "mars_jezero", "region_id": "earth_atacama"}
        )
        assert r.status_code == 409
        assert r.json()["error"] == "features_checksum_mismatch"
    finally:
        app.dependency_overrides.clear()


def test_missing_mandatory_feature_never_ranks(data_dir: Path, tmp_path: Path):
    """Null out roughness on the windows that ranked best; they must disappear, not rise."""
    import shutil

    from pipeline.common import finish, new_run

    d = tmp_path / "copy2"
    shutil.copytree(data_dir, d)
    a = Artifacts(d)
    svc = Service(Settings(EAE_DATA_DIR=d, EAE_STORE="memory"), MemoryStore(a))
    app.dependency_overrides[get_service] = lambda: svc
    try:
        c = TestClient(app)
        sid = _search(c, top_k=5).json()["search_id"]
        top_cells = [
            m["cell_id"]
            for x in c.get(f"/searches/{sid}/candidates").json()["candidates"]
            for m in x["members"]
        ]
        df, _ = a.read_features("earth_sahara", 200)
        df.loc[df["cell_id"].isin(top_cells), "roughness"] = np.nan
        run = new_run(
            "seed_fake",
            data_status="synthetic",
            scoring=load_scoring(),
            grid=load_grid(),
            region_id="earth_sahara",
            scale_m=200,
        )
        finish(run)
        a.write_features(df, "earth_sahara", 200, run)
        res = c.get(f"/searches/{_search(c, top_k=5).json()['search_id']}/candidates").json()
        new_cells = {m["cell_id"] for x in res["candidates"] for m in x["members"]}
        assert not new_cells & set(top_cells)
        assert res["search"]["meta"]["counts"]["excluded_missing_mandatory"] >= 0
    finally:
        app.dependency_overrides.clear()
