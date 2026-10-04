import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TenderLocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tender may span multiple delivery locations."""

    __tablename__ = "tender_locations"

    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)

    tender: Mapped["Tender"] = relationship(back_populates="locations")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderLocation {self.city}, {self.state}>"
