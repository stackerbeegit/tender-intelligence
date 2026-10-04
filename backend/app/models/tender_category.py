import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import TenderCategory as TenderCategoryEnum


class TenderCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    `confidence` is null when the category was set directly (manual entry
    today; a human override later) and populated only when the Sprint 4
    intelligence engine assigns it — keeping the fact/interpretation
    distinction from docs/architecture.md §8 visible on this row itself.
    """

    __tablename__ = "tender_categories"

    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    category: Mapped[TenderCategoryEnum] = mapped_column(sa_enum(TenderCategoryEnum), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    tender: Mapped["Tender"] = relationship(back_populates="categories")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderCategory {self.category.value}>"
