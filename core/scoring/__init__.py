"""terrain-v1 scoring: per-feature similarity, histogram distance, weighted total.

The rules are in docs/SCORING.md; the numbers are in config/scoring/*.yaml.
A score is a "configured similarity", never a probability.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.config import ScoringConfig


def similarity(difference: float, tolerance: float) -> float:
    """``100 × max(0, 1 − difference / tolerance)``."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    return 100.0 * max(0.0, 1.0 - abs(difference) / tolerance)


def _cdf_at_edges(hist: Sequence[float]) -> np.ndarray:
    h = np.asarray(hist, dtype=float)
    total = h.sum()
    if total <= 0:
        raise ValueError("histogram has no mass")
    return np.concatenate([[0.0], np.cumsum(h / total)])


def wasserstein_hist_deg(
    h1: Sequence[float], h2: Sequence[float], bins_deg: Sequence[float]
) -> float:
    """Wasserstein-1 distance in degrees between two binned slope distributions.

    ``∫ |CDF₁(s) − CDF₂(s)| ds`` from the first to the last bin edge. Mass is
    taken as uniform inside each bin, so each CDF is linear between edges and
    the integral is exact for that model. Ground distance is degrees, not bin
    index (D-021).
    """
    edges = np.asarray(bins_deg, dtype=float)
    if len(h1) != len(edges) - 1 or len(h2) != len(edges) - 1:
        raise ValueError("histograms must have one value per bin")
    d = _cdf_at_edges(h1) - _cdf_at_edges(h2)
    total = 0.0
    for k in range(len(edges) - 1):
        w = edges[k + 1] - edges[k]
        a, b = d[k], d[k + 1]
        if a * b >= 0:
            total += w * (abs(a) + abs(b)) / 2
        else:  # the linear difference crosses zero inside the bin
            total += w * (a * a + b * b) / (2 * (abs(a) + abs(b)))
    return float(total)


def absolute_tolerances(target: Mapping[str, Any], cfg: ScoringConfig) -> dict[str, float]:
    """Tolerances in feature units for one target. Stored with every result."""
    t = cfg.tolerances
    relief = target.get("relief")
    rough = target.get("roughness")
    if relief is None or rough is None:
        raise ValueError("target relief and roughness are required to set tolerances")
    return {
        "slope_hist": t.slope_hist_deg,
        "slope_median": t.slope_median_deg,
        "slope_p90": t.slope_p90_deg,
        "relief": max(t.relief_fraction_of_target * float(relief), t.relief_floor_m),
        "roughness": max(t.roughness_fraction_of_target * float(rough), t.roughness_floor_m),
    }


def feature_available(
    values: Mapping[str, Any], availability: Mapping[str, bool], key: str
) -> bool:
    v = values.get(key)
    if v is None or not availability.get(key, False):
        return False
    return not (isinstance(v, float) and math.isnan(v))


def missing_mandatory(
    values: Mapping[str, Any], availability: Mapping[str, bool], cfg: ScoringConfig
) -> list[str]:
    return [f for f in cfg.mandatory_features if not feature_available(values, availability, f)]


@dataclass
class Component:
    feature: str
    earth: Any
    target: Any
    difference: float
    tolerance: float
    similarity: float
    weight: float
    unit: str

    @property
    def within_tolerance(self) -> bool:
        return self.difference <= self.tolerance

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "earth": self.earth,
            "target": self.target,
            "difference": self.difference,
            "tolerance": self.tolerance,
            "similarity": self.similarity,
            "weight": self.weight,
            "unit": self.unit,
            "within_tolerance": self.within_tolerance,
        }


UNITS = {
    "slope_hist": "deg (Wasserstein-1)",
    "slope_median": "deg",
    "slope_p90": "deg",
    "relief": "m",
    "roughness": "m",
}


@dataclass
class WindowScore:
    total: float | None
    components: dict[str, Component] = field(default_factory=dict)
    excluded_reason: str | None = None
    missing: list[str] = field(default_factory=list)

    @property
    def main_mismatch(self) -> str | None:
        if not self.components:
            return None
        return min(self.components.values(), key=lambda c: (c.similarity, c.feature)).feature


def score_window(
    earth: Mapping[str, Any],
    earth_availability: Mapping[str, bool],
    target: Mapping[str, Any],
    tolerances: Mapping[str, float],
    cfg: ScoringConfig,
    weights: Mapping[str, float] | None = None,
) -> WindowScore:
    """Weighted mean of per-feature similarities over the mandatory features.

    A window missing any mandatory feature is excluded, never scored on the rest
    (CLAUDE.md rule 4). The target must be complete; callers refuse the search
    otherwise.
    """
    w = dict(weights if weights is not None else cfg.weights)
    missing = missing_mandatory(earth, earth_availability, cfg)
    if missing:
        return WindowScore(total=None, excluded_reason="missing_mandatory_feature", missing=missing)
    comps: dict[str, Component] = {}
    for f in cfg.mandatory_features:
        if f == cfg.histogram_feature:
            diff = wasserstein_hist_deg(earth[f], target[f], cfg.slope_hist_bins_deg)
        else:
            diff = abs(float(earth[f]) - float(target[f]))
        tol = float(tolerances[f])
        comps[f] = Component(
            feature=f,
            earth=earth[f],
            target=target[f],
            difference=diff,
            tolerance=tol,
            similarity=similarity(diff, tol),
            weight=float(w[f]),
            unit=UNITS.get(f, ""),
        )
    wsum = sum(c.weight for c in comps.values())
    if wsum <= 0:
        raise ValueError("weights must sum to a positive number")
    total = sum(c.weight * c.similarity for c in comps.values()) / wsum
    return WindowScore(total=total, components=comps)
