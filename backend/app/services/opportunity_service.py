"""
Opportunity CRM (docs/architecture.md §10): creation (by a person, or
automatically when a tender's relevance is high enough), the status
workflow, assignments, owner and notes.

Workflow rules live here and nowhere else:
- `TRANSITIONS` is the only way a status can move; every move writes an
  append-only `opportunity_status_history` row in the same commit.
- Leaving `BID_NO_BID` is the human bid / no-bid decision (§9) and is
  limited to `DECISION_ROLES`.
- Moving to NO_BID or LOST needs a reason.
- An admin may override the graph, with a mandatory comment; the history
  row records that it was an override.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.core.logging import get_logger
from app.models.enums import EligibilityStatus, OpportunityOrigin, OpportunityStatus, OpportunityTeam
from app.models.opportunity import Opportunity
from app.models.opportunity_assignment import OpportunityAssignment
from app.models.opportunity_note import OpportunityNote
from app.models.opportunity_status_history import OpportunityStatusHistory
from app.models.qualification_result import QualificationResult
from app.models.role import Role
from app.models.tender import Tender
from app.models.user import User
from app.services import audit_service, notification_service

logger = get_logger(__name__)

S = OpportunityStatus
TRANSITIONS: dict[OpportunityStatus, tuple[OpportunityStatus, ...]] = {
    S.NEW: (S.SCREENING, S.NO_BID),
    S.SCREENING: (S.QUALIFIED, S.NO_BID),
    S.QUALIFIED: (S.MANAGEMENT_REVIEW, S.NO_BID),
    S.MANAGEMENT_REVIEW: (S.BID_NO_BID, S.QUALIFIED, S.NO_BID),
    S.BID_NO_BID: (S.PROPOSAL_IN_PROGRESS, S.NO_BID),
    S.PROPOSAL_IN_PROGRESS: (S.SUBMITTED, S.NO_BID),
    S.SUBMITTED: (S.TECHNICAL_EVALUATION, S.LOST),
    S.TECHNICAL_EVALUATION: (S.COMMERCIAL_EVALUATION, S.LOST),
    S.COMMERCIAL_EVALUATION: (S.WON, S.LOST),
    S.WON: (),
    S.LOST: (),
    S.NO_BID: (),
}
FINAL_STATUSES = {S.WON, S.LOST, S.NO_BID}
COMMENT_REQUIRED = {S.NO_BID, S.LOST}

CRM_ROLES = ("admin", "bd_manager", "sales")  # create, move, assign, prepare bids
NOTE_ROLES = ("admin", "bd_manager", "sales", "technical")
DECISION_ROLES = ("admin", "bd_manager")  # the bid / no-bid decision

ROLE_TEAM = {
    "sales": OpportunityTeam.SALES,
    "bd_manager": OpportunityTeam.BD,
    "admin": OpportunityTeam.MANAGEMENT,
    "technical": OpportunityTeam.TECHNICAL,
}


class OpportunityExistsError(DomainError):
    def __init__(self, opportunity: Opportunity):
        super().__init__("This tender is already an opportunity")
        self.opportunity = opportunity


class InvalidTransitionError(DomainError):
    pass


class TransitionNotPermittedError(DomainError):
    pass


class CommentRequiredError(DomainError):
    pass


def label(status: OpportunityStatus) -> str:
    return status.value.replace("_", " ").capitalize().replace("Bid no bid", "Bid / no-bid decision")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _link(opportunity: Opportunity) -> str:
    return notification_service.app_link(f"/opportunities/{opportunity.id}")


def _participants(opportunity: Opportunity) -> list[User]:
    return [opportunity.owner, *(a.user for a in opportunity.assignments)]


# ------------------------------------------------------------- creation


def create_opportunity(
    db: Session,
    tender: Tender,
    *,
    user: User | None,
    origin: OpportunityOrigin = OpportunityOrigin.MANUAL,
    comment: str | None = None,
) -> Opportunity:
    if tender.opportunity is not None:
        raise OpportunityExistsError(tender.opportunity)
    opportunity = Opportunity(
        tender_id=tender.id,
        status=S.NEW,
        created_from=origin,
        created_by_id=user.id if user else None,
        owner_id=user.id if user else None,
        title=tender.title[:1000],
    )
    opportunity.status_history.append(
        OpportunityStatusHistory(
            from_status=None, to_status=S.NEW, changed_by_id=user.id if user else None, changed_at=_now(), comment=comment
        )
    )
    tender.opportunity = opportunity
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)
    audit_service.record(
        db,
        action="opportunity.created",
        user_id=user.id if user else None,
        entity_type="opportunity",
        entity_id=str(opportunity.id),
        details={"tender_id": str(tender.id), "origin": origin.value, "comment": comment},
    )
    return opportunity


def ensure_opportunity(db: Session, tender: Tender, user: User, comment: str) -> tuple[Opportunity, bool]:
    if tender.opportunity is not None:
        return tender.opportunity, False
    return create_opportunity(db, tender, user=user, comment=comment), True


def auto_promote(db: Session, tender: Tender, result: QualificationResult, min_score: int) -> Opportunity | None:
    """Called after every qualification run. Promotes an open tender with a
    high enough relevance that isn't NOT_ELIGIBLE; never touches a tender
    that already has an opportunity."""
    if min_score <= 0 or tender.opportunity is not None:
        return None
    if result.relevance_score < min_score or result.eligibility_status is EligibilityStatus.NOT_ELIGIBLE:
        return None
    closing = tender.closing_date
    if closing is not None:
        closing = closing if closing.tzinfo else closing.replace(tzinfo=timezone.utc)
        if closing <= _now():
            return None

    comment = (
        f"Auto-promoted: relevance {result.relevance_score}/100 (threshold {min_score}), "
        f"eligibility {result.eligibility_status.value}."
    )
    opportunity = create_opportunity(db, tender, user=None, origin=OpportunityOrigin.AUTO_RELEVANCE, comment=comment)
    bd_managers = db.query(User).join(Role).filter(Role.name == "bd_manager", User.is_active.is_(True)).all()
    notification_service.notify(
        db,
        bd_managers,
        event_type="opportunity.auto_promoted",
        subject=f"New opportunity: {opportunity.title[:120]}",
        text=f"{comment}\n\nReview it: {_link(opportunity)}",
        entity_type="opportunity",
        entity_id=str(opportunity.id),
    )
    logger.info("Auto-promoted tender=%s to opportunity=%s", tender.id, opportunity.id)
    return opportunity


# ------------------------------------------------------------- workflow


def allowed_transitions(opportunity: Opportunity, user: User) -> list[OpportunityStatus]:
    role = user.role.name
    if role not in CRM_ROLES:
        return []
    targets = list(TRANSITIONS[opportunity.status])
    if opportunity.status is S.BID_NO_BID and role not in DECISION_ROLES:
        return []
    return targets


def transition(
    db: Session,
    opportunity: Opportunity,
    to_status: OpportunityStatus,
    user: User,
    comment: str | None = None,
    override: bool = False,
) -> OpportunityStatusHistory:
    comment = (comment or "").strip() or None
    from_status = opportunity.status
    if to_status is from_status:
        raise InvalidTransitionError(f"The opportunity is already '{label(to_status)}'")

    if override:
        if user.role.name != "admin":
            raise TransitionNotPermittedError("Only an admin can override the workflow")
        if not comment:
            raise CommentRequiredError("An override needs a comment explaining why")
    else:
        if to_status not in TRANSITIONS[from_status]:
            allowed = ", ".join(label(s) for s in TRANSITIONS[from_status]) or "none — this status is final"
            raise InvalidTransitionError(
                f"Cannot move from '{label(from_status)}' to '{label(to_status)}' (allowed: {allowed})"
            )
        if user.role.name not in CRM_ROLES:
            raise TransitionNotPermittedError(f"Role '{user.role.name}' cannot change opportunity status")
        if from_status is S.BID_NO_BID and user.role.name not in DECISION_ROLES:
            raise TransitionNotPermittedError("The bid / no-bid decision is made by a BD manager or admin")
    if to_status in COMMENT_REQUIRED and not comment:
        raise CommentRequiredError(f"Moving to '{label(to_status)}' needs a reason in the comment")

    entry = OpportunityStatusHistory(
        from_status=from_status,
        to_status=to_status,
        changed_by_id=user.id,
        changed_at=_now(),
        comment=f"[override] {comment}" if override else comment,
    )
    opportunity.status = to_status
    opportunity.status_history.append(entry)
    db.commit()
    db.refresh(entry)
    audit_service.record(
        db,
        action="opportunity.status_changed",
        user_id=user.id,
        entity_type="opportunity",
        entity_id=str(opportunity.id),
        details={"from": from_status.value, "to": to_status.value, "comment": comment, "override": override},
    )
    notification_service.notify(
        db,
        _participants(opportunity),
        event_type="opportunity.status_changed",
        subject=f"{opportunity.title[:100]}: {label(to_status)}",
        text=(
            f"{user.full_name} moved this opportunity from '{label(from_status)}' to '{label(to_status)}'."
            + (f"\nComment: {comment}" if comment else "")
            + f"\n\nOpen it: {_link(opportunity)}"
        ),
        entity_type="opportunity",
        entity_id=str(opportunity.id),
        exclude=user,
    )
    return entry


# ------------------------------------------------------ people and notes


def assign(
    db: Session, opportunity: Opportunity, assignee: User, team: OpportunityTeam, by: User
) -> OpportunityAssignment:
    existing = next((a for a in opportunity.assignments if a.user_id == assignee.id and a.team is team), None)
    if existing is not None:
        return existing
    assignment = OpportunityAssignment(user_id=assignee.id, team=team, assigned_by_id=by.id)
    opportunity.assignments.append(assignment)
    db.commit()
    db.refresh(assignment)
    audit_service.record(
        db,
        action="opportunity.assigned",
        user_id=by.id,
        entity_type="opportunity",
        entity_id=str(opportunity.id),
        details={"user_id": str(assignee.id), "team": team.value},
    )
    notification_service.notify(
        db,
        [assignee],
        event_type="opportunity.assigned",
        subject=f"Assigned to you: {opportunity.title[:120]}",
        text=(
            f"{by.full_name} added you to the {team.value} team for this opportunity "
            f"(status: {label(opportunity.status)}).\n\nOpen it: {_link(opportunity)}"
        ),
        entity_type="opportunity",
        entity_id=str(opportunity.id),
        exclude=by,
    )
    return assignment


def unassign(db: Session, assignment: OpportunityAssignment, by: User) -> None:
    opportunity_id, details = assignment.opportunity_id, {"user_id": str(assignment.user_id), "team": assignment.team.value}
    db.delete(assignment)
    db.commit()
    audit_service.record(
        db, action="opportunity.unassigned", user_id=by.id, entity_type="opportunity",
        entity_id=str(opportunity_id), details=details,
    )


def set_owner(db: Session, opportunity: Opportunity, owner: User | None, by: User) -> Opportunity:
    opportunity.owner_id = owner.id if owner else None
    db.commit()
    db.refresh(opportunity)
    audit_service.record(
        db, action="opportunity.owner_changed", user_id=by.id, entity_type="opportunity",
        entity_id=str(opportunity.id), details={"owner_id": str(owner.id) if owner else None},
    )
    if owner is not None:
        notification_service.notify(
            db,
            [owner],
            event_type="opportunity.owner_changed",
            subject=f"You now own: {opportunity.title[:120]}",
            text=f"{by.full_name} made you the owner of this opportunity.\n\nOpen it: {_link(opportunity)}",
            entity_type="opportunity",
            entity_id=str(opportunity.id),
            exclude=by,
        )
    return opportunity


def add_note(db: Session, opportunity: Opportunity, author: User, text: str) -> OpportunityNote:
    note = OpportunityNote(author_id=author.id, note_text=text.strip())
    opportunity.notes.append(note)
    db.commit()
    db.refresh(note)
    return note
