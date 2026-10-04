from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_enum
from app.models.enums import OrganisationType


class TenderOrganisation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Normalised buyer identity. `normalized_name` (lowercased, whitespace-
    collapsed) is the get-or-create key used by the ingestion service so
    "XYZ Dept." and "xyz dept" don't become two rows.
    """

    __tablename__ = "tender_organisations"

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    type: Mapped[OrganisationType] = mapped_column(
        sa_enum(OrganisationType), nullable=False, default=OrganisationType.OTHER
    )
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    tenders: Mapped[list["Tender"]] = relationship(back_populates="organisation")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TenderOrganisation {self.name}>"
