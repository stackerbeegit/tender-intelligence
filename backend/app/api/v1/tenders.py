import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.exceptions import DomainError
from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.enums import EligibilityStatus, TenderStatus
from app.models.user import User
from app.repositories.tender_repository import TenderFilter, TenderRepository
from app.schemas.tender import ManualTenderCreate, TenderDetail, TenderListResponse
from app.services import manual_tender_service

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("", response_model=TenderListResponse)
def list_tenders(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    keyword: str | None = Query(default=None),
    source_id: uuid.UUID | None = Query(default=None),
    state: str | None = Query(default=None),
    city: str | None = Query(default=None),
    category: TenderCategoryEnum | None = Query(default=None),
    min_value: Decimal | None = Query(default=None),
    max_value: Decimal | None = Query(default=None),
    closing_after: datetime | None = Query(default=None),
    closing_before: datetime | None = Query(default=None),
    status_filter: TenderStatus | None = Query(default=None, alias="status"),
    eligibility: EligibilityStatus | None = Query(default=None),
    min_relevance: int | None = Query(default=None, ge=0, le=100),
    sort: str = Query(default="closing", pattern="^(closing|relevance)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> TenderListResponse:
    filters = TenderFilter(
        keyword=keyword,
        source_id=source_id,
        state=state,
        city=city,
        category=category,
        min_value=min_value,
        max_value=max_value,
        closing_after=closing_after,
        closing_before=closing_before,
        status=status_filter,
        eligibility=eligibility,
        min_relevance=min_relevance,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    items, total = TenderRepository(db).search(filters)
    return TenderListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/states", response_model=list[str])
def list_tender_states(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[str]:
    return TenderRepository(db).list_states()


@router.get("/{tender_id}", response_model=TenderDetail)
def get_tender(tender_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    tender = TenderRepository(db).get_by_id(tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    return tender


@router.post("/manual", response_model=TenderDetail, status_code=status.HTTP_201_CREATED)
def create_manual_tender(
    payload: ManualTenderCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "bd_manager", "technical")),
):
    try:
        tender, _created = manual_tender_service.create_manual_tender(db, payload)
    except DomainError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return TenderRepository(db).get_by_id(tender.id)
