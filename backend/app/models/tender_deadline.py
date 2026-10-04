import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import DeadlineType


class TenderDeadline(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One deadline event. Corrigenda that move a submission date create a
    *new* row with deadline_type=EXTENDED rather than overwriting the
    original — so the full history survives (brief: "Test changed tender
    deadlines"). `tenders.closing_date` always mirrors the latest
    bid_submission/extended deadline for quick filtering.
    """

    __tablename__ = "tender_deadlines"

    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    deadline_type: Mapped[DeadlineType] = mapped_column(sa_enum(DeadlineType), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tender_documents.id"), nullable=True
    )

    tender: Mapped["Tender"] = relationship(back_populates="deadlines")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderDeadline {self.deadline_type.value} {self.deadline_at}>"
