import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.v1.opportunities import _brief, get_opportunity_or_404
from app.bidding.draft import DraftGroundingError
from app.core.database import get_db
from app.core.exceptions import LLMNotConfiguredError, LLMResponseError
from app.models.bid_checklist_item import BidChecklistItem
from app.models.opportunity import Opportunity
from app.models.user import User
from app.repositories.tender_repository import TenderRepository
from app.schemas.opportunity import (
    BidDraftRead,
    BidDraftVersion,
    BidPreparationRead,
    BidPreparationStartResponse,
    ChecklistItemCreate,
    ChecklistItemRead,
    ChecklistItemUpdate,
)
from app.services import audit_service, bid_preparation_service, profile_service
from app.services.bid_preparation_service import TenderNotAnalysedError
from app.services.opportunity_service import CRM_ROLES, NOTE_ROLES
from app.services.profile_service import ProfileNotConfiguredError

router = APIRouter(tags=["bid preparation"])

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _read(db: Session, opportunity: Opportunity, user: User) -> BidPreparationRead:
    tender = opportunity.tender
    drafts = opportunity.bid_drafts  # newest first
    latest = drafts[0] if drafts else None
    return BidPreparationRead(
        opportunity_id=opportunity.id,
        tender_id=tender.id,
        tender_analysed=bool(tender.requirements or tender.eligibility_criteria or tender.submission_documents),
        profile_configured=profile_service.get_profile(db) is not None,
        checklist=[
            ChecklistItemRead.model_validate(item).model_copy(update={"owner": _brief(item.owner)})
            for item in opportunity.checklist_items
        ],
        latest_draft=(
            BidDraftRead.model_validate(latest).model_copy(update={"created_by": _brief(latest.created_by)})
            if latest
            else None
        ),
        draft_versions=[
            BidDraftVersion(
                id=d.id,
                version=d.version,
                created_at=d.created_at,
                created_by=_brief(d.created_by),
                placeholder_count=len(d.placeholders),
            )
            for d in drafts
        ],
        can_prepare=user.role.name in CRM_ROLES,
        can_edit_checklist=user.role.name in NOTE_ROLES,
    )


@router.post("/tenders/{tender_id}/bid-preparation", response_model=BidPreparationStartResponse)
def start_bid_preparation(
    tender_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(*CRM_ROLES))
):
    """'Interested — prepare bid': makes the tender an opportunity (if it
    isn't one), assigns the caller, builds the submission checklist and
    tries to write a draft. A draft that can't be written (no profile, not
    analysed, no model configured, or rejected by the grounding check) is
    reported in `draft_error`/`draft_problems`; the checklist is still
    returned. Does not change the opportunity's status."""
    tender = TenderRepository(db).get_by_id(tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    outcome = bid_preparation_service.prepare_bid(db, tender, user)
    db.expire_all()
    opportunity = get_opportunity_or_404(db, outcome.opportunity.id)
    return BidPreparationStartResponse(
        **_read(db, opportunity, user).model_dump(),
        opportunity_created=outcome.created,
        draft_error=outcome.draft_error,
        draft_problems=outcome.draft_problems,
    )


@router.get("/opportunities/{opportunity_id}/bid-preparation", response_model=BidPreparationRead)
def get_bid_preparation(
    opportunity_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _read(db, get_opportunity_or_404(db, opportunity_id), user)


@router.post("/opportunities/{opportunity_id}/bid-drafts", response_model=BidDraftRead, status_code=status.HTTP_201_CREATED)
def generate_draft(
    opportunity_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(*CRM_ROLES))
):
    opportunity = get_opportunity_or_404(db, opportunity_id)
    try:
        draft = bid_preparation_service.generate_draft(db, opportunity, user)
    except DraftGroundingError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": str(exc), "problems": exc.problems}
        )
    except ProfileNotConfiguredError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Set up the company profile before generating a draft")
    except TenderNotAnalysedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    except LLMNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except LLMResponseError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return BidDraftRead.model_validate(draft).model_copy(update={"created_by": _brief(draft.created_by)})


@router.post("/opportunities/{opportunity_id}/checklist/sync", response_model=BidPreparationRead)
def sync_checklist(
    opportunity_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles(*NOTE_ROLES))
):
    """Picks up documents found by a newer analysis run; keeps every status
    a person has set."""
    opportunity = get_opportunity_or_404(db, opportunity_id)
    bid_preparation_service.sync_checklist(db, opportunity)
    return _read(db, opportunity, user)


@router.post(
    "/opportunities/{opportunity_id}/checklist", response_model=ChecklistItemRead, status_code=status.HTTP_201_CREATED
)
def add_checklist_item(
    opportunity_id: uuid.UUID,
    payload: ChecklistItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*NOTE_ROLES)),
):
    item = bid_preparation_service.add_manual_item(db, get_opportunity_or_404(db, opportunity_id), payload.title, user)
    return ChecklistItemRead.model_validate(item)


def _get_item_or_404(db: Session, opportunity_id: uuid.UUID, item_id: uuid.UUID) -> BidChecklistItem:
    item = db.get(BidChecklistItem, item_id)
    if item is None or item.opportunity_id != opportunity_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Checklist item not found")
    return item


@router.patch("/opportunities/{opportunity_id}/checklist/{item_id}", response_model=ChecklistItemRead)
def update_checklist_item(
    opportunity_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ChecklistItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*NOTE_ROLES)),
):
    item = _get_item_or_404(db, opportunity_id, item_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("owner_id") is not None:
        owner = db.get(User, changes["owner_id"])
        if owner is None or not owner.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unknown or inactive user")
    item = bid_preparation_service.update_item(db, item, changes, user)
    return ChecklistItemRead.model_validate(item).model_copy(update={"owner": _brief(item.owner)})


@router.delete("/opportunities/{opportunity_id}/checklist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checklist_item(
    opportunity_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*NOTE_ROLES)),
):
    item = _get_item_or_404(db, opportunity_id, item_id)
    if not item.is_manual:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Items from the tender can't be deleted — set their status to 'not applicable' instead",
        )
    db.delete(item)
    db.commit()
    audit_service.record(
        db, action="bid.checklist_item_deleted", user_id=user.id, entity_type="opportunity",
        entity_id=str(opportunity_id), details={"title": item.title},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------- downloads


def _attachment(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _audit_download(db: Session, user: User, opportunity: Opportunity, what: str) -> None:
    audit_service.record(
        db, action="bid.downloaded", user_id=user.id, entity_type="opportunity",
        entity_id=str(opportunity.id), details={"file": what},
    )


@router.get("/opportunities/{opportunity_id}/bid-pack/draft.docx")
def download_draft(
    opportunity_id: uuid.UUID,
    version: int | None = Query(default=None, description="Defaults to the latest version"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    opportunity = get_opportunity_or_404(db, opportunity_id)
    drafts = opportunity.bid_drafts
    draft = next((d for d in drafts if d.version == version), None) if version else (drafts[0] if drafts else None)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No draft bid has been generated yet")
    _audit_download(db, user, opportunity, f"draft v{draft.version}")
    name = f"{bid_preparation_service.base_filename(opportunity)}-draft-bid-v{draft.version}.docx"
    return _attachment(bid_preparation_service.draft_document(draft), DOCX, name)


@router.get("/opportunities/{opportunity_id}/bid-pack/checklist.xlsx")
def download_checklist(opportunity_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    opportunity = get_opportunity_or_404(db, opportunity_id)
    _audit_download(db, user, opportunity, "checklist")
    name = f"{bid_preparation_service.base_filename(opportunity)}-checklist.xlsx"
    return _attachment(bid_preparation_service.checklist_document(opportunity), XLSX, name)


@router.get("/opportunities/{opportunity_id}/bid-pack.zip")
def download_bid_pack(opportunity_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    opportunity = get_opportunity_or_404(db, opportunity_id)
    _audit_download(db, user, opportunity, "bid pack")
    name = f"{bid_preparation_service.base_filename(opportunity)}-bid-pack.zip"
    return _attachment(bid_preparation_service.bid_pack(opportunity), "application/zip", name)
