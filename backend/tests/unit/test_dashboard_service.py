import uuid
from datetime import datetime, timedelta, timezone

from app.models import Tender
from app.models.enums import AnalysisStatus, TenderStatus
from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.tender_analysis import TenderAnalysis
from app.models.tender_category import TenderCategory
from app.services import dashboard_service

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def _tender(db, source, *, closes_in_days, created_days_ago=0, status=TenderStatus.OPEN, categories=()):
    tender = Tender(
        source_id=source.id,
        fingerprint_hash=f"fp-{uuid.uuid4()}",
        title="t",
        status=status,
        closing_date=None if closes_in_days is None else NOW + timedelta(days=closes_in_days),
        created_at=NOW - timedelta(days=created_days_ago),
    )
    tender.categories = [TenderCategory(category=c) for c in categories]
    db.add(tender)
    db.commit()
    return tender


def test_metrics_count_only_active_tenders(db_session, sample_source):
    soft = TenderCategoryEnum.SOFTWARE_DEVELOPMENT
    cyber = TenderCategoryEnum.CYBERSECURITY
    _tender(db_session, sample_source, closes_in_days=3, categories=[soft])  # new, expiring, relevant
    _tender(db_session, sample_source, closes_in_days=20, created_days_ago=30, categories=[soft, cyber])
    _tender(db_session, sample_source, closes_in_days=None, categories=[TenderCategoryEnum.OTHER])
    _tender(db_session, sample_source, closes_in_days=-1, categories=[soft])  # deadline passed
    _tender(db_session, sample_source, closes_in_days=5, status=TenderStatus.CANCELLED, categories=[soft])

    metrics = dashboard_service.get_metrics(db_session, now=NOW)

    assert metrics.active_tenders == 3
    assert metrics.new_tenders == 2
    assert metrics.relevant_tenders == 2  # 'other' alone isn't a focus area; multi-category counted once
    assert metrics.expiring_soon == 1
    assert dict(metrics.by_category) == {soft: 2, cyber: 1, TenderCategoryEnum.OTHER: 1}


def test_metrics_without_data_source_are_none_not_zero(db_session):
    metrics = dashboard_service.get_metrics(db_session, now=NOW)
    for name in ("highly_relevant", "under_review", "bidding", "submitted", "won", "lost"):
        assert getattr(metrics, name) is None
        assert name in metrics.pending_metrics


def test_analysed_counts_only_successful_runs(db_session, sample_source):
    for status in (AnalysisStatus.DONE, AnalysisStatus.FAILED):
        tender = _tender(db_session, sample_source, closes_in_days=10)
        db_session.add(TenderAnalysis(tender_id=tender.id, status=status, started_at=NOW))
    db_session.commit()

    assert dashboard_service.get_metrics(db_session, now=NOW).analysed_tenders == 1


def test_by_state_prefers_delivery_state_over_buyer_state(db_session, sample_source):
    from app.models.tender_location import TenderLocation
    from app.models.tender_organisation import TenderOrganisation

    gujarat_buyer = TenderOrganisation(name="Dept Gujarat", normalized_name="dept gujarat", state="Gujarat")
    db_session.add(gujarat_buyer)
    db_session.commit()

    delivered = _tender(db_session, sample_source, closes_in_days=3)
    delivered.organisation_id = gujarat_buyer.id
    delivered.locations = [TenderLocation(state="Rajasthan"), TenderLocation(state="Delhi")]
    buyer_only = _tender(db_session, sample_source, closes_in_days=3)
    buyer_only.organisation_id = gujarat_buyer.id
    expired = _tender(db_session, sample_source, closes_in_days=-2)
    expired.locations = [TenderLocation(state="Rajasthan")]
    db_session.commit()

    metrics = dashboard_service.get_metrics(db_session, now=NOW)

    assert metrics.by_state == [("Delhi", 1), ("Gujarat", 1), ("Rajasthan", 1)]


def test_closing_timeline_is_zero_filled_per_day(db_session, sample_source):
    _tender(db_session, sample_source, closes_in_days=1)
    _tender(db_session, sample_source, closes_in_days=1)
    _tender(db_session, sample_source, closes_in_days=30)

    timeline = dashboard_service.get_metrics(db_session, now=NOW).closing_timeline

    assert len(timeline) == dashboard_service.CLOSING_TIMELINE_DAYS
    assert timeline[0] == (NOW.date(), 0)
    assert timeline[1] == (NOW.date() + timedelta(days=1), 2)
    assert sum(count for _, count in timeline) == 2
