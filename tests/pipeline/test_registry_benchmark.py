"""Registry import, the benchmark report, and export re-verification (Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pyproj import Geod

from backend.eval.benchmark import benchmark, kendall_tau, report_markdown
from backend.main import app, get_service
from backend.service import Service
from backend.settings import Settings
from backend.store.memory import MemoryStore
from core.artifacts import Artifacts
from core.config import load_grid, load_scoring, load_target, load_targets
from pipeline.fake import seed_region, seed_target
from pipeline.registry import geodesic_buffer, import_registry, relevance_tokens


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("bench")
    a = Artifacts(d)
    g, s = load_grid(), load_scoring()
    for t in load_targets().values():
        seed_target(a, g, s, t)
    seed_region(a, g, s, "earth_atacama", 200, max_windows=400)
    return d


def test_geodesic_buffer_radius():
    circle = geodesic_buffer(-68.0, -22.0, 10_000)
    geod = Geod(ellps="WGS84")
    for lon, lat in list(circle.exterior.coords)[::8]:
        _, _, dist = geod.inv(-68.0, -22.0, lon, lat)
        assert dist == pytest.approx(10_000, rel=1e-3)


def test_relevance_tokens():
    assert relevance_tokens("Mars; Jezero crater, MOON") == ["crater", "jezero", "mars", "moon"]
    assert relevance_tokens(None) == []


def test_import_csv_buffers_points_and_records_assumption(tmp_path: Path):
    csv = tmp_path / "sites.csv"
    csv.write_text(
        "site_id,Site Name,Lat,Lon,Planetary Body,Reference\n"
        "A1,Test site one,-22.5,-68.2,Mars,Doe 2020\n"
        "A2,No coordinates,,,Moon,\n",
        encoding="utf-8",
    )
    a = Artifacts(tmp_path / "data")
    snap = import_registry(
        a,
        csv,
        source="fixture",
        version="fx-1",
        review_date="2026-11-14",
        name_col="Site Name",
        lat_col="Lat",
        lon_col="Lon",
        id_col="site_id",
        relevance_cols=["Planetary Body"],
        ref_cols=["Reference"],
        buffer_m=5_000,
    )
    assert len(snap.entries) == 1  # the record without coordinates cannot be checked spatially
    e = snap.entries[0]
    assert e.id == "A1" and e.body_target_relevance == ["mars"]
    assert "5 km radius" in e.boundary_note and "assumption" in e.boundary_note
    assert e.citations == [{"field": "Reference", "value": "Doe 2020"}]
    again = a.read_registry()
    assert again.version == "fx-1" and again.sources_checked == ["fixture"]
    assert again.entries[0].geometry.equals_exact(e.geometry, 1e-9)


def test_benchmark_report(data_dir: Path, tmp_path: Path):
    a = Artifacts(data_dir)
    s, g = load_scoring(), load_grid()
    df, _ = a.read_features("earth_atacama", 200)
    # A test-only registry with one Mars record on the first window and one Moon record.
    first = df.iloc[0]
    csv = tmp_path / "r.csv"
    csv.write_text(
        "name,latitude,longitude,rel\n"
        f"Mars-relevant fixture,{first.center_lat},{first.center_lon},mars terrain\n"
        f"Moon fixture,{first.center_lat},{first.center_lon},moon\n",
        encoding="utf-8",
    )
    reg_dir = Artifacts(tmp_path / "reg")
    snap = import_registry(
        reg_dir,
        csv,
        source="fixture",
        version="fx",
        review_date="2026-11-14",
        relevance_cols=["rel"],
        buffer_m=2_000,
    )
    b = benchmark(
        df,
        a.read_target_profile("mars_jezero", 200),
        load_target("mars_jezero"),
        snap,
        s,
        g,
        "earth_atacama",
        top_k=10,
    )
    assert [p["name"] for p in b["positives"]] == [
        "Mars-relevant fixture"
    ]  # moon record is not a Jezero positive
    assert b["positives"][0]["best_rank"] is not None
    assert len(b["sensitivity"]) == 20
    assert b["negative_controls"]["relief_below_m"] == 30
    md = report_markdown(b)
    assert "not a pipeline failure" in md and "probability" in md  # says what the score is not
    assert "Recall@10" in md


def test_kendall_tau():
    assert kendall_tau([1, 2, 3], [1, 2, 3]) == 1
    assert kendall_tau([1, 2, 3], [3, 2, 1]) == -1


def test_verify_export_round_trip(data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from typer.testing import CliRunner

    import backend.settings as bs
    from pipeline.cli import app as cli

    svc = Service(
        Settings(EAE_DATA_DIR=data_dir, EAE_STORE="memory"), MemoryStore(Artifacts(data_dir))
    )
    app.dependency_overrides[get_service] = lambda: svc
    try:
        c = TestClient(app)
        sid = c.post(
            "/searches", json={"target_id": "mars_jezero", "region_id": "earth_atacama", "top_k": 5}
        ).json()["search_id"]
        export = tmp_path / "export.geojson"
        export.write_text(c.get(f"/searches/{sid}/export.geojson").text, encoding="utf-8")
    finally:
        app.dependency_overrides.clear()
    monkeypatch.setenv("EAE_DATA_DIR", str(data_dir))
    bs.get_settings.cache_clear()
    try:
        result = CliRunner().invoke(cli, ["verify-export", str(export)])
        assert result.exit_code == 0, result.output
        assert "identical" in result.output
        fc = json.loads(export.read_text(encoding="utf-8"))
        fc["features"][0]["properties"]["configured_similarity"] += 1
        export.write_text(json.dumps(fc), encoding="utf-8")
        bad = CliRunner().invoke(cli, ["verify-export", str(export)])
        assert bad.exit_code == 1 and "differ" in bad.output
    finally:
        bs.get_settings.cache_clear()
