import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import CrawlerRunStatus


class CrawlerRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One execution of a source's connector, recorded by CrawlerRunner.
    Powers the admin "Source Health" view (brief §21)."""

    __tablename__ = "crawler_runs"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[CrawlerRunStatus] = mapped_column(
        sa_enum(CrawlerRunStatus), nullable=False, default=CrawlerRunStatus.RUNNING
    )
    tenders_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tenders_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tenders_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped["Source"] = relationship(back_populates="crawler_runs")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CrawlerRun {self.source_id} {self.status.value}>"
