import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import OpportunityStatus


class OpportunityStatusHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only audit trail of every status change. `from_status` is null
    for the creation row; `changed_by_id` is null when the system acted
    (auto-promotion by relevance)."""

    __tablename__ = "opportunity_status_history"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False, index=True
    )
    from_status: Mapped[OpportunityStatus | None] = mapped_column(sa_enum(OpportunityStatus), nullable=True)
    to_status: Mapped[OpportunityStatus] = mapped_column(sa_enum(OpportunityStatus), nullable=False)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="status_history")  # noqa: F821
    changed_by: Mapped["User | None"] = relationship()  # noqa: F821
