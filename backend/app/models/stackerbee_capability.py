import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum, sa_json
from app.models.enums import TenderCategory


class StackerbeeCapability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One focus area the company delivers in, keyed by the same
    `TenderCategory` enum tenders are classified with, so technical fit is
    a direct comparison rather than fuzzy text matching."""

    __tablename__ = "stackerbee_capabilities"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stackerbee_profile.id"), nullable=False, index=True
    )
    capability: Mapped[TenderCategory] = mapped_column(sa_enum(TenderCategory), nullable=False)
    technologies: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    certifications: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["StackerbeeProfile"] = relationship(back_populates="capabilities")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StackerbeeCapability {self.capability.value}>"
