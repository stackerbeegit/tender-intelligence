"""opportunity CRM, notifications, submission documents, bid preparation

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22

Sprint 6:
- `tender_submission_documents` — FACT table of documents a tender says
  must be submitted (citation-verified like the Sprint 4 facts). Existing
  tenders get rows on their next analysis run.
- `opportunities` + assignments, notes and the append-only status history.
- `notifications` — every e-mail attempted and its outcome.
- `bid_checklist_items` and `bid_drafts` — the per-opportunity bid pack.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.base import sa_enum, sa_json
from app.models.enums import (
    ChecklistItemStatus,
    NotificationStatus,
    OpportunityOrigin,
    OpportunityStatus,
    OpportunityTeam,
    SubmissionDocumentKind,
)

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "tender_submission_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tender_id", UUID, sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("document_id", UUID, sa.ForeignKey("tender_documents.id"), nullable=False),
        sa.Column("kind", sa_enum(SubmissionDocumentKind), nullable=False),
        sa.Column("document_name", sa.String(length=500), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=True),
        sa.Column("format_instructions", sa.String(length=500), nullable=True),
        sa.Column("form_reference", sa.String(length=500), nullable=True),
        sa.Column("clause_text", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("generated_by_model", sa.String(length=100), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_tender_submission_documents_tender_id", "tender_submission_documents", ["tender_id"])

    op.create_table(
        "opportunities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tender_id", UUID, sa.ForeignKey("tenders.id"), nullable=False, unique=True),
        sa.Column("status", sa_enum(OpportunityStatus), nullable=False),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_from", sa_enum(OpportunityOrigin), nullable=False),
        sa.Column("created_by_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_opportunities_status", "opportunities", ["status"])

    op.create_table(
        "opportunity_assignments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("opportunity_id", UUID, sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team", sa_enum(OpportunityTeam), nullable=False),
        sa.Column("assigned_by_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("opportunity_id", "user_id", "team", name="uq_opportunity_assignment"),
    )
    op.create_index("ix_opportunity_assignments_opportunity_id", "opportunity_assignments", ["opportunity_id"])

    op.create_table(
        "opportunity_notes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("opportunity_id", UUID, sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("author_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_opportunity_notes_opportunity_id", "opportunity_notes", ["opportunity_id"])

    op.create_table(
        "opportunity_status_history",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("opportunity_id", UUID, sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("from_status", sa_enum(OpportunityStatus), nullable=True),
        sa.Column("to_status", sa_enum(OpportunityStatus), nullable=False),
        sa.Column("changed_by_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_opportunity_status_history_opportunity_id", "opportunity_status_history", ["opportunity_id"]
    )

    op.create_table(
        "notifications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("status", sa_enum(NotificationStatus), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "bid_checklist_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("opportunity_id", UUID, sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column(
            "submission_document_id",
            UUID,
            sa.ForeignKey("tender_submission_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("kind", sa_enum(SubmissionDocumentKind), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=True),
        sa.Column("format_instructions", sa.String(length=500), nullable=True),
        sa.Column("form_reference", sa.String(length=500), nullable=True),
        sa.Column("source_clause", sa.Text(), nullable=True),
        sa.Column("source_file_name", sa.String(length=500), nullable=True),
        sa.Column("source_document_id", UUID, nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("is_manual", sa.Boolean(), nullable=False),
        sa.Column("status", sa_enum(ChecklistItemStatus), nullable=False),
        sa.Column("status_set_by_user", sa.Boolean(), nullable=False),
        sa.Column("prefill_reason", sa.String(length=500), nullable=True),
        sa.Column("owner_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_bid_checklist_items_opportunity_id", "bid_checklist_items", ["opportunity_id"])

    op.create_table(
        "bid_drafts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("opportunity_id", UUID, sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa_json(), nullable=False),
        sa.Column("placeholders", sa_json(), nullable=False),
        sa.Column("generated_by_model", sa.String(length=100), nullable=False),
        sa.Column("created_by_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("opportunity_id", "version", name="uq_bid_draft_version"),
    )
    op.create_index("ix_bid_drafts_opportunity_id", "bid_drafts", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_bid_drafts_opportunity_id", table_name="bid_drafts")
    op.drop_table("bid_drafts")
    op.drop_index("ix_bid_checklist_items_opportunity_id", table_name="bid_checklist_items")
    op.drop_table("bid_checklist_items")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_opportunity_status_history_opportunity_id", table_name="opportunity_status_history")
    op.drop_table("opportunity_status_history")
    op.drop_index("ix_opportunity_notes_opportunity_id", table_name="opportunity_notes")
    op.drop_table("opportunity_notes")
    op.drop_index("ix_opportunity_assignments_opportunity_id", table_name="opportunity_assignments")
    op.drop_table("opportunity_assignments")
    op.drop_index("ix_opportunities_status", table_name="opportunities")
    op.drop_table("opportunities")
    op.drop_index("ix_tender_submission_documents_tender_id", table_name="tender_submission_documents")
    op.drop_table("tender_submission_documents")
