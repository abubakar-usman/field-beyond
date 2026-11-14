"""`pipeline` command line. Run `uv run pipeline --help`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from backend.settings import get_settings
from core.artifacts import Artifacts
from core.config import (
    load_grid,
    load_scoring,
    load_sources,
    load_target,
    load_targets,
    run_config_hash,
)
from core.provenance import git_sha

app = typer.Typer(help="Earth Analog Explorer offline pipeline.", no_args_is_help=True)

ScoringOpt = Annotated[str, typer.Option(help="Scoring config version")]
GridOpt = Annotated[str, typer.Option(help="Grid config version")]


def _artifacts() -> Artifacts:
    return Artifacts(get_settings().data_dir)


@app.command("check-config")
def check_config(scoring: ScoringOpt = "terrain-v1", grid: GridOpt = "pilot-v1") -> None:
    """Validate every config file and print the config hash and code version."""
    s = load_scoring(scoring)
    g = load_grid(grid)
    t = load_targets()
    load_sources()
    typer.echo(
        f"scoring {s.version} ({s.feature_schema_version}), grid {g.version}, targets {sorted(t)}"
    )
    typer.echo(f"config hash {run_config_hash(scoring, grid)}")
    typer.echo(f"code version {git_sha()}")


@app.command("seed-fake")
def seed_fake(
    region: Annotated[list[str] | None, typer.Option(help="Region id(s); default all")] = None,
    scale: Annotated[
        list[int] | None, typer.Option(help="Scale(s) in metres; default each region's scales")
    ] = None,
    max_windows: Annotated[
        int | None, typer.Option(help="Only the first N windows (quick tests)")
    ] = None,
    seed: int = 7,
    scoring: ScoringOpt = "terrain-v1",
    grid: GridOpt = "pilot-v1",
) -> None:
    """Write SYNTHETIC features and target profiles so the app runs before real data exists."""
    from pipeline.fake import seed_region, seed_target

    a, s, g = _artifacts(), load_scoring(scoring), load_grid(grid)
    for t in load_targets().values():
        out = seed_target(a, g, s, t)
        typer.echo(f"target {t.id}: synthetic profile, run {out['run_id']}")
    for r in g.regions:
        if region and r.id not in region:
            continue
        for sc in scale or r.scales_m:
            out = seed_region(a, g, s, r.id, sc, seed=seed, max_windows=max_windows)
            typer.echo(f"{r.id} {sc} m: {out['windows']} synthetic windows, run {out['run_id']}")
    typer.echo("All outputs are marked data_status=synthetic.")


@app.command("run")
def run(
    region: Annotated[str, typer.Option(help="Region id, e.g. earth_sahara")],
    target: Annotated[
        str | None, typer.Option(help="Target id; picks the scale and also builds its profile")
    ] = None,
    scale: Annotated[int | None, typer.Option(help="Scale in metres if no target is given")] = None,
    no_stac: Annotated[bool, typer.Option(help="Skip STAC; use deterministic tile names")] = False,
    scoring: ScoringOpt = "terrain-v1",
    grid: GridOpt = "pilot-v1",
) -> None:
    """Real Earth features for a region (Copernicus DEM + WorldCover) at the target's scale."""
    from pipeline.extract import run_region, run_target

    a, s, g = _artifacts(), load_scoring(scoring), load_grid(grid)
    if target:
        t = load_target(target)
        sc = t.comparison.scale_m
        run_target(a, g, s, t, progress=typer.echo)
    elif scale:
        sc = scale
    else:
        raise typer.BadParameter("give --target or --scale")
    out = run_region(a, g, s, region, sc, use_stac=not no_stac, progress=typer.echo)
    typer.echo(json.dumps(out))


@app.command("target")
def target_cmd(
    target: Annotated[str, typer.Option(help="Target id, e.g. mars_jezero")],
    scoring: ScoringOpt = "terrain-v1",
    grid: GridOpt = "pilot-v1",
) -> None:
    """Real target profile and hillshade preview from SLDEM2015 or the MOLA-HRSC blend."""
    from pipeline.extract import run_target

    out = run_target(
        _artifacts(),
        load_grid(grid),
        load_scoring(scoring),
        load_target(target),
        progress=typer.echo,
    )
    typer.echo(json.dumps(out, default=str))


@app.command("import-registry")
def import_registry_cmd(
    path: Annotated[Path, typer.Argument(help="CSV or GeoJSON of documented analog sites")],
    source: Annotated[str, typer.Option(help="Source label, e.g. usgs_known_terrestrial_analogs")],
    version: Annotated[str, typer.Option(help="Registry version string, e.g. usgs-2025-10")],
    review_date: Annotated[str, typer.Option(help="ISO date the records were checked")],
    name_col: str = "name",
    lat_col: str = "latitude",
    lon_col: str = "longitude",
    id_col: str | None = None,
    relevance_col: Annotated[
        list[str] | None, typer.Option(help="Column(s) naming relevant bodies/targets")
    ] = None,
    ref_col: Annotated[list[str] | None, typer.Option(help="Column(s) holding citations")] = None,
    point_buffer_km: Annotated[
        float, typer.Option(help="Radius for point records (stated assumption)")
    ] = 10.0,
    replace: Annotated[bool, typer.Option(help="Drop all existing sources first")] = False,
) -> None:
    """Import known-analog records. Point records become circles of the stated radius."""
    from pipeline.registry import import_registry

    snap = import_registry(
        _artifacts(),
        path,
        source=source,
        version=version,
        review_date=review_date,
        name_col=name_col,
        lat_col=lat_col,
        lon_col=lon_col,
        id_col=id_col,
        relevance_cols=relevance_col or [],
        ref_cols=ref_col or [],
        buffer_m=point_buffer_km * 1000,
        append=not replace,
    )
    typer.echo(f"registry {snap.version}: {len(snap.entries)} entries from {snap.sources_checked}")


@app.command("load-db")
def load_db(grid: GridOpt = "pilot-v1") -> None:
    """Copy artifacts into PostGIS (evidence store) for the SQL-backed API."""
    from pipeline.load_db import load_all

    load_all(_artifacts(), load_grid(grid), get_settings().database_url, progress=typer.echo)


@app.command("push")
def push_cmd() -> None:
    """Copy data/processed to object storage (EAE_STORAGE_URL)."""
    import os

    from pipeline.storage import push

    url = os.environ.get("EAE_STORAGE_URL")
    if not url:
        raise typer.BadParameter("set EAE_STORAGE_URL (s3://bucket or gs://bucket)")
    n = push(_artifacts().root, url)
    typer.echo(f"pushed {n} files to {url}/processed")


@app.command("pull")
def pull_cmd() -> None:
    """Copy processed artifacts from object storage into data/processed."""
    import os

    from pipeline.storage import pull

    url = os.environ.get("EAE_STORAGE_URL")
    if not url:
        raise typer.BadParameter("set EAE_STORAGE_URL (s3://bucket or gs://bucket)")
    n = pull(url, _artifacts().root)
    typer.echo(f"pulled {n} files from {url}/processed")


@app.command("benchmark")
def benchmark_cmd(
    target: Annotated[str, typer.Option()] = "mars_jezero",
    region: Annotated[str, typer.Option()] = "earth_atacama",
    top_k: int | None = None,
    out: Annotated[Path | None, typer.Option(help="Write the Markdown report here")] = None,
    scoring: ScoringOpt = "terrain-v1",
    grid: GridOpt = "pilot-v1",
) -> None:
    """Atacama-style benchmark: registry positives, low-relief controls, ±20 % sensitivity."""
    from backend.eval.benchmark import benchmark, report_markdown

    a, s, g = _artifacts(), load_scoring(scoring), load_grid(grid)
    tcfg = load_target(target)
    tprof = a.read_target_profile(target, tcfg.comparison.scale_m)
    df, _ = a.read_features(region, tcfg.comparison.scale_m)
    b = benchmark(df, tprof, tcfg, a.read_registry(), s, g, region, top_k)
    md = report_markdown(b)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(md)


@app.command("verify-export")
def verify_export(path: Annotated[Path, typer.Argument(help="A search export (.geojson)")]) -> None:
    """Re-run an exported search from its embedded configuration and compare the ranking."""
    from backend.search.engine import SearchParams, run_search
    from backend.service import Service
    from backend.store.memory import MemoryStore

    fc = json.loads(path.read_text(encoding="utf-8"))
    cfg = fc["search_configuration"]
    req, meta = cfg["request"], cfg["meta"]
    settings = get_settings()
    svc = Service(
        settings, MemoryStore(Artifacts(settings.data_dir)), meta["provenance"]["grid_version"]
    )
    target = svc.target_profile(req["target_id"])
    df, run = svc.features(req["region_id"], target.scale_m)
    problems = []
    if run.id != meta["provenance"]["earth_run_id"]:
        problems.append(f"features run changed: {meta['provenance']['earth_run_id']} -> {run.id}")
    if target.run_id != meta["provenance"]["target_run_id"]:
        problems.append(
            f"target run changed: {meta['provenance']['target_run_id']} -> {target.run_id}"
        )
    result = run_search(
        SearchParams(
            target_id=req["target_id"],
            region_id=req["region_id"],
            top_k=req["top_k"],
            scoring_version=req["scoring_version"],
            purpose=req.get("purpose", "exposed_terrain"),
            exclude_documented_analogs=req.get("exclude_documented_analogs", True),
            optional_feature_groups=req.get("optional_feature_groups", []),
        ),
        target=target,
        features=df,
        run=run,
        registry=svc.store.registry(),
        scoring=load_scoring(req["scoring_version"]),
        grid=svc.grid,
    )
    old = [
        (
            f["properties"]["list"],
            f["properties"]["member_cell_ids"][0],
            round(f["properties"]["configured_similarity"], 9),
        )
        for f in fc["features"]
    ]
    new = [
        (c["list"], c["members"][0]["cell_id"], round(c["score"], 9))
        for c in result["candidates"] + result["reference_matches"]
    ]
    if old != new:
        problems.append("ranking or scores differ")
    if problems:
        for p in problems:
            typer.echo(f"DIFFERENT: {p}")
        raise typer.Exit(1)
    typer.echo(f"identical: {len(new)} results reproduced")


if __name__ == "__main__":
    app()
