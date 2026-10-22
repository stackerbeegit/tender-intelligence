import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum, sa_json
from app.models.enums import EligibilityStatus


class QualificationResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    INTERPRETATION table (docs/architecture.md §7–8): how this tender's
    verified facts compare to the company profile. Computed by
    deterministic rules in `app/matching/` — no model call — so the same
    facts and profile always give the same result.

    - `reasons`: one entry per eligibility fact checked, each with its
      outcome and evidence (the `tender_eligibility` row and the profile
      data it was compared to).
    - `relevance_factors`: `{name: {score, weight, known, explanation,
      evidence}}`. `relevance_score` is always
      `round(sum(score * weight) / sum(weight))` over these — stored for
      sorting, never as a number without its breakdown.
    - `risks`: `{risk, severity, explanation, evidence, document_id,
      file_name, page}` entries, independent of the verdict.
    """

    __tablename__ = "qualification_results"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, unique=True
    )
    eligibility_status: Mapped[EligibilityStatus] = mapped_column(sa_enum(EligibilityStatus), nullable=False)
    reasons: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    relevance_factors: Mapped[dict] = mapped_column(sa_json(), default=dict, nullable=False)
    risks: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tender: Mapped["Tender"] = relationship(back_populates="qualification")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QualificationResult tender={self.tender_id} {self.eligibility_status.value} {self.relevance_score}>"
