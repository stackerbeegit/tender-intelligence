import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OpportunityNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "opportunity_notes"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="notes")  # noqa: F821
    author: Mapped["User"] = relationship()  # noqa: F821
