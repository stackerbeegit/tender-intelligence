import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.tender import Tender
from app.models.user import User
from app.repositories.tender_repository import TenderRepository
from app.schemas.analysis import (
    AnalysisRunRead,
    CitationRead,
    EligibilityRead,
    RequirementRead,
    TenderAnalysisResponse,
)
from app.services import tender_intelligence_service

router = APIRouter(prefix="/tenders/{tender_id}", tags=["analysis"])


def _get_tender_or_404(db: Session, tender_id: uuid.UUID) -> Tender:
    tender = TenderRepository(db).get_by_id(tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    return tender


def _build_response(tender: Tender) -> TenderAnalysisResponse:
    return TenderAnalysisResponse(
        tender_id=tender.id,
        analysis=AnalysisRunRead.model_validate(tender.analysis) if tender.analysis else None,
        requirements=[
            RequirementRead(
                id=row.id,
                category=row.category,
                summary=row.summary,
                requirement_text=row.requirement_text,
                details=row.details,
                citation=CitationRead(
                    document_id=row.document_id, file_name=row.document.file_name, page_number=row.page_number
                ),
                generated_by_model=row.generated_by_model,
            )
            for row in tender.requirements
        ],
        eligibility=[
            EligibilityRead(
                id=row.id,
                criterion_type=row.criterion_type,
                summary=row.summary,
                criterion_text=row.criterion_text,
                extracted_value=row.extracted_value,
                citation=CitationRead(
                    document_id=row.document_id, file_name=row.document.file_name, page_number=row.page_number
                ),
                generated_by_model=row.generated_by_model,
            )
            for row in tender.eligibility_criteria
        ],
    )


@router.get("/analysis", response_model=TenderAnalysisResponse)
def get_analysis(tender_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return _build_response(_get_tender_or_404(db, tender_id))


@router.post("/analysis", response_model=TenderAnalysisResponse)
def run_analysis(
    tender_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "bd_manager", "technical")),
):
    """Runs extraction + summary synchronously. A failed run still returns
    200: the outcome (status=failed + error) is recorded on the analysis
    itself, and the previous run's facts are left in place."""
    tender = _get_tender_or_404(db, tender_id)
    tender_intelligence_service.analyse_tender(db, tender)
    db.expire_all()
    return _build_response(_get_tender_or_404(db, tender_id))


@router.get("/eligibility", response_model=list[EligibilityRead])
def get_eligibility(tender_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Eligibility FACTS only (brief §19 `/tenders/{id}/eligibility`)."""
    return _build_response(_get_tender_or_404(db, tender_id)).eligibility
