import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum, sa_json
from app.models.enums import AnalysisStatus


class TenderAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per tender: the state of its latest intelligence run plus the
    AI-generated executive summary. The summary is INTERPRETATION — it is
    written from the already-verified fact rows, not from raw document
    text, and the UI always labels it AI-generated.

    `summary` (jsonb) holds the structured summary sections; `run_stats`
    records what the run did (pages read, LLM calls, facts kept, facts
    dropped because their quote could not be found on the cited page) so
    a reviewer can see how much was discarded rather than it vanishing.
    """

    __tablename__ = "tender_analysis"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, unique=True
    )
    status: Mapped[AnalysisStatus] = mapped_column(sa_enum(AnalysisStatus), nullable=False)
    summary: Mapped[dict | None] = mapped_column(sa_json(), nullable=True)
    run_stats: Mapped[dict] = mapped_column(sa_json(), default=dict, nullable=False)
    documents_analysed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_by_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    tender: Mapped["Tender"] = relationship(back_populates="analysis")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderAnalysis tender={self.tender_id} {self.status.value}>"
