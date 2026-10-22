from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, sa_json


class StackerbeeProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    The company's own credentials that tenders are matched against — one
    row, admin-edited (never hardcoded). Nullable fields mean "not recorded"
    and make the matching engine answer UNKNOWN rather than guess, so
    `msme_registered=None` is deliberately different from `False`.

    `turnover_by_year` is a list of `{"financial_year": "2024-25",
    "amount_inr": 123}`; `locations` is a list of state names;
    `certifications` holds company-level certificates (ISO 27001, CMMI
    Level 3, ...).
    """

    __tablename__ = "stackerbee_profile"

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    msme_registered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    msme_certificate_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    startup_registered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    startup_certificate_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    turnover_by_year: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    net_worth_inr: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    years_in_business: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    locations: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)
    certifications: Mapped[list] = mapped_column(sa_json(), default=list, nullable=False)

    capabilities: Mapped[list["StackerbeeCapability"]] = relationship(  # noqa: F821
        back_populates="profile", cascade="all, delete-orphan", order_by="StackerbeeCapability.capability"
    )
    experience: Mapped[list["StackerbeeExperience"]] = relationship(  # noqa: F821
        back_populates="profile", cascade="all, delete-orphan", order_by="StackerbeeExperience.year.desc()"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StackerbeeProfile {self.company_name}>"
