"""Gazetteer selection uses a synthetic dBase table, not the network."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from backend.service import Service
from backend.settings import Settings
from backend.store.memory import MemoryStore
from core.artifacts import Artifacts
from core.config import GazetteerFile, load_gazetteer, load_grid, load_scoring
from core.gazetteer import feature_to_target, select_features, to_east_180
from pipeline.gazetteer import import_gazetteer, parse_dbf


def _dbf(rows: list[dict[str, str]]) -> bytes:
    fields = [
        ("name", 24),
        ("clean_name", 24),
        ("approval", 32),
        ("diameter", 12),
        ("center_lon", 12),
        ("center_lat", 12),
        ("type", 24),
        ("min_lon", 12),
        ("max_lon", 12),
        ("min_lat", 12),
        ("max_lat", 12),
        ("link", 48),
    ]
    nrec = len(rows)
    hlen = 32 + 32 * len(fields) + 1
    rlen = 1 + sum(length for _, length in fields)
    buf = bytearray(hlen + nrec * rlen)
    buf[0] = 0x03
    buf[4:8] = nrec.to_bytes(4, "little")
    buf[8:10] = hlen.to_bytes(2, "little")
    buf[10:12] = rlen.to_bytes(2, "little")
    for i, (name, length) in enumerate(fields):
        at = 32 + 32 * i
        buf[at : at + len(name)] = name.encode("ascii")
        buf[at + 11] = ord("C")
        buf[at + 16] = length
    buf[hlen - 1] = 0x0D
    for i, row in enumerate(rows):
        rec = bytearray(b" " * rlen)
        off = 1
        for name, length in fields:
            raw = row.get(name, "").encode("utf-8")[:length]
            rec[off : off + len(raw)] = raw
            off += length
        start = hlen + i * rlen
        buf[start : start + rlen] = rec
    return bytes(buf)


def _row(**kw: str) -> dict[str, str]:
    base = {
        "name": "Sample",
        "clean_name": "Sample",
        "approval": "Adopted by IAU",
        "diameter": "20",
        "center_lon": "10",
        "center_lat": "0",
        "type": "Crater, craters",
        "min_lon": "9",
        "max_lon": "11",
        "min_lat": "-1",
        "max_lat": "1",
        "link": "http://planetarynames.wr.usgs.gov/Feature/1",
    }
    base.update(kw)
    return base


def _body(name: str) -> GazetteerFile:
    return next(b for b in load_gazetteer().bodies if b.body.value == name)


def test_dbf_round_trip_and_filters():
    raw = _dbf(
        [
            _row(
                name="Jezero",
                clean_name="Jezero",
                diameter="47.5212",
                center_lat="18.4082",
                center_lon="77.6873",
                min_lon="77.0",
                max_lon="78.3",
                min_lat="18.0",
                max_lat="18.8",
            ),
            _row(name="Twin", clean_name="Twin", center_lon="10"),
            _row(name="Twin", clean_name="Twin", center_lon="11"),
            _row(name="West", clean_name="West", center_lon="312"),
            _row(name="Tiny", clean_name="Tiny", diameter="5"),
            _row(name="Huge", clean_name="Huge", diameter="100"),
            _row(name="Olympus", clean_name="Olympus", type="Mons, montes"),
            _row(name="Pending", clean_name="Pending", approval="Provisional"),
            _row(name="Polar", clean_name="Polar", center_lat="70"),
            _row(name="Anio Valles", clean_name="Anio Valles", type="Vallis, valles"),
            _row(
                name="Jezero",
                clean_name="Jezero",
                type="Crater, craters",
                center_lat="18.4",
                center_lon="77.6",
            ),
        ]
    )
    rows = parse_dbf(raw)
    assert rows[0]["clean_name"] == "Jezero"
    assert to_east_180(312) == -48
    cfg = load_gazetteer()
    mars = select_features(
        rows,
        _body("mars"),
        cfg,
        reserved_ids={"mars_jezero_crater"},
        source_url="https://example.invalid/mars.zip",
        source_sha256="a" * 64,
    )
    ids = [r["id"] for r in mars]
    assert "mars_jezero_crater" not in ids  # curated-style reservation wins
    assert "mars_twin_crater" in ids
    assert "mars_twin_crater_2" in ids
    west = next(r for r in mars if r["id"] == "mars_west_crater")
    assert west["center_lon"] == -48
    assert "mars_tiny_crater" not in ids
    assert "mars_huge_crater" not in ids
    assert "mars_olympus_mons" not in ids
    assert "mars_pending_crater" not in ids
    assert "mars_polar_crater" in ids
    moon = select_features(
        rows,
        _body("moon"),
        cfg,
        reserved_ids=set(),
        source_url="https://example.invalid/moon.zip",
        source_sha256="b" * 64,
    )
    moon_ids = {r["id"] for r in moon}
    assert "moon_polar_crater" not in moon_ids
    assert "moon_jezero_crater" in moon_ids
    valles = next(r for r in mars if r["id"] == "mars_anio_valles_vallis")
    assert valles["name"] == "Anio Valles"
    target = feature_to_target(west)
    assert target.comparison.footprint_m == 10000
    assert target.comparison.scale_m == 200
    assert target.preview.bbox.west < target.preview.bbox.east


def test_import_writes_catalog(tmp_path: Path, monkeypatch):
    zpath = tmp_path / "points.zip"
    with ZipFile(zpath, "w") as zf:
        zf.writestr("points.cpg", "UTF-8")
        zf.writestr(
            "points.dbf",
            _dbf(
                [
                    _row(
                        name="Gale",
                        clean_name="Gale",
                        diameter="154",  # outside 10–60, dropped
                    ),
                    _row(name="Gusev", clean_name="Gusev", diameter="30", center_lat="-14.5"),
                ]
            ),
        )

    def fake_fetch(url: str, dest: Path) -> str:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zpath.read_bytes())
        return "c" * 64

    monkeypatch.setattr("pipeline.gazetteer.fetch", fake_fetch)
    artifacts = Artifacts(tmp_path / "data")
    catalog = import_gazetteer(artifacts, load_scoring(), load_grid(), progress=lambda _m: None)
    ids = {row["id"] for row in catalog["targets"]}
    assert ids == {"mars_gusev_crater", "moon_gusev_crater"}
    assert "mars_gale_crater" not in ids
    saved = artifacts.read_gazetteer_catalog()
    assert saved is not None
    assert saved["sources"][0]["kept"] == 1
    run = artifacts.read_run(catalog["run_id"])
    assert run.status == "completed"
    assert run.data_status == "measured"

    settings = Settings(EAE_DATA_DIR=tmp_path / "data", EAE_STORE="memory")
    svc = Service(settings, MemoryStore(artifacts))
    listed = {row["id"]: row for row in svc.targets()}
    assert listed["mars_jezero"]["origin"] == "curated"
    assert listed["mars_gusev_crater"]["origin"] == "iau_gazetteer"
    assert listed["mars_gusev_crater"]["profile_status"] == "not_ready"
    assert listed["mars_gusev_crater"]["feature_type"] == "Crater"
    assert svc.resolve_target("mars_gusev_crater").comparison.center_lat == -14.5
