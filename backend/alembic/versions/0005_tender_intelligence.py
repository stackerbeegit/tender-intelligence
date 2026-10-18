"""tender intelligence: tender_requirements, tender_eligibility,
tender_analysis; tender_documents.extracted_pages

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-04

Sprint 4: LLM-backed structured extraction. Requirements and eligibility
criteria are FACT tables (verbatim clause + document + page, verified in
code before insert); tender_analysis holds the AI-generated summary
(INTERPRETATION) and run status. `extracted_pages` keeps per-page text
so citations can name a page — documents processed before this migration
have it null and are re-processed automatically on their next analysis.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.base import sa_enum, sa_json
from app.models.enums import AnalysisStatus, EligibilityCriterionType, RequirementCategory

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("tender_documents", sa.Column("extracted_pages", sa_json(), nullable=True))

    op.create_table(
        "tender_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tender_documents.id"), nullable=False
        ),
        sa.Column("category", sa_enum(RequirementCategory), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("details", sa_json(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("generated_by_model", sa.String(length=100), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_tender_requirements_tender_id", "tender_requirements", ["tender_id"])

    op.create_table(
        "tender_eligibility",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column(
            "document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tender_documents.id"), nullable=False
        ),
        sa.Column("criterion_type", sa_enum(EligibilityCriterionType), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("criterion_text", sa.Text(), nullable=False),
        sa.Column("extracted_value", sa_json(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("generated_by_model", sa.String(length=100), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_tender_eligibility_tender_id", "tender_eligibility", ["tender_id"])

    op.create_table(
        "tender_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False, unique=True
        ),
        sa.Column("status", sa_enum(AnalysisStatus), nullable=False),
        sa.Column("summary", sa_json(), nullable=True),
        sa.Column("run_stats", sa_json(), nullable=False),
        sa.Column("documents_analysed", sa.Integer(), nullable=False),
        sa.Column("generated_by_model", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
    )


def downgrade() -> None:
    op.drop_table("tender_analysis")
    op.drop_index("ix_tender_eligibility_tender_id", table_name="tender_eligibility")
    op.drop_table("tender_eligibility")
    op.drop_index("ix_tender_requirements_tender_id", table_name="tender_requirements")
    op.drop_table("tender_requirements")
    op.drop_column("tender_documents", "extracted_pages")
