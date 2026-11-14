"""Spatial grouping of scored windows into candidate regions (D-021).

1. Sort by score descending, then cell_id ascending.
2. Keep a window when its IoU with every kept window is <= the threshold.
3. Merge kept windows whose polygons still overlap (intersection area > 0).
4. Candidate score = best member score; every member is kept.

Polygons should be in an equal-area projection (the region LAEA).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shapely import STRtree
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


@dataclass(frozen=True)
class ScoredWindow:
    cell_id: int
    score: float
    geom: BaseGeometry


@dataclass
class Group:
    members: list[ScoredWindow]

    @property
    def score(self) -> float:
        return max(m.score for m in self.members)

    @property
    def best(self) -> ScoredWindow:
        return min(self.members, key=lambda m: (-m.score, m.cell_id))

    @property
    def geom(self) -> BaseGeometry:
        return unary_union([m.geom for m in self.members])


def iou(a: BaseGeometry, b: BaseGeometry) -> float:
    inter = a.intersection(b).area
    if inter <= 0:
        return 0.0
    return float(inter / (a.area + b.area - inter))


def nms(windows: Sequence[ScoredWindow], iou_above: float) -> list[ScoredWindow]:
    ordered = sorted(windows, key=lambda w: (-w.score, w.cell_id))
    kept: list[ScoredWindow] = []
    tree_geoms: list[BaseGeometry] = []
    for w in ordered:
        # Kept set is small (top-k scale); a linear scan with a bbox pre-check is enough.
        if all(not w.geom.intersects(g) or iou(w.geom, g) <= iou_above for g in tree_geoms):
            kept.append(w)
            tree_geoms.append(w.geom)
    return kept


def merge_overlapping(kept: Sequence[ScoredWindow]) -> list[Group]:
    """Union-find over kept windows whose intersection has positive area."""
    n = len(kept)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    geoms = [k.geom for k in kept]
    tree = STRtree(geoms)
    for i, g in enumerate(geoms):
        for j in tree.query(g):
            j = int(j)
            if j <= i:
                continue
            if g.intersection(geoms[j]).area > 0:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    groups: dict[int, list[ScoredWindow]] = {}
    for i, k in enumerate(kept):
        groups.setdefault(find(i), []).append(k)
    out = [Group(members=sorted(m, key=lambda w: (-w.score, w.cell_id))) for m in groups.values()]
    out.sort(key=lambda g: (-g.score, g.best.cell_id))
    return out


def group_windows(windows: Sequence[ScoredWindow], iou_above: float) -> list[Group]:
    return merge_overlapping(nms(windows, iou_above))
