"""
Shared base/mixins for ORM models. Every table gets a UUID primary key and
created_at/updated_at timestamps via `TimestampMixin`, per the convention in
`docs/database.md`.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Type

import sqlalchemy as sa
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["Base", "UUIDPrimaryKeyMixin", "TimestampMixin", "sa_enum", "sa_json"]


def sa_enum(enum_cls: Type[Enum], length: int = 50) -> sa.Enum:
    """
    A `str` Enum stored as a plain VARCHAR with DB-level CHECK validation
    (`native_enum=False`), rather than a Postgres native enum type — this
    keeps the same column definition portable to the SQLite test database
    and avoids ALTER TYPE migrations whenever a new enum member is added.
    """
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [member.value for member in cls],
    )


def sa_json() -> sa.JSON:
    """
    JSONB on Postgres, plain JSON (TEXT-backed) on SQLite. Plain Postgres
    `json` has no equality operator, which breaks any query needing
    `SELECT DISTINCT` on a row containing that column (as tender search
    does) — `jsonb` supports equality, so always use this helper instead
    of bare `sa.JSON()` for any JSON column.
    """
    return sa.JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
