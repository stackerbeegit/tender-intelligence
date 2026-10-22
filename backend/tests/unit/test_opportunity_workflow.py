"""
Opportunity workflow rules and their audit trail (Sprint 6 exit criterion:
"status transitions are fully audited"), plus notifications and
auto-promotion by relevance.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.audit_log import AuditLog
from app.models.enums import EligibilityStatus, NotificationStatus, OpportunityOrigin, OpportunityStatus, OpportunityTeam
from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User
from app.services import opportunity_service
from app.services.opportunity_service import (
    CommentRequiredError,
    InvalidTransitionError,
    OpportunityExistsError,
    TransitionNotPermittedError,
)

S = OpportunityStatus


@pytest.fixture()
def make_user(db_session):
    def _make(role: str, name: str | None = None) -> User:
        user = User(
            email=f"{role}-{uuid.uuid4().hex[:6]}@stackerbee.com",
            hashed_password="not-used",  # these users never log in
            full_name=name or role.replace("_", " ").title(),
            role_id=db_session.query(Role).filter_by(name=role).one().id,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


def _walk(db, opportunity, user, *statuses, comment=None):
    for status in statuses:
        opportunity_service.transition(db, opportunity, status, user, comment=comment)


def test_full_happy_path_is_recorded_step_by_step(db_session, sample_tender, make_user, outbox):
    sales, bd = make_user("sales"), make_user("bd_manager")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=sales)

    _walk(db_session, opportunity, sales, S.SCREENING, S.QUALIFIED, S.MANAGEMENT_REVIEW, S.BID_NO_BID)
    _walk(db_session, opportunity, bd, S.PROPOSAL_IN_PROGRESS)
    _walk(db_session, opportunity, sales, S.SUBMITTED, S.TECHNICAL_EVALUATION, S.COMMERCIAL_EVALUATION, S.WON)

    history = opportunity.status_history
    assert [(h.from_status, h.to_status) for h in history] == [
        (None, S.NEW),
        (S.NEW, S.SCREENING),
        (S.SCREENING, S.QUALIFIED),
        (S.QUALIFIED, S.MANAGEMENT_REVIEW),
        (S.MANAGEMENT_REVIEW, S.BID_NO_BID),
        (S.BID_NO_BID, S.PROPOSAL_IN_PROGRESS),
        (S.PROPOSAL_IN_PROGRESS, S.SUBMITTED),
        (S.SUBMITTED, S.TECHNICAL_EVALUATION),
        (S.TECHNICAL_EVALUATION, S.COMMERCIAL_EVALUATION),
        (S.COMMERCIAL_EVALUATION, S.WON),
    ]
    assert history[5].changed_by_id == bd.id
    assert all(h.changed_by_id is not None for h in history)
    audited = db_session.query(AuditLog).filter_by(action="opportunity.status_changed").count()
    assert audited == len(history) - 1
    assert opportunity_service.allowed_transitions(opportunity, sales) == []  # WON is final


def test_status_cannot_skip_steps(db_session, sample_tender, make_user):
    sales = make_user("sales")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=sales)
    with pytest.raises(InvalidTransitionError, match="allowed: Screening, No bid"):
        opportunity_service.transition(db_session, opportunity, S.PROPOSAL_IN_PROGRESS, sales)
    assert opportunity.status is S.NEW
    assert len(opportunity.status_history) == 1


def test_the_bid_decision_belongs_to_bd_managers_and_admins(db_session, sample_tender, make_user):
    sales = make_user("sales")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=sales)
    _walk(db_session, opportunity, sales, S.SCREENING, S.QUALIFIED, S.MANAGEMENT_REVIEW, S.BID_NO_BID)

    assert opportunity_service.allowed_transitions(opportunity, sales) == []
    with pytest.raises(TransitionNotPermittedError, match="BD manager or admin"):
        opportunity_service.transition(db_session, opportunity, S.PROPOSAL_IN_PROGRESS, sales)
    assert opportunity_service.allowed_transitions(opportunity, make_user("admin")) == [S.PROPOSAL_IN_PROGRESS, S.NO_BID]


def test_technical_and_viewer_roles_cannot_move_status(db_session, sample_tender, make_user):
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=make_user("sales"))
    for role in ("technical", "viewer"):
        user = make_user(role)
        assert opportunity_service.allowed_transitions(opportunity, user) == []
        with pytest.raises(TransitionNotPermittedError):
            opportunity_service.transition(db_session, opportunity, S.SCREENING, user)


def test_no_bid_and_lost_need_a_reason(db_session, sample_tender, make_user):
    sales = make_user("sales")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=sales)
    with pytest.raises(CommentRequiredError):
        opportunity_service.transition(db_session, opportunity, S.NO_BID, sales, comment="   ")
    opportunity_service.transition(db_session, opportunity, S.NO_BID, sales, comment="Outside our capability")
    assert opportunity.status_history[-1].comment == "Outside our capability"


def test_admin_override_is_allowed_only_with_a_comment_and_is_marked(db_session, sample_tender, make_user):
    admin, bd = make_user("admin"), make_user("bd_manager")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=admin)

    with pytest.raises(TransitionNotPermittedError):
        opportunity_service.transition(db_session, opportunity, S.SUBMITTED, bd, comment="x", override=True)
    with pytest.raises(CommentRequiredError):
        opportunity_service.transition(db_session, opportunity, S.SUBMITTED, admin, override=True)

    opportunity_service.transition(
        db_session, opportunity, S.SUBMITTED, admin, comment="Bid was submitted offline", override=True
    )
    assert opportunity.status is S.SUBMITTED
    assert opportunity.status_history[-1].comment == "[override] Bid was submitted offline"


def test_one_opportunity_per_tender(db_session, sample_tender, make_user):
    sales = make_user("sales")
    first = opportunity_service.create_opportunity(db_session, sample_tender, user=sales)
    with pytest.raises(OpportunityExistsError) as exc:
        opportunity_service.create_opportunity(db_session, sample_tender, user=sales)
    assert exc.value.opportunity.id == first.id


def test_status_changes_notify_participants_but_not_the_actor(db_session, sample_tender, make_user, outbox):
    sales, technical, bd = make_user("sales"), make_user("technical", "Tech Lead"), make_user("bd_manager")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=sales)  # sales owns it
    opportunity_service.assign(db_session, opportunity, technical, OpportunityTeam.TECHNICAL, by=bd)
    outbox.sent.clear()

    opportunity_service.transition(db_session, opportunity, S.SCREENING, sales)

    assert sorted(m.to for m in outbox.sent) == [technical.email]
    assert "Screening" in outbox.sent[0].subject
    assert f"/opportunities/{opportunity.id}" in outbox.sent[0].text


def test_assignment_emails_the_assignee_once(db_session, sample_tender, make_user, outbox):
    bd, technical = make_user("bd_manager"), make_user("technical")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=bd)
    opportunity_service.assign(db_session, opportunity, technical, OpportunityTeam.TECHNICAL, by=bd)
    opportunity_service.assign(db_session, opportunity, technical, OpportunityTeam.TECHNICAL, by=bd)  # no duplicate

    assert len(opportunity.assignments) == 1
    assert [m.to for m in outbox.sent] == [technical.email]
    assert "technical team" in outbox.sent[0].text


def test_a_failing_mail_server_is_recorded_not_raised(db_session, sample_tender, make_user, monkeypatch):
    class Broken:
        def send(self, message):
            raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr("app.notifications.email.get_email_sender", lambda settings=None: Broken())
    bd, technical = make_user("bd_manager"), make_user("technical")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=bd)

    opportunity_service.assign(db_session, opportunity, technical, OpportunityTeam.TECHNICAL, by=bd)

    row = db_session.query(Notification).filter_by(user_id=technical.id).one()
    assert row.status is NotificationStatus.FAILED
    assert "smtp down" in row.error


def test_unconfigured_email_is_recorded_as_skipped(db_session, sample_tender, make_user, monkeypatch):
    from app.core.config import Settings
    from app.notifications import email

    original = email.get_email_sender
    monkeypatch.setattr(
        "app.notifications.email.get_email_sender",
        lambda settings=None: original(Settings(notifications_email_enabled=True, smtp_host="")),
    )
    bd, technical = make_user("bd_manager"), make_user("technical")
    opportunity = opportunity_service.create_opportunity(db_session, sample_tender, user=bd)
    opportunity_service.assign(db_session, opportunity, technical, OpportunityTeam.TECHNICAL, by=bd)

    row = db_session.query(Notification).filter_by(user_id=technical.id).one()
    assert row.status is NotificationStatus.SKIPPED
    assert row.error == "SMTP_HOST is not set"


# --------------------------------------------------------- auto-promotion


def _result(score: int, status=EligibilityStatus.UNCERTAIN):
    return SimpleNamespace(relevance_score=score, eligibility_status=status)


@pytest.mark.parametrize(
    "score, status, closing_in_days, expected",
    [
        (75, EligibilityStatus.UNCERTAIN, 10, True),
        (70, EligibilityStatus.ELIGIBLE, None, True),
        (69, EligibilityStatus.ELIGIBLE, 10, False),
        (95, EligibilityStatus.NOT_ELIGIBLE, 10, False),
        (95, EligibilityStatus.ELIGIBLE, -1, False),  # already closed
    ],
)
def test_auto_promotion_rules(db_session, sample_tender, make_user, outbox, score, status, closing_in_days, expected):
    bd = make_user("bd_manager")
    sample_tender.closing_date = (
        datetime.now(timezone.utc) + timedelta(days=closing_in_days) if closing_in_days is not None else None
    )
    db_session.commit()

    opportunity = opportunity_service.auto_promote(db_session, sample_tender, _result(score, status), min_score=70)

    assert (opportunity is not None) is expected
    if expected:
        assert opportunity.created_from is OpportunityOrigin.AUTO_RELEVANCE
        assert opportunity.status_history[0].changed_by_id is None  # the system acted
        assert f"relevance {score}/100" in opportunity.status_history[0].comment
        assert [m.to for m in outbox.sent] == [bd.email]


def test_auto_promotion_off_and_never_twice(db_session, sample_tender, make_user):
    assert opportunity_service.auto_promote(db_session, sample_tender, _result(99), min_score=0) is None
    first = opportunity_service.auto_promote(db_session, sample_tender, _result(99), min_score=70)
    assert first is not None
    assert opportunity_service.auto_promote(db_session, sample_tender, _result(99), min_score=70) is None
