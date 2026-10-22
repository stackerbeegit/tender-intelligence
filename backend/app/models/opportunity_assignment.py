import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import OpportunityTeam


class OpportunityAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user working on an opportunity as part of a team. `created_at` is
    when they were assigned."""

    __tablename__ = "opportunity_assignments"
    __table_args__ = (UniqueConstraint("opportunity_id", "user_id", "team", name="uq_opportunity_assignment"),)

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team: Mapped[OpportunityTeam] = mapped_column(sa_enum(OpportunityTeam), nullable=False)
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="assignments")  # noqa: F821
    user: Mapped["User"] = relationship(foreign_keys=[user_id])  # noqa: F821
