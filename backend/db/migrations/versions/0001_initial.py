"""Initial schema: every table in IMPLEMENTATION_PLAN.md §5 (empty).

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql as pg

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _geom(kind: str = "GEOMETRY") -> Geometry:
    return Geometry(geometry_type=kind, srid=4326, spatial_index=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "source_assets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("asset_key", sa.Text(), nullable=False),
        sa.Column("body", sa.String(8), nullable=False),
        sa.Column("footprint", _geom(), nullable=True),
        sa.Column("footprint_wkt", sa.Text(), nullable=True),
        sa.Column("crs", sa.Text(), nullable=False),
        sa.Column("resolution_m", sa.Float(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("access_meta", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("body IN ('earth', 'moon', 'mars')", name="ck_source_assets_body"),
        sa.CheckConstraint(
            "(body = 'earth' AND footprint_wkt IS NULL) OR (body <> 'earth' AND footprint IS NULL)",
            name="ck_source_assets_footprint_by_body",
        ),
        sa.UniqueConstraint("provider", "asset_key", "sha256", name="uq_source_assets_key"),
    )

    op.create_table(
        "processing_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("inputs", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("outputs", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("features_sha256", sa.String(64), nullable=True),
        sa.Column("data_status", sa.String(16), nullable=False, server_default="measured"),
        sa.Column("code_version", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="ck_processing_runs_status"
        ),
    )

    op.create_table(
        "earth_cells",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("region_id", sa.String(64), nullable=False),
        sa.Column("grid_version", sa.String(32), nullable=False),
        sa.Column("boundary", _geom("POLYGON"), nullable=False),
        sa.Column("footprint_m", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey("earth_cells.id"), nullable=True),
    )
    op.create_index("ix_earth_cells_region_grid", "earth_cells", ["region_id", "grid_version"])
    op.create_index("ix_earth_cells_boundary", "earth_cells", ["boundary"], postgresql_using="gist")

    op.create_table(
        "planetary_targets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("body", sa.String(8), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("boundary_wkt", sa.Text(), nullable=False),
        sa.Column("crs", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("preview_uri", sa.Text(), nullable=True),
        sa.CheckConstraint("body IN ('moon', 'mars')", name="ck_planetary_targets_body"),
    )

    op.create_table(
        "feature_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("owner_type", sa.String(8), nullable=False),
        sa.Column(
            "cell_id",
            sa.BigInteger(),
            sa.ForeignKey("earth_cells.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "target_id",
            sa.String(64),
            sa.ForeignKey("planetary_targets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("scale_m", sa.Integer(), nullable=False),
        sa.Column("values", pg.JSONB(), nullable=False),
        sa.Column("availability", pg.JSONB(), nullable=False),
        sa.Column(
            "source_asset_ids", pg.ARRAY(sa.BigInteger()), nullable=False, server_default="{}"
        ),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("processing_runs.id"), nullable=False),
        sa.CheckConstraint(
            "owner_type IN ('cell', 'target')", name="ck_feature_profiles_owner_type"
        ),
        sa.CheckConstraint(
            "(owner_type = 'cell' AND cell_id IS NOT NULL AND target_id IS NULL) OR "
            "(owner_type = 'target' AND target_id IS NOT NULL AND cell_id IS NULL)",
            name="ck_feature_profiles_owner",
        ),
        sa.CheckConstraint("scale_m > 0", name="ck_feature_profiles_scale"),
        sa.UniqueConstraint(
            "owner_type", "cell_id", "target_id", "scale_m", "run_id", name="uq_feature_profiles"
        ),
    )
    op.create_index(
        "ix_feature_profiles_cell", "feature_profiles", ["cell_id", "scale_m", "run_id"]
    )

    op.create_table(
        "search_jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("request", pg.JSONB(), nullable=False),
        sa.Column("scoring_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result_meta", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "earth_run_id", sa.String(64), sa.ForeignKey("processing_runs.id"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')", name="ck_search_jobs_status"
        ),
    )
    op.create_index("ix_search_jobs_cache_key", "search_jobs", ["cache_key"])

    op.create_table(
        "candidate_matches",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "search_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("search_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("result_list", sa.String(24), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("region_geom", _geom(), nullable=False),
        sa.Column("member_cell_ids", pg.ARRAY(sa.BigInteger()), nullable=False),
        sa.Column(
            "member_scores", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("component_scores", pg.JSONB(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("novelty_status", sa.String(32), nullable=False),
        sa.Column("novelty", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("explanation", pg.JSONB(), nullable=False),
        sa.CheckConstraint(
            "novelty_status IN ('not_in_checked_records', 'under_review', 'documented_analog', "
            "'promising', 'rejected')",
            name="ck_candidate_matches_novelty",
        ),
        sa.CheckConstraint(
            "result_list IN ('candidates', 'reference_matches')", name="ck_candidate_matches_list"
        ),
    )
    op.create_index(
        "ix_candidate_matches_search", "candidate_matches", ["search_id", "result_list", "rank"]
    )
    op.create_index(
        "ix_candidate_matches_region_geom",
        "candidate_matches",
        ["region_geom"],
        postgresql_using="gist",
    )

    op.create_table(
        "known_analog_registry",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("boundary", _geom(), nullable=False),
        sa.Column(
            "body_target_relevance", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("citations", pg.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("registry_version", sa.String(64), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("boundary_note", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_known_analog_registry_boundary",
        "known_analog_registry",
        ["boundary"],
        postgresql_using="gist",
    )

    op.create_table(
        "review_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidate_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("candidate_matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("novelty_status", sa.String(32), nullable=False),
        sa.Column("evidence", pg.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "decision IN ('under_review', 'promising', 'documented_analog', 'rejected')",
            name="ck_review_records_decision",
        ),
    )


def downgrade() -> None:
    for table in (
        "review_records",
        "known_analog_registry",
        "candidate_matches",
        "search_jobs",
        "feature_profiles",
        "planetary_targets",
        "earth_cells",
        "processing_runs",
        "source_assets",
    ):
        op.drop_table(table)
