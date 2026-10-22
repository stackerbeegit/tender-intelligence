import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.enums import OpportunityStatus
from app.models.opportunity import Opportunity
from app.models.opportunity_assignment import OpportunityAssignment
from app.models.tender import Tender
from app.models.user import User
from app.repositories.tender_repository import TenderRepository
from app.schemas.opportunity import (
    AssignmentCreate,
    AssignmentRead,
    NoteCreate,
    NoteRead,
    OpportunityCreate,
    OpportunityDetail,
    OpportunityListItem,
    OpportunityListResponse,
    OwnerUpdate,
    StatusHistoryRead,
    TenderBrief,
    TenderOpportunityRef,
    TransitionRequest,
    UserBrief,
)
from app.services import opportunity_service
from app.services.opportunity_service import (
    CRM_ROLES,
    DECISION_ROLES,
    NOTE_ROLES,
    CommentRequiredError,
    InvalidTransitionError,
    OpportunityExistsError,
    TransitionNotPermittedError,
)

router = APIRouter(tags=["opportunities"])


def _brief(user: User | None) -> UserBrief | None:
    return UserBrief.model_validate(user) if user else None


def _list_item(o: Opportunity) -> OpportunityListItem:
    tender = o.tender
    q = tender.qualification
    seen: set = set()
    assignees = []
    for a in o.assignments:
        if a.user_id not in seen:
            seen.add(a.user_id)
            assignees.append(_brief(a.user))
    return OpportunityListItem(
        id=o.id,
        status=o.status,
        created_from=o.created_from,
        tender=TenderBrief(
            id=tender.id,
            title=tender.title,
            tender_number=tender.tender_number,
            organisation=tender.organisation.name if tender.organisation else None,
            closing_date=tender.closing_date,
        ),
        owner=_brief(o.owner),
        assignees=assignees,
        relevance_score=q.relevance_score if q else None,
        eligibility_status=q.eligibility_status if q else None,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


def _detail(o: Opportunity, user: User) -> OpportunityDetail:
    return OpportunityDetail(
        **_list_item(o).model_dump(),
        assignments=[
            AssignmentRead(id=a.id, user=_brief(a.user), team=a.team, assigned_at=a.created_at) for a in o.assignments
        ],
        notes=[NoteRead(id=n.id, author=_brief(n.author), note_text=n.note_text, created_at=n.created_at) for n in o.notes],
        history=[
            StatusHistoryRead(
                id=h.id,
                from_status=h.from_status,
                to_status=h.to_status,
                changed_by=_brief(h.changed_by),
                changed_at=h.changed_at,
                comment=h.comment,
            )
            for h in o.status_history
        ],
        allowed_transitions=opportunity_service.allowed_transitions(o, user),
        can_edit=user.role.name in CRM_ROLES,
        can_decide=user.role.name in DECISION_ROLES,
    )


def get_opportunity_or_404(db: Session, opportunity_id: uuid.UUID) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity


def _get_user_or_400(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unknown or inactive user")
    return user


@router.get("/opportunities", response_model=OpportunityListResponse)
def list_opportunities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status_filter: OpportunityStatus | None = Query(default=None, alias="status"),
    mine: bool = Query(default=False, description="Only opportunities I own or am assigned to"),
    open_only: bool = Query(default=False, description="Hide won / lost / no-bid"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    stmt = select(Opportunity)
    if status_filter:
        stmt = stmt.where(Opportunity.status == status_filter)
    if open_only:
        stmt = stmt.where(Opportunity.status.not_in(list(opportunity_service.FINAL_STATUSES)))
    if mine:
        assigned = select(OpportunityAssignment.opportunity_id).where(OpportunityAssignment.user_id == user.id)
        stmt = stmt.where(or_(Opportunity.owner_id == user.id, Opportunity.id.in_(assigned)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = (
        stmt.join(Tender, Tender.id == Opportunity.tender_id)
        .order_by(Tender.closing_date.asc().nulls_last(), Opportunity.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(
            selectinload(Opportunity.tender).selectinload(Tender.organisation),
            selectinload(Opportunity.tender).selectinload(Tender.qualification),
            selectinload(Opportunity.assignments).selectinload(OpportunityAssignment.user),
            selectinload(Opportunity.owner),
        )
    )
    items = [_list_item(o) for o in db.scalars(stmt)]
    return OpportunityListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/opportunities", response_model=OpportunityDetail, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*CRM_ROLES))
):
    tender = TenderRepository(db).get_by_id(payload.tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    try:
        opportunity = opportunity_service.create_opportunity(db, tender, user=user, comment=payload.comment)
    except OpportunityExistsError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"message": str(exc), "opportunity_id": str(exc.opportunity.id)}
        )
    return _detail(opportunity, user)


@router.get("/tenders/{tender_id}/opportunity", response_model=TenderOpportunityRef)
def get_tender_opportunity(tender_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    return TenderOpportunityRef(opportunity=_list_item(tender.opportunity) if tender.opportunity else None)


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _detail(get_opportunity_or_404(db, opportunity_id), user)


@router.post("/opportunities/{opportunity_id}/transitions", response_model=OpportunityDetail)
def change_status(
    opportunity_id: uuid.UUID,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CRM_ROLES)),
):
    opportunity = get_opportunity_or_404(db, opportunity_id)
    try:
        opportunity_service.transition(db, opportunity, payload.to_status, user, payload.comment, payload.override)
    except TransitionNotPermittedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))
    except (InvalidTransitionError, CommentRequiredError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.refresh(opportunity)
    return _detail(opportunity, user)


@router.patch("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def update_owner(
    opportunity_id: uuid.UUID,
    payload: OwnerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CRM_ROLES)),
):
    opportunity = get_opportunity_or_404(db, opportunity_id)
    owner = _get_user_or_400(db, payload.owner_id) if payload.owner_id else None
    opportunity_service.set_owner(db, opportunity, owner, user)
    db.refresh(opportunity)
    return _detail(opportunity, user)


@router.post(
    "/opportunities/{opportunity_id}/assignments", response_model=OpportunityDetail, status_code=status.HTTP_201_CREATED
)
def add_assignment(
    opportunity_id: uuid.UUID,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CRM_ROLES)),
):
    opportunity = get_opportunity_or_404(db, opportunity_id)
    opportunity_service.assign(db, opportunity, _get_user_or_400(db, payload.user_id), payload.team, by=user)
    db.refresh(opportunity)
    return _detail(opportunity, user)


@router.delete("/opportunities/{opportunity_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assignment(
    opportunity_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CRM_ROLES)),
):
    assignment = db.get(OpportunityAssignment, assignment_id)
    if assignment is None or assignment.opportunity_id != opportunity_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    opportunity_service.unassign(db, assignment, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/opportunities/{opportunity_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def add_note(
    opportunity_id: uuid.UUID,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*NOTE_ROLES)),
):
    note = opportunity_service.add_note(db, get_opportunity_or_404(db, opportunity_id), user, payload.note_text)
    return NoteRead(id=note.id, author=_brief(user), note_text=note.note_text, created_at=note.created_at)
