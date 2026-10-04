import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.enums import TenderStatus
from app.models.tender import Tender
from app.models.tender_category import TenderCategory
from app.models.tender_location import TenderLocation
from app.models.tender_organisation import TenderOrganisation


@dataclass
class TenderFilter:
    keyword: str | None = None
    source_id: uuid.UUID | None = None
    state: str | None = None
    city: str | None = None
    category: TenderCategoryEnum | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    closing_after: datetime | None = None
    closing_before: datetime | None = None
    status: TenderStatus | None = None
    page: int = 1
    page_size: int = 20


class TenderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, tender_id: uuid.UUID) -> Tender | None:
        stmt = (
            select(Tender)
            .options(
                joinedload(Tender.organisation),
                joinedload(Tender.locations),
                joinedload(Tender.categories),
                joinedload(Tender.deadlines),
                joinedload(Tender.documents),
            )
            .where(Tender.id == tender_id)
        )
        return self.db.scalar(stmt)

    def search(self, filters: TenderFilter) -> tuple[list[Tender], int]:
        stmt = select(Tender).options(joinedload(Tender.organisation))

        if filters.keyword:
            pattern = f"%{filters.keyword.lower()}%"
            stmt = stmt.outerjoin(TenderOrganisation, Tender.organisation_id == TenderOrganisation.id).where(
                or_(
                    func.lower(Tender.title).like(pattern),
                    func.lower(Tender.tender_number).like(pattern),
                    func.lower(TenderOrganisation.name).like(pattern),
                )
            )
        if filters.source_id:
            stmt = stmt.where(Tender.source_id == filters.source_id)
        if filters.status:
            stmt = stmt.where(Tender.status == filters.status)
        if filters.min_value is not None:
            stmt = stmt.where(Tender.tender_value >= filters.min_value)
        if filters.max_value is not None:
            stmt = stmt.where(Tender.tender_value <= filters.max_value)
        if filters.closing_after:
            stmt = stmt.where(Tender.closing_date >= filters.closing_after)
        if filters.closing_before:
            stmt = stmt.where(Tender.closing_date <= filters.closing_before)
        if filters.state or filters.city:
            stmt = stmt.join(TenderLocation, TenderLocation.tender_id == Tender.id)
            if filters.state:
                stmt = stmt.where(TenderLocation.state == filters.state)
            if filters.city:
                stmt = stmt.where(TenderLocation.city == filters.city)
        if filters.category:
            stmt = stmt.join(TenderCategory, TenderCategory.tender_id == Tender.id).where(
                TenderCategory.category == filters.category
            )

        stmt = stmt.distinct()

        total = self.db.scalar(select(func.count()).select_from(stmt.with_only_columns(Tender.id).subquery()))

        stmt = (
            stmt.order_by(Tender.closing_date.asc().nulls_last(), Tender.created_at.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        items = list(self.db.scalars(stmt).unique())
        return items, total or 0
