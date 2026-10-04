"""sources, crawler_runs, tender_organisations, tenders, tender_documents,
tender_deadlines, tender_locations, tender_categories

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04

Sprint 2: source registry + tender ingestion schema. See
docs/database.md §2-3 for the full column rationale.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.base import sa_enum, sa_json
from app.models.enums import (
    CrawlerRunStatus,
    DeadlineType,
    DocumentType,
    ExtractionStatus,
    OcrStatus,
    OrganisationType,
    SourceStatus,
    SourceType,
    TenderCategory,
    TenderStatus,
)

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("organisation", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("source_type", sa_enum(SourceType), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False, server_default="India"),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("auth_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("api_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("crawler_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("frequency", sa.String(length=50), nullable=True),
        sa.Column("last_successful_crawl_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa_enum(SourceStatus), nullable=False),
        sa.Column("terms_access_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "crawler_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa_enum(CrawlerRunStatus), nullable=False),
        sa.Column("tenders_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tenders_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tenders_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_crawler_runs_source_id", "crawler_runs", ["source_id"])

    op.create_table(
        "tender_organisations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("normalized_name", sa.String(length=500), nullable=False),
        sa.Column("type", sa_enum(OrganisationType), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_tender_organisations_normalized_name", "tender_organisations", ["normalized_name"], unique=True
    )

    op.create_table(
        "tenders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("source_tender_id", sa.String(length=255), nullable=True),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("tender_number", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column(
            "organisation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tender_organisations.id"), nullable=True
        ),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("closing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tender_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("emd_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("tender_fee", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", sa_enum(TenderStatus), nullable=False),
        sa.Column("raw_metadata", sa_json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tenders_source_tender_id", "tenders", ["source_tender_id"])
    op.create_index("ix_tenders_fingerprint_hash", "tenders", ["fingerprint_hash"], unique=True)
    op.create_index(
        "ix_tenders_source_id_source_tender_id",
        "tenders",
        ["source_id", "source_tender_id"],
        unique=True,
        postgresql_where=sa.text("source_tender_id IS NOT NULL"),
    )

    op.create_table(
        "tender_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("document_type", sa_enum(DocumentType), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("storage_path", sa.String(length=1000), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("ocr_status", sa_enum(OcrStatus), nullable=False),
        sa.Column("extraction_status", sa_enum(ExtractionStatus), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tender_documents_tender_id", "tender_documents", ["tender_id"])

    op.create_table(
        "tender_deadlines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("deadline_type", sa_enum(DeadlineType), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tender_documents.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tender_deadlines_tender_id", "tender_deadlines", ["tender_id"])

    op.create_table(
        "tender_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tender_locations_tender_id", "tender_locations", ["tender_id"])

    op.create_table(
        "tender_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("category", sa_enum(TenderCategory), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tender_categories_tender_id", "tender_categories", ["tender_id"])

    # Seed a 'manual' source so the manual-entry ingestion fallback (Rule 12)
    # has somewhere to attach to out of the box.
    sources = sa.table(
        "sources",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("organisation", sa.String),
        sa.column("url", sa.String),
        sa.column("source_type", sa.String),
        sa.column("country", sa.String),
        sa.column("auth_required", sa.Boolean),
        sa.column("api_available", sa.Boolean),
        sa.column("crawler_enabled", sa.Boolean),
        sa.column("status", sa.String),
        sa.column("terms_access_notes", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    import uuid
    from datetime import datetime, timezone as dt_timezone

    now = datetime.now(dt_timezone.utc)
    op.bulk_insert(
        sources,
        [
            {
                "id": uuid.uuid4(),
                "name": "Manual Entry",
                "organisation": None,
                "url": None,
                "source_type": SourceType.MANUAL.value,
                "country": "India",
                "auth_required": False,
                "api_available": False,
                "crawler_enabled": False,
                "status": SourceStatus.DISABLED.value,
                "terms_access_notes": (
                    "Not a crawled source. Tenders are entered directly by Stackerbee staff "
                    "(Rule 12 manual-upload fallback) — no automated access of any portal."
                ),
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("tender_categories")
    op.drop_table("tender_locations")
    op.drop_table("tender_deadlines")
    op.drop_table("tender_documents")
    op.drop_table("tenders")
    op.drop_table("tender_organisations")
    op.drop_table("crawler_runs")
    op.drop_table("sources")
