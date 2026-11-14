"""Deterministic explanation text built from the measured numbers (no generated prose).

Wording follows .claude/skills/scientific-copy/SKILL.md: state the measured
difference, the tolerance and the similarity. No percent gaps, no
"probability" or "confidence".
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

LABELS = {
    "slope_hist": "Slope distribution",
    "slope_median": "Median slope",
    "slope_p90": "90th-percentile slope",
    "relief": "Relief (p95 − p5)",
    "roughness": "Roughness (plane-fit residual)",
}


def _fmt(v: float, unit: str) -> str:
    if unit.startswith("deg"):
        return f"{v:.1f}°"
    if unit == "m":
        return f"{v:.0f} m" if abs(v) >= 10 else f"{v:.1f} m"
    return f"{v:.2f}"


def feature_line(c: Mapping[str, Any]) -> str:
    f = c["feature"]
    unit = c["unit"]
    inside = "within tolerance" if c["within_tolerance"] else "outside tolerance"
    sim = round(c["similarity"])
    if f == "slope_hist":
        return (
            f"{LABELS[f]}: Wasserstein-1 distance {_fmt(c['difference'], unit)} "
            f"on a {_fmt(c['tolerance'], unit)} tolerance, similarity {sim} ({inside})"
        )
    return (
        f"{LABELS.get(f, f)}: {_fmt(c['earth'], unit)} vs target {_fmt(c['target'], unit)}, "
        f"difference {_fmt(c['difference'], unit)} on a {_fmt(c['tolerance'], unit)} tolerance, "
        f"similarity {sim} ({inside})"
    )


def explain(
    components: Mapping[str, Mapping[str, Any]],
    main_mismatch: str | None,
    *,
    scale_m: int,
    window_m: int,
    target_name: str,
    unavailable: list[str],
    scoring_version: str,
) -> dict[str, Any]:
    lines = [feature_line(components[f]) for f in components]
    summary = (
        f"Terrain measurements compared with {target_name} at {scale_m} m pixels "
        f"in a {window_m / 1000:g} km window ({scoring_version})."
    )
    mismatch = None
    if main_mismatch is not None:
        c = components[main_mismatch]
        mismatch = (
            f"Main mismatch: {LABELS.get(main_mismatch, main_mismatch).lower()} "
            f"(similarity {round(c['similarity'])})."
        )
    not_available = [f"{u}: not available" for u in unavailable]
    return {
        "summary": summary,
        "lines": lines,
        "main_mismatch": mismatch,
        "not_available": not_available,
        "text": " ".join([summary, *lines, *([mismatch] if mismatch else []), *not_available]),
    }
