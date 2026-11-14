"""Benchmark and sensitivity report for one target and region (D-022, plan §6.3).

- Positives: registry entries inside the region whose relevance mentions the
  target's body or the target keyword (e.g. "mars", "jezero"). They are judged
  by where windows overlapping them rank among all eligible scored windows.
- Negative controls: eligible windows with relief below the yaml threshold.
  They must not fill top_k.
- Sensitivity: each weight and each tolerance moved by ±20 %; report the
  top-k overlap and Kendall tau over the union of top-k lists.

No training happens, so there are no train/test splits; geographic holdouts in
the plan apply to learned models and are out of scope while ML is (D-001).
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd
from shapely.geometry import box as shp_box

from backend.search.engine import _row_values
from backend.search.filter import eligibility
from core.artifacts import RegistrySnapshot, TargetProfileRecord
from core.config import GridConfig, ScoringConfig, TargetConfig
from core.grid import window_from_cell_id, window_lonlat_polygon
from core.scoring import absolute_tolerances, score_window


@dataclass
class Ranked:
    scores: pd.DataFrame  # cell_id, score, relief (eligible + complete only), sorted


def score_all(
    df: pd.DataFrame,
    target: TargetProfileRecord,
    scoring: ScoringConfig,
    weights: dict[str, float] | None = None,
    tolerances: dict[str, float] | None = None,
) -> pd.DataFrame:
    tol = tolerances or absolute_tolerances(target.values, scoring)
    elig = df.loc[eligibility(df, scoring) == ""]
    out = []
    for row in elig.to_dict(orient="records"):
        vals, avail = _row_values(row, scoring)
        ws = score_window(vals, avail, target.values, tol, scoring, weights)
        if ws.total is not None:
            out.append(
                {"cell_id": int(row["cell_id"]), "score": ws.total, "relief": vals["relief"]}
            )
    res = pd.DataFrame(out, columns=["cell_id", "score", "relief"])
    return res.sort_values(
        ["score", "cell_id"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)


def kendall_tau(a: list[int], b: list[int]) -> float:
    """Tau-b-free simple Kendall tau over items present in both rankings."""
    common = [x for x in a if x in set(b)]
    if len(common) < 2:
        return float("nan")
    pos_b = {x: i for i, x in enumerate(b)}
    conc = disc = 0
    for x, y in itertools.combinations(common, 2):
        s = (a.index(x) - a.index(y)) * (pos_b[x] - pos_b[y])
        if s > 0:
            conc += 1
        elif s < 0:
            disc += 1
    n = conc + disc
    return (conc - disc) / n if n else float("nan")


def positives(
    registry: RegistrySnapshot, region_bbox: Any, target: TargetConfig
) -> list[dict[str, Any]]:
    keywords = {target.body.value, *target.id.split("_")[1:]}
    rb = shp_box(region_bbox.west, region_bbox.south, region_bbox.east, region_bbox.north)
    out = []
    for e in registry.entries:
        if not e.geometry.intersects(rb):
            continue
        if keywords & set(e.body_target_relevance):
            out.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "geometry": e.geometry,
                    "relevance": e.body_target_relevance,
                }
            )
    return out


def benchmark(
    df: pd.DataFrame,
    target: TargetProfileRecord,
    target_cfg: TargetConfig,
    registry: RegistrySnapshot,
    scoring: ScoringConfig,
    grid: GridConfig,
    region_id: str,
    top_k: int | None = None,
) -> dict[str, Any]:
    top_k = top_k or scoring.retrieval.top_k_default
    region = grid.region(region_id)
    df = df.loc[df["region_id"] == region_id]
    ranked = score_all(df, target, scoring)
    n = len(ranked)
    rank_of = {cid: i + 1 for i, cid in enumerate(ranked["cell_id"])}

    pos_report = []
    if n:
        polys = {
            cid: window_lonlat_polygon(region, window_from_cell_id(grid, cid))
            for cid in ranked["cell_id"]
        }
    for p in positives(registry, region.bbox, target_cfg):
        hits = [cid for cid, poly in polys.items() if poly.intersects(p["geometry"])] if n else []
        best = min((rank_of[c] for c in hits), default=None)
        pos_report.append(
            {
                "id": p["id"],
                "name": p["name"],
                "relevance": p["relevance"],
                "overlapping_scored_windows": len(hits),
                "best_rank": best,
                "best_percentile": None if best is None else 100 * (1 - (best - 1) / n),
                f"in_top_{top_k}": best is not None and best <= top_k,
            }
        )
    judged = [p for p in pos_report if p["best_rank"] is not None]
    recall = (sum(p[f"in_top_{top_k}"] for p in judged) / len(judged)) if judged else None

    thr = scoring.negative_control.eligible_relief_below_m
    neg = ranked.loc[ranked["relief"] < thr]
    neg_in_top = int(ranked.head(top_k)["relief"].lt(thr).sum())

    base_top = ranked.head(top_k)["cell_id"].tolist()
    sens = []
    for kind, keys in (("weight", list(scoring.weights)), ("tolerance", list(scoring.weights))):
        for key in keys:
            for factor in (0.8, 1.2):
                if kind == "weight":
                    w = dict(scoring.weights)
                    w[key] *= factor
                    r = score_all(df, target, scoring, weights=w)
                else:
                    tol = absolute_tolerances(target.values, scoring)
                    tol[key] *= factor
                    r = score_all(df, target, scoring, tolerances=tol)
                top = r.head(top_k)["cell_id"].tolist()
                union = list(dict.fromkeys(base_top + top))
                full_a = [c for c in ranked["cell_id"] if c in set(union)]
                full_b = [c for c in r["cell_id"] if c in set(union)]
                sens.append(
                    {
                        "parameter": f"{kind}:{key}",
                        "factor": factor,
                        "top_k_overlap": len(set(base_top) & set(top)) / max(1, top_k),
                        "kendall_tau_union": kendall_tau(full_a, full_b),
                    }
                )
    return {
        "target_id": target.target_id,
        "region_id": region_id,
        "scoring_version": scoring.version,
        "data_status": target.data_status,
        "top_k": top_k,
        "eligible_scored_windows": n,
        "registry": {
            "version": registry.version,
            "review_date": registry.review_date,
            "sources_checked": registry.sources_checked,
        },
        "positives": pos_report,
        "recall_at_k": recall,
        "negative_controls": {
            "relief_below_m": thr,
            "count": len(neg),
            "in_top_k": neg_in_top,
            "fills_top_k": neg_in_top >= top_k,
            "best_rank": int(neg.index.min()) + 1 if len(neg) else None,
        },
        "sensitivity": sens,
    }


def report_markdown(b: dict[str, Any]) -> str:
    k = b["top_k"]
    lines = [
        f"# Benchmark: {b['target_id']} on {b['region_id']} ({b['scoring_version']})",
        "",
        f"Data: **{b['data_status']}**. Eligible scored windows: {b['eligible_scored_windows']}. top_k = {k}.",
        f"Registry checked: {b['registry']['version']} ({', '.join(b['registry']['sources_checked']) or 'none loaded'}),"
        f" review date {b['registry']['review_date'] or 'n/a'}.",
        "",
        "Scores are configured similarity, not probability. A weak positive ranking is a property of "
        f"{b['scoring_version']}, not a pipeline failure (D-022).",
        "",
        "## Positives",
        "",
    ]
    if not b["positives"]:
        lines.append("No registry entries in this region mention the target body or keyword.")
    else:
        lines += [
            "| Record | Relevance | Overlapping windows | Best rank | Percentile | In top k |",
            "|---|---|---|---|---|---|",
        ]
        for p in b["positives"]:
            pct = "—" if p["best_percentile"] is None else f"{p['best_percentile']:.1f}"
            lines.append(
                f"| {p['name']} | {', '.join(p['relevance'])} | {p['overlapping_scored_windows']} | "
                f"{p['best_rank'] or '—'} | {pct} | {'yes' if p[f'in_top_{k}'] else 'no'} |"
            )
        r = b["recall_at_k"]
        lines += ["", f"Recall@{k} over judged positives: {'n/a' if r is None else f'{r:.2f}'}"]
    nc = b["negative_controls"]
    lines += [
        "",
        "## Negative controls",
        "",
        f"Eligible windows with relief < {nc['relief_below_m']:g} m: {nc['count']}. "
        f"In top {k}: {nc['in_top_k']}. Fill top k: {'**yes (fails)**' if nc['fills_top_k'] else 'no (passes)'}.",
        "",
        "## Sensitivity (±20 %)",
        "",
        "| Parameter | Factor | Top-k overlap | Kendall tau (union of top-k) |",
        "|---|---|---|---|",
    ]
    for s in b["sensitivity"]:
        tau = "n/a" if math.isnan(s["kendall_tau_union"]) else f"{s['kendall_tau_union']:.2f}"
        lines.append(f"| {s['parameter']} | {s['factor']} | {s['top_k_overlap']:.2f} | {tau} |")
    return "\n".join(lines) + "\n"
