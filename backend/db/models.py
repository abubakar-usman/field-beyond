"""SQLAlchemy models for IMPLEMENTATION_PLAN.md §5.

Earth geometries are PostGIS geometry in EPSG:4326. Moon and Mars geometries
are never given an Earth SRID: they are WKT text with explicit ``body`` and
``crs`` columns (CLAUDE.md rule 3). A check constraint on ``source_assets``
enforces that split.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

BODY_CHECK = "body IN ('earth', 'moon', 'mars')"


class Base(DeclarativeBase):
    pass


def _earth_geom(kind: str = "GEOMETRY") -> Geometry:
    return Geometry(geometry_type=kind, srid=4326, spatial_index=False)


class SourceAsset(Base):
    __tablename__ = "source_assets"
    __table_args__ = (
        CheckConstraint(BODY_CHECK, name="ck_source_assets_body"),
        CheckConstraint(
            "(body = 'earth' AND footprint_wkt IS NULL) OR (body <> 'earth' AND footprint IS NULL)",
            name="ck_source_assets_footprint_by_body",
        ),
        UniqueConstraint("provider", "asset_key", "sha256", name="uq_source_assets_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64))
    product_id: Mapped[str] = mapped_column(String(64))
    asset_key: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(String(8))
    footprint: Mapped[Any | None] = mapped_column(_earth_geom(), nullable=True)
    footprint_wkt: Mapped[str | None] = mapped_column(Text, nullable=True)
    crs: Mapped[str] = mapped_column(Text)
    resolution_m: Mapped[float] = mapped_column(Float)
    source_version: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_uri: Mapped[str] = mapped_column(Text)
    access_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="ck_processing_runs_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    features_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_status: Mapped[str] = mapped_column(String(16), default="measured")
    code_version: Mapped[str] = mapped_column(Text)
    config_hash: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EarthCell(Base):
    __tablename__ = "earth_cells"
    __table_args__ = (
        Index("ix_earth_cells_region_grid", "region_id", "grid_version"),
        Index("ix_earth_cells_boundary", "boundary", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    region_id: Mapped[str] = mapped_column(String(64))
    grid_version: Mapped[str] = mapped_column(String(32))
    boundary: Mapped[Any] = mapped_column(_earth_geom("POLYGON"))
    footprint_m: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("earth_cells.id"), nullable=True
    )


class PlanetaryTarget(Base):
    __tablename__ = "planetary_targets"
    __table_args__ = (
        CheckConstraint("body IN ('moon', 'mars')", name="ck_planetary_targets_body"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    body: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(Text)
    boundary_wkt: Mapped[str] = mapped_column(Text)
    crs: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    preview_uri: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeatureProfile(Base):
    __tablename__ = "feature_profiles"
    __table_args__ = (
        CheckConstraint("owner_type IN ('cell', 'target')", name="ck_feature_profiles_owner_type"),
        CheckConstraint(
            "(owner_type = 'cell' AND cell_id IS NOT NULL AND target_id IS NULL) OR "
            "(owner_type = 'target' AND target_id IS NOT NULL AND cell_id IS NULL)",
            name="ck_feature_profiles_owner",
        ),
        CheckConstraint("scale_m > 0", name="ck_feature_profiles_scale"),
        UniqueConstraint(
            "owner_type", "cell_id", "target_id", "scale_m", "run_id", name="uq_feature_profiles"
        ),
        Index("ix_feature_profiles_cell", "cell_id", "scale_m", "run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_type: Mapped[str] = mapped_column(String(8))
    cell_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("earth_cells.id", ondelete="CASCADE"), nullable=True
    )
    target_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("planetary_targets.id", ondelete="CASCADE"), nullable=True
    )
    schema_version: Mapped[str] = mapped_column(Text)
    scale_m: Mapped[int] = mapped_column(Integer)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB)
    availability: Mapped[dict[str, bool]] = mapped_column(JSONB)
    source_asset_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("processing_runs.id"))


class SearchJob(Base):
    __tablename__ = "search_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')", name="ck_search_jobs_status"
        ),
        Index("ix_search_jobs_cache_key", "cache_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    scoring_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    earth_run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("processing_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CandidateMatch(Base):
    __tablename__ = "candidate_matches"
    __table_args__ = (
        CheckConstraint(
            "novelty_status IN ('not_in_checked_records', 'under_review', 'documented_analog', "
            "'promising', 'rejected')",
            name="ck_candidate_matches_novelty",
        ),
        CheckConstraint(
            "result_list IN ('candidates', 'reference_matches')", name="ck_candidate_matches_list"
        ),
        Index("ix_candidate_matches_search", "search_id", "result_list", "rank"),
        Index("ix_candidate_matches_region_geom", "region_geom", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_jobs.id", ondelete="CASCADE")
    )
    result_list: Mapped[str] = mapped_column(String(24))
    rank: Mapped[int] = mapped_column(Integer)
    region_geom: Mapped[Any] = mapped_column(_earth_geom())
    member_cell_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    member_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    component_scores: Mapped[dict[str, Any]] = mapped_column(JSONB)
    total_score: Mapped[float] = mapped_column(Float)
    novelty_status: Mapped[str] = mapped_column(String(32))
    novelty: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB)


class KnownAnalog(Base):
    __tablename__ = "known_analog_registry"
    __table_args__ = (
        Index("ix_known_analog_registry_boundary", "boundary", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text)
    boundary: Mapped[Any] = mapped_column(_earth_geom())
    body_target_relevance: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    # "references" is an SQL reserved word, so the column is named citations.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(Text)
    registry_version: Mapped[str] = mapped_column(String(64))
    review_date: Mapped[date] = mapped_column(Date)
    boundary_note: Mapped[str] = mapped_column(Text, default="")


class ReviewRecord(Base):
    __tablename__ = "review_records"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('under_review', 'promising', 'documented_analog', 'rejected')",
            name="ck_review_records_decision",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_matches.id", ondelete="CASCADE")
    )
    reviewer_id: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(32))
    previous_status: Mapped[str] = mapped_column(String(32))
    novelty_status: Mapped[str] = mapped_column(String(32))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
