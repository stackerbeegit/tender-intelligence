"""matching: stackerbee_profile, stackerbee_capabilities,
stackerbee_experience, qualification_results

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20

Sprint 5: the admin-managed company profile that tenders are matched
against, and `qualification_results` — the INTERPRETATION table holding
the eligibility verdict, evidence-linked reasons, relevance factor
breakdown and risks computed by the deterministic engine in
`app/matching/`. No profile data is seeded: it is entered by an admin.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.base import sa_enum, sa_json
from app.models.enums import CustomerType, EligibilityStatus, TenderCategory

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "stackerbee_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("msme_registered", sa.Boolean(), nullable=True),
        sa.Column("msme_certificate_ref", sa.String(length=255), nullable=True),
        sa.Column("startup_registered", sa.Boolean(), nullable=True),
        sa.Column("startup_certificate_ref", sa.String(length=255), nullable=True),
        sa.Column("turnover_by_year", sa_json(), nullable=False),
        sa.Column("net_worth_inr", sa.Numeric(18, 2), nullable=True),
        sa.Column("years_in_business", sa.Integer(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("locations", sa_json(), nullable=False),
        sa.Column("certifications", sa_json(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "stackerbee_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stackerbee_profile.id"), nullable=False
        ),
        sa.Column("capability", sa_enum(TenderCategory), nullable=False),
        sa.Column("technologies", sa_json(), nullable=False),
        sa.Column("certifications", sa_json(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_stackerbee_capabilities_profile_id", "stackerbee_capabilities", ["profile_id"])

    op.create_table(
        "stackerbee_experience",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stackerbee_profile.id"), nullable=False
        ),
        sa.Column("project_name", sa.String(length=500), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("customer_type", sa_enum(CustomerType), nullable=False),
        sa.Column("capability", sa_enum(TenderCategory), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("technologies", sa_json(), nullable=False),
        sa.Column("project_value_inr", sa.Numeric(18, 2), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_stackerbee_experience_profile_id", "stackerbee_experience", ["profile_id"])

    op.create_table(
        "qualification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenders.id"), nullable=False, unique=True
        ),
        sa.Column("eligibility_status", sa_enum(EligibilityStatus), nullable=False),
        sa.Column("reasons", sa_json(), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("relevance_factors", sa_json(), nullable=False),
        sa.Column("risks", sa_json(), nullable=False),
        sa.Column("engine_version", sa.String(length=20), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_qualification_results_relevance_score", "qualification_results", ["relevance_score"])


def downgrade() -> None:
    op.drop_index("ix_qualification_results_relevance_score", table_name="qualification_results")
    op.drop_table("qualification_results")
    op.drop_index("ix_stackerbee_experience_profile_id", table_name="stackerbee_experience")
    op.drop_table("stackerbee_experience")
    op.drop_index("ix_stackerbee_capabilities_profile_id", table_name="stackerbee_capabilities")
    op.drop_table("stackerbee_capabilities")
    op.drop_table("stackerbee_profile")
