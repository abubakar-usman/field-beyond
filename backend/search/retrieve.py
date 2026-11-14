"""Nearest-neighbour shortlist on four z-scored scalars (D-020).

The region's windows number in the tens of thousands at most, so an exact
brute-force distance in NumPy is used; it is the same answer a BallTree gives.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from core.config import ScoringConfig


@dataclass
class IndexStats:
    features: list[str]
    mean: list[float]
    std: list[float]
    n: int

    def to_dict(self) -> dict[str, Any]:
        return {"features": self.features, "mean": self.mean, "std": self.std, "n": self.n}


def complete_rows(df: pd.DataFrame, features: list[str]) -> pd.Series:
    return df[features].notna().all(axis=1)


def index_stats(eligible: pd.DataFrame, cfg: ScoringConfig) -> IndexStats:
    feats = list(cfg.retrieval_features)
    x = eligible.loc[complete_rows(eligible, feats), feats].astype(float).to_numpy()
    if x.shape[0] == 0:
        return IndexStats(feats, [0.0] * len(feats), [1.0] * len(feats), 0)
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    # A constant feature carries no ranking information; leave it unscaled rather than divide by 0.
    std = np.where(std > 0, std, 1.0)
    return IndexStats(feats, mean.tolist(), std.tolist(), int(x.shape[0]))


def shortlist(
    eligible: pd.DataFrame,
    target: Mapping[str, Any],
    cfg: ScoringConfig,
    top_k: int,
    stats: IndexStats | None = None,
) -> tuple[pd.DataFrame, IndexStats]:
    """Rows of ``eligible`` nearest the target, ``shortlist_multiplier × top_k`` of them.

    Rows missing a retrieval feature are not in the tree (they would be
    excluded at scoring anyway). Ties break on ``cell_id`` ascending.
    """
    stats = stats or index_stats(eligible, cfg)
    feats = stats.features
    pool = eligible.loc[complete_rows(eligible, feats)]
    if pool.empty:
        return pool.assign(retrieval_distance=pd.Series(dtype=float)), stats
    x = (pool[feats].astype(float).to_numpy() - np.asarray(stats.mean)) / np.asarray(stats.std)
    t = (np.asarray([float(target[f]) for f in feats]) - np.asarray(stats.mean)) / np.asarray(
        stats.std
    )
    dist = np.sqrt(((x - t) ** 2).sum(axis=1))
    out = pool.assign(retrieval_distance=dist)
    out = out.sort_values(["retrieval_distance", "cell_id"], kind="mergesort")
    n = cfg.retrieval.shortlist_multiplier * top_k
    return out.head(n), stats
