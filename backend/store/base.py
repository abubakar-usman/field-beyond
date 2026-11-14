"""Where searches, candidates, evidence profiles, registry and reviews are kept.

Two implementations share this interface:
- :class:`backend.store.sql.SqlStore` — PostGIS (Docker Compose, the VM).
- :class:`backend.store.memory.MemoryStore` — in process, evidence read from the
  verified parquet; for laptops without Docker and for tests.

Search inputs (target profiles and `features.parquet`) always come from the
pipeline artifacts on disk (D-019); the store never ranks anything.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from core.artifacts import RegistrySnapshot

ListName = Literal["candidates", "reference_matches"]

# Review workflow (IMPLEMENTATION_PLAN.md §6.2). Keys are current statuses.
TRANSITIONS: dict[str, set[str]] = {
    "not_in_checked_records": {"under_review", "promising", "rejected", "documented_analog"},
    "under_review": {"promising", "rejected", "documented_analog"},
    "promising": {"under_review", "rejected", "documented_analog"},
    "rejected": {"under_review"},
    "documented_analog": {"under_review"},
}


class InvalidTransition(ValueError):
    pass


def check_transition(current: str, decision: str) -> None:
    allowed = TRANSITIONS.get(current, set())
    if decision not in allowed:
        raise InvalidTransition(
            f"cannot move a candidate from {current!r} to {decision!r}; allowed: {sorted(allowed)}"
        )


class Store(Protocol):
    kind: str

    def healthy(self) -> tuple[bool, str]: ...

    def find_search(self, cache_key: str) -> str | None: ...

    def save_search(
        self, search_id: str, cache_key: str, request: dict[str, Any], result: dict[str, Any]
    ) -> None: ...

    def get_search(self, search_id: str) -> dict[str, Any] | None: ...

    def list_candidates(
        self, search_id: str, list_name: ListName, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]: ...

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None: ...

    def get_shortlist(self, search_id: str) -> list[dict[str, Any]]: ...

    def cell_profiles(
        self, cell_ids: list[int], scale_m: int, run_id: str
    ) -> dict[int, dict[str, Any]]: ...

    def registry(self) -> RegistrySnapshot: ...

    def add_review(
        self,
        candidate_id: str,
        reviewer_id: str,
        decision: str,
        note: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]: ...

    def list_reviews(self, candidate_id: str) -> list[dict[str, Any]]: ...
