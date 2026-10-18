import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum, sa_json
from app.models.enums import TenderStatus


class Tender(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Core tender record (brief Module 3). `fingerprint_hash` and
    `(source_id, source_tender_id)` are the two dedup keys — see
    app/services/tender_ingestion_service.py for how they're used.
    """

    __tablename__ = "tenders"

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    source_tender_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    tender_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tender_organisations.id"), nullable=True
    )
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tender_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    emd_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tender_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[TenderStatus] = mapped_column(sa_enum(TenderStatus), nullable=False, default=TenderStatus.OPEN)
    raw_metadata: Mapped[dict] = mapped_column(sa_json(), default=dict, nullable=False)

    source: Mapped["Source"] = relationship(back_populates="tenders")  # noqa: F821
    organisation: Mapped["TenderOrganisation | None"] = relationship(back_populates="tenders")  # noqa: F821
    locations: Mapped[list["TenderLocation"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    categories: Mapped[list["TenderCategory"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    deadlines: Mapped[list["TenderDeadline"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan", order_by="TenderDeadline.deadline_at"
    )
    documents: Mapped[list["TenderDocument"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    requirements: Mapped[list["TenderRequirement"]] = relationship(  # noqa: F821
        back_populates="tender", cascade="all, delete-orphan", order_by="TenderRequirement.page_number"
    )
    eligibility_criteria: Mapped[list["TenderEligibility"]] = relationship(  # noqa: F821
        back_populates="tender", cascade="all, delete-orphan", order_by="TenderEligibility.page_number"
    )
    analysis: Mapped["TenderAnalysis | None"] = relationship(  # noqa: F821
        back_populates="tender", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tender {self.title[:40]!r}>"
