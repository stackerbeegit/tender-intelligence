"""convert json columns to jsonb

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04

Plain Postgres `json` has no equality operator, which breaks any query
needing `SELECT DISTINCT` on a row containing that column — exactly what
tender search does once `tenders.raw_metadata` is in the selected columns.
`jsonb` supports equality. Migrations 0001/0002 now create these columns
as jsonb directly for fresh installs; this migration repairs databases
that already ran the original json-typed versions (safe to run even if a
column is already jsonb — the cast is a no-op then).

SQLite ignores this migration's DDL in all but name — `ALTER COLUMN TYPE`
is Postgres-specific, so this migration is a no-op on SQLite test runs
(see downgrade/upgrade guarded by dialect below).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ("roles", "permissions"),
    ("audit_logs", "details"),
    ("tenders", "raw_metadata"),
]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE jsonb USING {column}::text::jsonb")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column in _COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE json USING {column}::text::json")
