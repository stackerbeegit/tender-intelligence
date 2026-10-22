import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum, sa_json
from app.models.enums import CustomerType, TenderCategory


class StackerbeeExperience(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A completed past project — the evidence behind "similar projects" and
    "government experience" eligibility checks. `capability` says which
    focus area it counts as experience in."""

    __tablename__ = "stackerbee_experience"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stackerbee_profile.id"), nullable=False, index=True
    )
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_type: Mapped[CustomerType] = mapped_column(sa_enum(CustomerType), nullable=False)
    capability: Mapped[TenderCategory | None] = mapped_column(sa_enum(TenderCategory), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    technologies: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    project_value_inr: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)  # completion year
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["StackerbeeProfile"] = relationship(back_populates="experience")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StackerbeeExperience {self.project_name[:40]!r}>"
