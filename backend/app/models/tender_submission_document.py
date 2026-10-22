import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import SubmissionDocumentKind


class TenderSubmissionDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    FACT table (Sprint 6): a document the tender says bidders must submit.
    Same guarantee as `TenderRequirement` — `clause_text` is verified to
    occur on `page_number` of `document_id` before the row is stored.
    `mandatory` is null when the clause doesn't say.
    """

    __tablename__ = "tender_submission_documents"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tender_documents.id"), nullable=False
    )
    kind: Mapped[SubmissionDocumentKind] = mapped_column(sa_enum(SubmissionDocumentKind), nullable=False)
    document_name: Mapped[str] = mapped_column(String(500), nullable=False)
    mandatory: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    format_instructions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    form_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    clause_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-indexed
    generated_by_model: Mapped[str] = mapped_column(String(100), nullable=False)

    tender: Mapped["Tender"] = relationship(back_populates="submission_documents")  # noqa: F821
    document: Mapped["TenderDocument"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderSubmissionDocument {self.kind.value}: {self.document_name[:40]!r}>"
