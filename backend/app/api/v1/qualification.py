import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.tender import Tender
from app.models.user import User
from app.repositories.tender_repository import TenderRepository
from app.schemas.qualification import QualificationRead, QualificationResponse
from app.services import profile_service, qualification_service
from app.services.profile_service import ProfileNotConfiguredError

router = APIRouter(prefix="/tenders/{tender_id}", tags=["qualification"])


def _get_tender_or_404(db: Session, tender_id: uuid.UUID) -> Tender:
    tender = TenderRepository(db).get_by_id(tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    return tender


def _build_response(db: Session, tender: Tender) -> QualificationResponse:
    profile = profile_service.get_profile(db)
    result = tender.qualification
    return QualificationResponse(
        tender_id=tender.id,
        profile_configured=profile is not None,
        is_stale=result is not None and qualification_service.is_stale(tender, result, profile),
        qualification=QualificationRead.model_validate(result) if result else None,
    )


@router.get("/qualification", response_model=QualificationResponse)
def get_qualification(tender_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """The stored result as computed — not recomputed on read; `is_stale`
    says whether its inputs have changed since."""
    return _build_response(db, _get_tender_or_404(db, tender_id))


@router.post("/qualification", response_model=QualificationResponse)
def compute_qualification(
    tender_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "bd_manager", "technical")),
):
    """Re-runs the deterministic matching engine. Fast (no model call), so
    it runs inline."""
    tender = _get_tender_or_404(db, tender_id)
    try:
        qualification_service.compute(db, tender)
    except ProfileNotConfiguredError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Set up the company profile before computing qualification"
        )
    db.expire_all()
    return _build_response(db, _get_tender_or_404(db, tender_id))
