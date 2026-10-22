import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_json


class BidDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    INTERPRETATION: an AI-written draft bid, versioned per opportunity.
    Only stored after `app/bidding/draft.py` has checked that every amount,
    certification and project it mentions is present in its inputs;
    `content` is the assembled document (sections with citations),
    `placeholders` the `[TO FILL: …]` items people must complete. Never
    submitted by the system.
    """

    __tablename__ = "bid_drafts"
    __table_args__ = (UniqueConstraint("opportunity_id", "version", name="uq_bid_draft_version"),)

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(sa_json(), nullable=False)
    placeholders: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    generated_by_model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="bid_drafts")  # noqa: F821
    created_by: Mapped["User | None"] = relationship()  # noqa: F821
