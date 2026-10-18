import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum, sa_json
from app.models.enums import RequirementCategory


class TenderRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    FACT table (docs/architecture.md §8). `requirement_text` is a verbatim
    quote from the document, and the intelligence layer only stores a row
    after checking that quote actually occurs on `page_number` of
    `document_id` (app/intelligence/extraction/citations.py). `details`
    holds structured fields read off that same clause (e.g. a manpower
    row's role/count/experience) — still fact, never a Stackerbee-relative
    judgement.
    """

    __tablename__ = "tender_requirements"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tender_documents.id"), nullable=False
    )
    category: Mapped[RequirementCategory] = mapped_column(sa_enum(RequirementCategory), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(sa_json(), default=dict, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-indexed
    generated_by_model: Mapped[str] = mapped_column(String(100), nullable=False)

    tender: Mapped["Tender"] = relationship(back_populates="requirements")  # noqa: F821
    document: Mapped["TenderDocument"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderRequirement {self.category.value}: {self.summary[:40]!r}>"
