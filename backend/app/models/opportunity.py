import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import OpportunityOrigin, OpportunityStatus


class Opportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A tender the company is actively pursuing (docs/architecture.md §10).
    One per tender. `status` only changes through
    `opportunity_service.transition()`, which writes the append-only
    `opportunity_status_history` row in the same commit.
    """

    __tablename__ = "opportunities"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False, unique=True
    )
    status: Mapped[OpportunityStatus] = mapped_column(sa_enum(OpportunityStatus), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_from: Mapped[OpportunityOrigin] = mapped_column(sa_enum(OpportunityOrigin), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True  # null = created by the system
    )
    title: Mapped[str] = mapped_column(String(1000), nullable=False)  # tender title at creation, for lists/emails

    tender: Mapped["Tender"] = relationship(back_populates="opportunity")  # noqa: F821
    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_id])  # noqa: F821
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])  # noqa: F821
    assignments: Mapped[list["OpportunityAssignment"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan", order_by="OpportunityAssignment.created_at"
    )
    notes: Mapped[list["OpportunityNote"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan", order_by="OpportunityNote.created_at.desc()"
    )
    status_history: Mapped[list["OpportunityStatusHistory"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan", order_by="OpportunityStatusHistory.changed_at"
    )
    checklist_items: Mapped[list["BidChecklistItem"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan", order_by="BidChecklistItem.position"
    )
    bid_drafts: Mapped[list["BidDraft"]] = relationship(  # noqa: F821
        back_populates="opportunity", cascade="all, delete-orphan", order_by="BidDraft.version.desc()"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Opportunity {self.title[:40]!r} {self.status.value}>"
