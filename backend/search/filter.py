"""Eligibility filter (purpose `exposed_terrain`). Thresholds come from the scoring yaml."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ScoringConfig


def eligibility(df: pd.DataFrame, cfg: ScoringConfig) -> pd.Series:
    """Reason a window is ineligible, or ``""`` when it passes.

    A null land-cover fraction or valid fraction cannot be checked, so it is
    ineligible (missing data is never a match).
    """
    e = cfg.eligibility
    reason = pd.Series("", index=df.index, dtype=object)

    def mark(cond: pd.Series, why: str) -> None:
        nonlocal reason
        reason = reason.where(~(cond & (reason == "")), why)

    vf = df["valid_fraction"].astype(float)
    mark(vf.isna(), "valid_fraction_unavailable")
    mark(vf < e.valid_fraction_min, "valid_fraction_below_min")
    for col, maximum, why in (
        ("water_fraction", e.water_fraction_max, "water_above_max"),
        ("built_up_fraction", e.built_up_fraction_max, "built_up_above_max"),
    ):
        v = df[col].astype(float)
        mark(v.isna(), f"{col}_unavailable")
        mark(v > maximum, why)
    if e.snow_ice == "exclude":
        mark(df["snow_ice_fraction"].astype(float).fillna(np.inf) > 0, "snow_ice_present")
    if e.vegetation == "exclude":
        mark(df["vegetation_fraction"].astype(float).fillna(np.inf) > 0, "vegetation_present")
    return reason
