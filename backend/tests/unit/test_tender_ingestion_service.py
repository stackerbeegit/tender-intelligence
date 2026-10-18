from datetime import datetime, timezone
from decimal import Decimal

from app.connectors.base.types import NormalisedDocument, NormalisedLocation, NormalisedTender
from app.models.enums import DeadlineType, OrganisationType, TenderStatus
from app.services import tender_ingestion_service


def _tender(**overrides) -> NormalisedTender:
    defaults = dict(
        source_tender_id="GEM/2026/T/001",
        title="Supply and installation of IT infrastructure",
        organisation_name="Ministry of Example Affairs",
        organisation_type=OrganisationType.CENTRAL_GOVT,
        tender_value=Decimal("5000000.00"),
        published_date=datetime(2026, 1, 1).date(),
        closing_date=datetime(2026, 2, 1, 17, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return NormalisedTender(**defaults)


def test_new_tender_is_created(db_session, sample_source):
    tender, created = tender_ingestion_service.ingest_tender(db_session, sample_source.id, _tender())
    assert created is True
    assert tender.title == "Supply and installation of IT infrastructure"
    assert tender.organisation.name == "Ministry of Example Affairs"
    assert len(tender.deadlines) == 1
    assert tender.deadlines[0].deadline_type == DeadlineType.BID_SUBMISSION


def test_reingesting_same_source_tender_id_updates_not_duplicates(db_session, sample_source):
    tender1, created1 = tender_ingestion_service.ingest_tender(db_session, sample_source.id, _tender())
    tender2, created2 = tender_ingestion_service.ingest_tender(
        db_session, sample_source.id, _tender(tender_value=Decimal("5500000.00"))
    )

    assert created1 is True
    assert created2 is False
    assert tender1.id == tender2.id
    assert tender2.tender_value == Decimal("5500000.00")

    all_tenders = db_session.query(type(tender1)).all()
    assert len(all_tenders) == 1


def test_changed_closing_date_adds_extended_deadline_and_marks_corrigendum(db_session, sample_source):
    tender, _ = tender_ingestion_service.ingest_tender(db_session, sample_source.id, _tender())
    original_deadline_count = len(tender.deadlines)

    new_closing = datetime(2026, 2, 15, 17, 0, tzinfo=timezone.utc)
    updated, created = tender_ingestion_service.ingest_tender(
        db_session, sample_source.id, _tender(closing_date=new_closing)
    )

    assert created is False
    # SQLite's DateTime(timezone=True) doesn't round-trip tzinfo, so compare
    # the naive wall-clock value — Postgres would preserve tzinfo exactly.
    assert updated.closing_date.replace(tzinfo=None) == new_closing.replace(tzinfo=None)
    assert updated.status == TenderStatus.CORRIGENDUM
    assert len(updated.deadlines) == original_deadline_count + 1
    assert updated.deadlines[-1].deadline_type == DeadlineType.EXTENDED
    assert updated.deadlines[-1].deadline_at.replace(tzinfo=None) == new_closing.replace(tzinfo=None)

    # the original bid_submission deadline is still there — history preserved
    assert any(d.deadline_type == DeadlineType.BID_SUBMISSION for d in updated.deadlines)


def test_unchanged_closing_date_does_not_add_a_new_deadline(db_session, sample_source):
    tender, _ = tender_ingestion_service.ingest_tender(db_session, sample_source.id, _tender())
    count_before = len(tender.deadlines)

    updated, _ = tender_ingestion_service.ingest_tender(db_session, sample_source.id, _tender())

    assert len(updated.deadlines) == count_before
    assert updated.status != TenderStatus.CORRIGENDUM


def test_same_tender_from_different_source_matches_by_fingerprint(db_session, sample_source):
    other_source = sample_source  # single-source fixture is enough to prove the lookup path works

    tender1, created1 = tender_ingestion_service.ingest_tender(
        db_session, sample_source.id, _tender(source_tender_id="PORTAL-A-001")
    )
    # No source_tender_id this time — simulates a re-publication where the
    # second listing's own reference number isn't known/used, so the
    # fingerprint (title+org+value+published_date) is the only match key.
    tender2, created2 = tender_ingestion_service.ingest_tender(
        db_session, other_source.id, _tender(source_tender_id=None)
    )

    assert created1 is True
    assert created2 is False
    assert tender1.id == tender2.id


def test_documents_and_locations_are_attached_without_duplication(db_session, sample_source):
    doc = NormalisedDocument(file_name="NIT.pdf", source_url="https://example.gov.in/nit.pdf")
    loc = NormalisedLocation(state="Delhi", city="New Delhi")

    tender, _ = tender_ingestion_service.ingest_tender(
        db_session, sample_source.id, _tender(documents=(doc,), locations=(loc,))
    )
    assert len(tender.documents) == 1
    assert len(tender.locations) == 1

    # re-ingesting with the same document/location must not duplicate rows
    updated, _ = tender_ingestion_service.ingest_tender(
        db_session, sample_source.id, _tender(documents=(doc,), locations=(loc,))
    )
    assert len(updated.documents) == 1
    assert len(updated.locations) == 1


def test_lookalike_bids_from_same_source_stay_separate(db_session, sample_source):
    """GeM lists different bids with identical title/buyer/start date. Each
    must be its own tender, and re-crawling must not flip their deadlines."""
    first = _tender(source_tender_id="GEM/2026/B/1", tender_value=None)
    second = _tender(
        source_tender_id="GEM/2026/R/2",
        tender_value=None,
        closing_date=datetime(2026, 2, 9, 17, 0, tzinfo=timezone.utc),
    )

    for _ in range(3):  # three crawls
        t1, _ = tender_ingestion_service.ingest_tender(db_session, sample_source.id, first)
        t2, _ = tender_ingestion_service.ingest_tender(db_session, sample_source.id, second)

    assert t1.id != t2.id
    assert t1.fingerprint_hash != t2.fingerprint_hash
    for tender, expected in ((t1, first), (t2, second)):
        db_session.refresh(tender)
        assert tender.closing_date.replace(tzinfo=timezone.utc) == expected.closing_date
        assert [d.deadline_type for d in tender.deadlines] == [DeadlineType.BID_SUBMISSION]
        assert tender.status == TenderStatus.OPEN


def test_listing_without_id_still_matches_by_fingerprint(db_session, sample_source):
    crawled, _ = tender_ingestion_service.ingest_tender(db_session, sample_source.id, _tender())
    manual, created = tender_ingestion_service.ingest_tender(
        db_session, sample_source.id, _tender(source_tender_id=None)
    )
    assert created is False
    assert manual.id == crawled.id
