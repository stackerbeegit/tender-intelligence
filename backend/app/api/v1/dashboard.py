from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    new_tenders: int
    relevant_tenders: int
    highly_relevant: int
    expiring_soon: int
    under_review: int
    bidding: int
    submitted: int
    won: int
    lost: int
    note: str


@router.get("/summary", response_model=DashboardSummary)
def summary(_current_user: User = Depends(get_current_user)) -> DashboardSummary:
    """
    Placeholder metrics. Real counts require `tenders` (Sprint 2) and
    `opportunities` (Sprint 6) to exist — until then this proves the
    authenticated dashboard route end-to-end without inventing data.
    """
    return DashboardSummary(
        new_tenders=0,
        relevant_tenders=0,
        highly_relevant=0,
        expiring_soon=0,
        under_review=0,
        bidding=0,
        submitted=0,
        won=0,
        lost=0,
        note=(
            "Tender ingestion (Sprint 2) and the opportunity CRM (Sprint 6) are not "
            "implemented yet — these counts are placeholders, not real data."
        ),
    )
