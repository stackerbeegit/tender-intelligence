import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import ChecklistItemStatus, SubmissionDocumentKind


class BidChecklistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One line of an opportunity's submission checklist — a working copy the
    bid team edits. Items built from a `tender_submission_documents` fact
    copy its name, clause and citation, so they stay readable after a
    re-analysis replaces the fact rows (the link is then set null and
    re-attached by the next sync). Manually added items have no source.
    """

    __tablename__ = "bid_checklist_items"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False, index=True
    )
    submission_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tender_submission_documents.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[SubmissionDocumentKind] = mapped_column(sa_enum(SubmissionDocumentKind), nullable=False)
    mandatory: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    format_instructions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    form_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_clause: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ChecklistItemStatus] = mapped_column(sa_enum(ChecklistItemStatus), nullable=False)
    status_set_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prefill_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="checklist_items")  # noqa: F821
    owner: Mapped["User | None"] = relationship()  # noqa: F821
