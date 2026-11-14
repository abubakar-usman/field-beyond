"""Request bodies. Responses are plain JSON documented in docs/WALKTHROUGH.md."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str = Field(examples=["mars_jezero"])
    region_id: str = Field(examples=["earth_sahara"])
    purpose: str = "exposed_terrain"
    required_feature_groups: list[Literal["terrain"]] = ["terrain"]
    optional_feature_groups: list[str] = []
    exclude_documented_analogs: bool = True
    retrieval_mode: Literal["baseline"] = "baseline"
    top_k: int | None = Field(default=None, ge=1)
    scoring_version: str = "terrain-v1"


class RescoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(min_length=1, max_length=120)
    decision: Literal["under_review", "promising", "documented_analog", "rejected"]
    note: str = Field(default="", max_length=4000)
    evidence: dict[str, object] = {}
