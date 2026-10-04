"""tender_documents: extracted_text + last_processing_error

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-04

Sprint 3: document processing pipeline needs somewhere to put extracted
text (used by the LLM intelligence layer in Sprint 4) and a readable
error message when download/validation/extraction/OCR fails on a given
document — never silently swallowed (brief Rule 6).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tender_documents", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column("tender_documents", sa.Column("last_processing_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tender_documents", "last_processing_error")
    op.drop_column("tender_documents", "extracted_text")
