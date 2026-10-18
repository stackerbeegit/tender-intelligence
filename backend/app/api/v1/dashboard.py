from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.user import User
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class CategoryCount(BaseModel):
    category: TenderCategoryEnum
    count: int


class StateCount(BaseModel):
    state: str
    count: int


class DayCount(BaseModel):
    date: date
    count: int


class DashboardSummary(BaseModel):
    """`None` means "not computable yet" (see `pending_metrics` for why),
    as opposed to a real count of 0."""

    active_tenders: int
    new_tenders: int
    relevant_tenders: int
    expiring_soon: int
    analysed_tenders: int
    highly_relevant: int | None
    under_review: int | None
    bidding: int | None
    submitted: int | None
    won: int | None
    lost: int | None
    by_category: list[CategoryCount]
    by_state: list[StateCount]
    closing_timeline: list[DayCount]
    last_crawl_at: datetime | None
    pending_metrics: dict[str, str]
    new_window_days: int
    expiring_window_days: int


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)) -> DashboardSummary:
    metrics = dashboard_service.get_metrics(db)
    return DashboardSummary(
        active_tenders=metrics.active_tenders,
        new_tenders=metrics.new_tenders,
        relevant_tenders=metrics.relevant_tenders,
        expiring_soon=metrics.expiring_soon,
        analysed_tenders=metrics.analysed_tenders,
        highly_relevant=metrics.highly_relevant,
        under_review=metrics.under_review,
        bidding=metrics.bidding,
        submitted=metrics.submitted,
        won=metrics.won,
        lost=metrics.lost,
        by_category=[CategoryCount(category=c, count=n) for c, n in metrics.by_category],
        by_state=[StateCount(state=s, count=n) for s, n in metrics.by_state],
        closing_timeline=[DayCount(date=d, count=n) for d, n in metrics.closing_timeline],
        last_crawl_at=metrics.last_crawl_at,
        pending_metrics=metrics.pending_metrics,
        new_window_days=dashboard_service.NEW_TENDER_WINDOW_DAYS,
        expiring_window_days=dashboard_service.EXPIRING_SOON_WINDOW_DAYS,
    )
