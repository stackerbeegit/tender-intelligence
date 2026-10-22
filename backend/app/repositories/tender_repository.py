import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import exists, func, or_, select, union
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.enums import EligibilityStatus, TenderStatus
from app.models.qualification_result import QualificationResult
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
    eligibility: EligibilityStatus | None = None
    min_relevance: int | None = None
    sort: str = "closing"  # "closing" (soonest first) | "relevance" (highest first)
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
        if filters.state:
            # A tender "belongs to" a state if it delivers there or its buyer
            # sits there — GeM state-government bids often only have the latter.
            state = filters.state.lower()
            stmt = stmt.where(
                or_(
                    exists().where(TenderLocation.tender_id == Tender.id, func.lower(TenderLocation.state) == state),
                    exists().where(
                        TenderOrganisation.id == Tender.organisation_id, func.lower(TenderOrganisation.state) == state
                    ),
                )
            )
        if filters.city:
            stmt = stmt.where(exists().where(TenderLocation.tender_id == Tender.id, TenderLocation.city == filters.city))
        if filters.category:
            # EXISTS rather than a join: a join could repeat a tender and need
            # SELECT DISTINCT, which Postgres won't combine with ordering by
            # the relevance subquery below.
            stmt = stmt.where(
                exists().where(TenderCategory.tender_id == Tender.id, TenderCategory.category == filters.category)
            )
        relevance = (
            select(QualificationResult.relevance_score)
            .where(QualificationResult.tender_id == Tender.id)
            .scalar_subquery()
        )
        if filters.eligibility:
            stmt = stmt.where(
                exists().where(
                    QualificationResult.tender_id == Tender.id,
                    QualificationResult.eligibility_status == filters.eligibility,
                )
            )
        if filters.min_relevance is not None:
            stmt = stmt.where(relevance >= filters.min_relevance)

        total = self.db.scalar(select(func.count()).select_from(stmt.with_only_columns(Tender.id).subquery()))

        order = (
            [relevance.desc().nulls_last(), Tender.closing_date.asc().nulls_last()]
            if filters.sort == "relevance"
            else [Tender.closing_date.asc().nulls_last()]
        )
        stmt = (
            stmt.order_by(*order, Tender.created_at.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        # selectinload (a second IN query), not joinedload: a JOIN would
        # multiply rows and break the LIMIT/OFFSET pagination above.
        items = list(
            self.db.scalars(
                stmt.options(
                    selectinload(Tender.categories),
                    selectinload(Tender.locations),
                    selectinload(Tender.qualification),
                    selectinload(Tender.opportunity),
                )
            ).unique()
        )
        return items, total or 0

    def list_states(self) -> list[str]:
        """Every state any tender delivers to or has a buyer in."""
        stmt = union(
            select(TenderLocation.state).where(TenderLocation.state.is_not(None)),
            select(TenderOrganisation.state).where(TenderOrganisation.state.is_not(None)),
        )
        return sorted(self.db.scalars(stmt).all())
