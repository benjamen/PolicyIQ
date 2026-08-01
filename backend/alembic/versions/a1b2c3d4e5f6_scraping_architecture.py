"""scraping architecture: risk areas, risk events, document collections, pipeline runs

Revision ID: a1b2c3d4e5f6
Revises: df3a5db0641e
Create Date: 2026-08-01

Adds the extended data model from docs/12-SCRAPING-ARCHITECTURE.md:
- RISK_AREA: curated taxonomy of what insurance covers (hierarchical)
- RISK_EVENT: per-product coverage status for a specific scenario
- DOCUMENT_COLLECTION: brochures, marketing PDFs, supplementary docs
- BROCHURE_ASSET: visual assets extracted from collection documents
- PIPELINE_RUN: tracking table for automated pipeline executions
- EXTRACTION_QUALITY_METRIC: per-run quality measurements
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "df3a5db0641e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Risk Area taxonomy ---
    op.create_table(
        "risk_area",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("code", sa.String(60), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("parent_id", sa.CHAR(36), sa.ForeignKey("risk_area.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_risk_area_parent_id", "risk_area", ["parent_id"])

    # --- Risk Event (comparison primitive) ---
    op.create_table(
        "risk_event",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("risk_area_id", sa.CHAR(36), sa.ForeignKey("risk_area.id"), nullable=False),
        sa.Column("policy_version_id", sa.CHAR(36), sa.ForeignKey("policy_version.id"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("coverage_status", sa.String(20), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("monetary_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("percentage_limit", sa.Numeric(5, 2), nullable=True),
        sa.Column("excess_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("waiting_period_days", sa.Integer, nullable=True),
        sa.Column("document_id", sa.CHAR(36), sa.ForeignKey("document.id"), nullable=True),
        sa.Column("section_id", sa.CHAR(36), sa.ForeignKey("section.id"), nullable=True),
        sa.Column("page", sa.Integer, nullable=True),
        sa.Column("paragraph_ref", sa.String(40), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_risk_event_area_version", "risk_event", ["risk_area_id", "policy_version_id"])
    op.create_index("ix_risk_event_coverage_status", "risk_event", ["coverage_status"])

    # --- Document Collection (brochures, supplementary) ---
    op.create_table(
        "document_collection",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("policy_version_id", sa.CHAR(36), sa.ForeignKey("policy_version.id"), nullable=False),
        sa.Column("collection_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("sha256_hash", sa.CHAR(64), nullable=False),
        sa.Column("mime_type", sa.String(60), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("published_date", sa.Date, nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("superseded_by_id", sa.CHAR(36), sa.ForeignKey("document_collection.id"), nullable=True),
        sa.Column("etag", sa.Text, nullable=True),
        sa.Column("last_modified", sa.Text, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("1")),
    )
    op.create_index("ix_doc_collection_version", "document_collection", ["policy_version_id"])
    op.create_index("ix_doc_collection_hash", "document_collection", ["sha256_hash"])

    # --- Brochure Asset (visual assets from collection docs) ---
    op.create_table(
        "brochure_asset",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("document_collection_id", sa.CHAR(36), sa.ForeignKey("document_collection.id"), nullable=False),
        sa.Column("asset_type", sa.String(40), nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("width_px", sa.Integer, nullable=True),
        sa.Column("height_px", sa.Integer, nullable=True),
    )
    op.create_index("ix_brochure_asset_collection", "brochure_asset", ["document_collection_id"])

    # --- Pipeline Run tracking ---
    op.create_table(
        "pipeline_run",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("run_type", sa.String(40), nullable=False),
        sa.Column("insurer_id", sa.CHAR(36), sa.ForeignKey("insurer.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats_json", sa.Text, nullable=True),  # JSONB on Postgres, TEXT on SQLite
        sa.Column("error_summary", sa.Text, nullable=True),
        sa.Column("triggered_by", sa.String(60), nullable=True),
    )
    op.create_index("ix_pipeline_run_insurer", "pipeline_run", ["insurer_id"])
    op.create_index("ix_pipeline_run_status", "pipeline_run", ["status"])

    # --- Extraction Quality Metric ---
    op.create_table(
        "extraction_quality_metric",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("pipeline_run_id", sa.CHAR(36), sa.ForeignKey("pipeline_run.id"), nullable=False),
        sa.Column("insurer_id", sa.CHAR(36), sa.ForeignKey("insurer.id"), nullable=False),
        sa.Column("total_facts_extracted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("facts_verified", sa.Integer, nullable=False, server_default="0"),
        sa.Column("facts_rejected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("verification_rate", sa.Float, nullable=True),
        sa.Column("avg_confidence", sa.Float, nullable=True),
        sa.Column("low_confidence_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
    )
    op.create_index("ix_quality_metric_run", "extraction_quality_metric", ["pipeline_run_id"])


def downgrade() -> None:
    op.drop_table("extraction_quality_metric")
    op.drop_table("pipeline_run")
    op.drop_table("brochure_asset")
    op.drop_table("document_collection")
    op.drop_table("risk_event")
    op.drop_table("risk_area")
