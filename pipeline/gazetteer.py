"""Download the USGS gazetteer center-point files and write a target catalog."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from core.artifacts import Artifacts, utcnow
from core.config import load_gazetteer, load_targets
from core.gazetteer import select_features
from pipeline.adapters.base import fetch
from pipeline.common import finish, new_run

Progress = Callable[[str], None]


def parse_dbf(data: bytes, encoding: str = "utf-8") -> list[dict[str, str]]:
    """Read a dBase III table. The gazetteer files use character and numeric fields only."""
    if len(data) < 32 or data[0] not in range(0x03, 0x90):
        raise ValueError("not a dBase table")
    nrec = int.from_bytes(data[4:8], "little")
    hlen = int.from_bytes(data[8:10], "little")
    rlen = int.from_bytes(data[10:12], "little")
    if hlen < 33 or rlen < 2 or hlen + nrec * rlen > len(data):
        raise ValueError("dBase header does not match the file length")
    fields: list[tuple[str, int]] = []
    pos = 32
    while pos + 32 <= hlen and data[pos] != 0x0D:
        name = data[pos : pos + 11].split(b"\x00", 1)[0].decode("ascii")
        fields.append((name, data[pos + 16]))
        pos += 32
    rows: list[dict[str, str]] = []
    for i in range(nrec):
        rec = data[hlen + i * rlen : hlen + (i + 1) * rlen]
        if not rec or rec[0:1] == b"*":
            continue
        off = 1
        row: dict[str, str] = {}
        for name, length in fields:
            row[name] = rec[off : off + length].decode(encoding, errors="replace").strip()
            off += length
        rows.append(row)
    return rows


def read_center_points(path: Path) -> list[dict[str, str]]:
    with ZipFile(path) as zf:
        names = zf.namelist()
        dbf_name = next(n for n in names if n.lower().endswith(".dbf"))
        cpg = next((n for n in names if n.lower().endswith(".cpg")), None)
        encoding = "utf-8"
        if cpg:
            label = zf.read(cpg).decode("ascii", errors="replace").strip()
            if label:
                encoding = label
        return parse_dbf(zf.read(dbf_name), encoding)


def import_gazetteer(
    artifacts: Artifacts,
    scoring: Any,
    grid: Any,
    *,
    progress: Progress = print,
) -> dict[str, Any]:
    """Fetch each configured gazetteer file and write ``gazetteer/catalog.json``."""
    cfg = load_gazetteer()
    reserved = set(load_targets())
    run = new_run(
        "gazetteer_import",
        data_status="measured",
        scoring=scoring,
        grid=grid,
        inputs={"gazetteer_version": cfg.version, "reserved_target_ids": sorted(reserved)},
    )
    artifacts.write_run(run)
    targets: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    try:
        for body in cfg.bodies:
            dest = artifacts.gazetteer_raw_path(body.body.value)
            progress(f"fetch {body.body.value} gazetteer")
            sha = fetch(body.url, dest)
            rows = read_center_points(dest)
            kept = select_features(
                rows,
                body,
                cfg,
                reserved_ids=reserved,
                source_url=body.url,
                source_sha256=sha,
            )
            reserved.update(row["id"] for row in kept)
            targets.extend(kept)
            sources.append(
                {
                    "body": body.body.value,
                    "url": body.url,
                    "sha256": sha,
                    "rows": len(rows),
                    "kept": len(kept),
                }
            )
            progress(f"{body.body.value}: kept {len(kept)} of {len(rows)} names")
        targets.sort(key=lambda row: (row["body"], row["name"].lower(), row["id"]))
        catalog = {
            "version": cfg.version,
            "imported_at": utcnow(),
            "run_id": run.id,
            "sources": sources,
            "targets": targets,
        }
        artifacts.write_gazetteer_catalog(catalog)
        run.source_asset_ids = [f"{s['body']}:{s['sha256'][:12]}" for s in sources]
        finish(run, targets=len(targets), sources=sources)
        artifacts.write_run(run)
    except Exception as exc:
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"
        run.finished_at = utcnow()
        artifacts.write_run(run)
        raise
    progress(f"wrote {len(targets)} names to {artifacts.gazetteer_catalog_path()}")
    return catalog
