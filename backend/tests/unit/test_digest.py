"""
Daily digest (Sprint 6 exit criterion: "a test digest email renders
correctly"): content selection, ordering, escaping, and the scheduled
task that sends it.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.enums import EligibilityStatus, OpportunityStatus, TenderStatus
from app.models.qualification_result import QualificationResult
from app.models.role import Role
from app.models.tender import Tender
from app.models.user import User
from app.notifications import digest
from app.services import opportunity_service
from app.workers import tasks

NOW = datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)


def _user(db, role="sales", name="Asha Rao"):
    user = User(
        email=f"{uuid.uuid4().hex[:6]}@stackerbee.com",
        hashed_password="not-used",
        full_name=name,
        role_id=db.query(Role).filter_by(name=role).one().id,
    )
    db.add(user)
    db.commit()
    return user


def _tender(db, source, title, created_hours_ago, closing_days, score=None):
    tender = Tender(
        source_id=source.id,
        fingerprint_hash=uuid.uuid4().hex,
        title=title,
        status=TenderStatus.OPEN,
        closing_date=NOW + timedelta(days=closing_days),
        created_at=NOW - timedelta(hours=created_hours_ago),
    )
    db.add(tender)
    db.flush()
    if score is not None:
        db.add(
            QualificationResult(
                tender_id=tender.id,
                eligibility_status=EligibilityStatus.UNCERTAIN,
                relevance_score=score,
                relevance_factors={},
                reasons=[],
                risks=[],
                engine_version="1.0",
                computed_at=NOW,
            )
        )
    db.commit()
    return tender


def test_digest_lists_new_tenders_by_relevance_and_my_opportunities(db_session, sample_source):
    me, colleague = _user(db_session), _user(db_session, "bd_manager", "Vikram")
    _tender(db_session, sample_source, "Low fit tender", 2, 20, score=30)
    _tender(db_session, sample_source, "High fit <portal> & app", 5, 20, score=88)
    _tender(db_session, sample_source, "Not yet scored", 1, 20)
    _tender(db_session, sample_source, "Old tender", 30, 20, score=99)  # older than 24h
    mine = _tender(db_session, sample_source, "My bid", 100, 3)
    opportunity = opportunity_service.create_opportunity(db_session, mine, user=me)
    opportunity_service.transition(db_session, opportunity, OpportunityStatus.SCREENING, colleague)
    for entry in opportunity.status_history:
        entry.changed_at = NOW - timedelta(hours=1)
    db_session.commit()

    content = digest.build_digest(db_session, me, NOW)

    assert [t.title for t in content.new_tenders] == ["High fit <portal> & app", "Low fit tender", "Not yet scored"]
    assert [(o.title, o.status, o.closing_soon) for o in content.my_opportunities] == [("My bid", "Screening", True)]
    assert [(c.to_status, c.by) for c in content.changes] == [("Screening", "Vikram")]

    subject, text, html = digest.render_digest(content, "Asha Rao", "https://tenders.example.com")
    assert subject == "Tender digest 22 Oct 2026: 3 new tender(s), 1 of your opportunities closing within 7 days"
    assert "relevance 88/100, Uncertain" in text
    assert "not scored yet" in text
    assert "[CLOSING SOON] My bid — Screening" in text
    assert f"https://tenders.example.com/opportunities/{opportunity.id}" in text
    assert "High fit &lt;portal&gt; &amp; app" in html  # escaped, not injected
    assert "<portal>" not in html
    assert html.index("High fit") < html.index("Low fit")
    assert "rule-based assessments" in html


def test_status_changes_i_made_myself_are_not_repeated_to_me(db_session, sample_source):
    me = _user(db_session)
    tender = _tender(db_session, sample_source, "Mine", 100, 20)
    opportunity = opportunity_service.create_opportunity(db_session, tender, user=me)
    opportunity_service.transition(db_session, opportunity, OpportunityStatus.SCREENING, me)
    for entry in opportunity.status_history:
        entry.changed_at = NOW - timedelta(hours=1)
    db_session.commit()

    assert digest.build_digest(db_session, me, NOW).changes == []


def test_empty_digest(db_session):
    content = digest.build_digest(db_session, _user(db_session), NOW)
    assert content.is_empty
    _, text, html = digest.render_digest(content, "Asha", "http://x")
    assert "NEW TENDERS (last 24 hours, most relevant first): 0" in text
    assert "No new tenders in the last 24 hours." in html


@pytest.fixture()
def session_factory(db_engine, db_session):
    return sessionmaker(bind=db_engine, autocommit=False, autoflush=False, future=True)


def test_daily_task_sends_only_non_empty_digests(db_session, sample_source, session_factory, outbox, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "notifications_email_enabled", True)
    monkeypatch.setattr(settings, "digest_enabled", True)
    _user(db_session, name="Has news")
    _tender(db_session, sample_source, "Fresh tender", 2, 10, score=70)

    result = tasks.send_daily_digests(session_factory=session_factory, now=NOW)

    assert result == {"status": "done", "sent": 1, "empty": 0}
    assert len(outbox.sent) == 1
    assert outbox.sent[0].html and "Fresh tender" in outbox.sent[0].html


def test_daily_task_does_nothing_while_email_is_off(session_factory, outbox, monkeypatch):
    monkeypatch.setattr(get_settings(), "notifications_email_enabled", False)
    assert tasks.send_daily_digests(session_factory=session_factory, now=NOW)["status"] == "skipped"
    assert outbox.sent == []


def test_digest_is_on_the_beat_schedule():
    from app.workers.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["daily-digest"]
    assert entry["task"] == "app.workers.tasks.send_daily_digest"
