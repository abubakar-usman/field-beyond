"""Novelty check against the known-analog registry.

Overlap with any registry entry -> ``documented_analog``. No overlap ->
``not_in_checked_records``. That label means "not in the records we checked",
never "new discovery" (CLAUDE.md rule 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shapely import STRtree
from shapely.geometry.base import BaseGeometry

from core.artifacts import RegistrySnapshot


@dataclass
class NoveltyResult:
    status: str
    matched: list[dict[str, Any]] = field(default_factory=list)


class NoveltyChecker:
    def __init__(self, registry: RegistrySnapshot):
        self.registry = registry
        self._geoms = [e.geometry for e in registry.entries]
        self._tree = STRtree(self._geoms) if self._geoms else None

    def check(self, geom_lonlat: BaseGeometry) -> NoveltyResult:
        if self._tree is None:
            return NoveltyResult(status="not_in_checked_records")
        hits = []
        for i in self._tree.query(geom_lonlat, predicate="intersects"):
            e = self.registry.entries[int(i)]
            hits.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "source": e.source,
                    "body_target_relevance": e.body_target_relevance,
                    "boundary_note": e.boundary_note,
                }
            )
        hits.sort(key=lambda h: str(h["id"]))
        return NoveltyResult(
            status="documented_analog" if hits else "not_in_checked_records", matched=hits
        )

    def describe(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry.version,
            "review_date": self.registry.review_date,
            "sources_checked": self.registry.sources_checked,
            "registry_loaded": self.registry.loaded,
            "entries": len(self.registry.entries),
        }
