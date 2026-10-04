from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import SourceStatus, SourceType


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A tender portal/registry entry (brief Module 1). `terms_access_notes`
    must be filled in before `crawler_enabled` may be set True — enforced
    in services/source_service.py, not here, so the rule has one readable
    home rather than being buried in a DB constraint.
    """

    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organisation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[SourceType] = mapped_column(
        sa_enum(SourceType), nullable=False, default=SourceType.OTHER
    )
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="India")
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    auth_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    crawler_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_successful_crawl_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SourceStatus] = mapped_column(
        sa_enum(SourceStatus), nullable=False, default=SourceStatus.DISABLED
    )
    terms_access_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenders: Mapped[list["Tender"]] = relationship(back_populates="source")  # noqa: F821
    crawler_runs: Mapped[list["CrawlerRun"]] = relationship(
        back_populates="source", order_by="CrawlerRun.started_at.desc()"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Source {self.name} ({self.source_type.value})>"
