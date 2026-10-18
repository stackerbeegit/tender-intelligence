"""
Dashboard metrics (brief §15), computed from real rows.

Only metrics whose underlying data exists are counted. The rest are
returned as `None` with the reason in `pending_metrics`, never as a 0
that would look like a real count:
- Highly Relevant needs relevance scoring (Sprint 5).
- Under Review / Bidding / Submitted / Won / Lost need the opportunity CRM
  (Sprint 6).

"Active" means status OPEN and the closing date hasn't passed (or isn't
known). Status alone isn't enough, since nothing marks a tender CLOSED when
its deadline passes yet.
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import AnalysisStatus, TenderStatus
from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.tender import Tender
from app.models.source import Source
from app.models.tender_analysis import TenderAnalysis
from app.models.tender_location import TenderLocation
from app.models.tender_organisation import TenderOrganisation
from app.models.tender_category import TenderCategory

NEW_TENDER_WINDOW_DAYS = 7
EXPIRING_SOON_WINDOW_DAYS = 7
CLOSING_TIMELINE_DAYS = 14
TOP_STATES = 10
# Deadlines are bucketed by Indian calendar day, which is what bidders plan by.
_IST = ZoneInfo("Asia/Kolkata")

PENDING_METRICS = {
    "highly_relevant": "Needs relevance scoring against the Stackerbee profile (Sprint 5).",
    "under_review": "Needs the opportunity CRM (Sprint 6).",
    "bidding": "Needs the opportunity CRM (Sprint 6).",
    "submitted": "Needs the opportunity CRM (Sprint 6).",
    "won": "Needs the opportunity CRM (Sprint 6).",
    "lost": "Needs the opportunity CRM (Sprint 6).",
}


@dataclass
class DashboardMetrics:
    active_tenders: int
    new_tenders: int
    relevant_tenders: int
    expiring_soon: int
    analysed_tenders: int
    by_category: list[tuple[TenderCategoryEnum, int]]
    by_state: list[tuple[str, int]] = field(default_factory=list)
    closing_timeline: list[tuple[date, int]] = field(default_factory=list)
    last_crawl_at: datetime | None = None
    highly_relevant: int | None = None
    under_review: int | None = None
    bidding: int | None = None
    submitted: int | None = None
    won: int | None = None
    lost: int | None = None
    pending_metrics: dict[str, str] = field(default_factory=lambda: dict(PENDING_METRICS))


def _active(now: datetime) -> Select:
    return select(Tender.id).where(
        Tender.status == TenderStatus.OPEN,
        or_(Tender.closing_date.is_(None), Tender.closing_date >= now),
    )


def _count(db: Session, stmt: Select) -> int:
    return db.scalar(select(func.count()).select_from(stmt.distinct().subquery())) or 0


def get_metrics(db: Session, now: datetime | None = None) -> DashboardMetrics:
    now = now or datetime.now(timezone.utc)
    active = _active(now)
    focus_area = active.join(TenderCategory, TenderCategory.tender_id == Tender.id).where(
        TenderCategory.category != TenderCategoryEnum.OTHER
    )

    by_category_rows = db.execute(
        select(TenderCategory.category, func.count(func.distinct(TenderCategory.tender_id)))
        .where(TenderCategory.tender_id.in_(active))
        .group_by(TenderCategory.category)
        .order_by(func.count(func.distinct(TenderCategory.tender_id)).desc())
    ).all()

    return DashboardMetrics(
        active_tenders=_count(db, active),
        new_tenders=_count(db, active.where(Tender.created_at >= now - timedelta(days=NEW_TENDER_WINDOW_DAYS))),
        relevant_tenders=_count(db, focus_area),
        expiring_soon=_count(
            db, active.where(Tender.closing_date <= now + timedelta(days=EXPIRING_SOON_WINDOW_DAYS))
        ),
        analysed_tenders=db.scalar(
            select(func.count()).select_from(TenderAnalysis).where(TenderAnalysis.status == AnalysisStatus.DONE)
        )
        or 0,
        by_category=[(category, count) for category, count in by_category_rows],
        by_state=_by_state(db, active),
        closing_timeline=_closing_timeline(db, active, now),
        last_crawl_at=db.scalar(select(func.max(Source.last_successful_crawl_at))),
    )


def _by_state(db: Session, active: Select) -> list[tuple[str, int]]:
    """Active tenders per state: the delivery state(s) when known, else the
    buyer's state. A tender delivering to two states counts once in each."""
    states_by_tender: dict = {}
    for tender_id, state in db.execute(
        select(TenderLocation.tender_id, TenderLocation.state).where(
            TenderLocation.tender_id.in_(active), TenderLocation.state.is_not(None)
        )
    ):
        states_by_tender.setdefault(tender_id, set()).add(state)
    for tender_id, state in db.execute(
        select(Tender.id, TenderOrganisation.state)
        .join(TenderOrganisation, TenderOrganisation.id == Tender.organisation_id)
        .where(Tender.id.in_(active), TenderOrganisation.state.is_not(None))
    ):
        states_by_tender.setdefault(tender_id, {state})

    counts = Counter(state for states in states_by_tender.values() for state in states)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:TOP_STATES]


def _closing_timeline(db: Session, active: Select, now: datetime) -> list[tuple[date, int]]:
    """Active tenders closing on each of the next CLOSING_TIMELINE_DAYS days,
    zero-filled so the chart shows quiet days too."""
    end = now + timedelta(days=CLOSING_TIMELINE_DAYS)
    closing_dates = db.scalars(
        select(Tender.closing_date).where(Tender.id.in_(active), Tender.closing_date <= end)
    ).all()
    today = now.astimezone(_IST).date()
    counts = Counter(
        (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(_IST).date() for d in closing_dates
    )
    return [(today + timedelta(days=i), counts.get(today + timedelta(days=i), 0)) for i in range(CLOSING_TIMELINE_DAYS)]
