import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum, sa_json
from app.models.enums import EligibilityCriterionType


class TenderEligibility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    FACT table for eligibility/qualification clauses — what the tender
    *requires*, never whether Stackerbee meets it (that comparison is
    Sprint 5's `qualification_results`, an interpretation table).
    `extracted_value` carries the numbers Sprint 5's deterministic
    comparisons need, e.g. `{"amount_inr": 100000000, "period_years": 3}`.
    Same citation guarantee as `TenderRequirement`.
    """

    __tablename__ = "tender_eligibility"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tender_documents.id"), nullable=False
    )
    criterion_type: Mapped[EligibilityCriterionType] = mapped_column(
        sa_enum(EligibilityCriterionType), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    criterion_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_value: Mapped[dict] = mapped_column(sa_json(), default=dict, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-indexed
    generated_by_model: Mapped[str] = mapped_column(String(100), nullable=False)

    tender: Mapped["Tender"] = relationship(back_populates="eligibility_criteria")  # noqa: F821
    document: Mapped["TenderDocument"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderEligibility {self.criterion_type.value}: {self.summary[:40]!r}>"
