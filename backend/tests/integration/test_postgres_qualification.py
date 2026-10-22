"""
Qualification against a real Postgres: jsonb round-trips of the stored
reasons/factors/risks, Numeric → float conversion of profile amounts, and
the staleness check, which compares timezone-aware datetimes on Postgres
(SQLite hands back naive ones, so the default suite can't cover it).

Everything runs inside one rolled-back transaction, so nothing is left in
the database — including when the database already has a company profile.
Skipped unless DATABASE_URL points at a reachable Postgres.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import sqlalchemy.exc
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.matching.relevance import relevance_score
from app.models.enums import (
    DocumentType,
    EligibilityCriterionType,
    EligibilityStatus,
    ExtractionStatus,
    SourceStatus,
    SourceType,
    TenderStatus,
)
from app.models.role import Role
from app.models.source import Source
from app.models.tender import Tender
from app.models.tender_document import TenderDocument
from app.models.tender_eligibility import TenderEligibility
from app.models.user import User
from app.schemas.profile import ProfileUpsert
from app.services import profile_service, qualification_service

settings = get_settings()

if "postgresql" not in settings.database_url:
    pytest.skip("Requires a real Postgres DATABASE_URL — not part of the default sqlite test run", allow_module_level=True)

try:
    _probe_engine = create_engine(settings.database_url, future=True)
    with _probe_engine.connect() as _probe_conn:
        _probe_conn.execute(text("SELECT 1"))
    _probe_engine.dispose()
except sqlalchemy.exc.OperationalError:
    pytest.skip("DATABASE_URL names Postgres but no server is reachable", allow_module_level=True)


@pytest.fixture()
def pg_session():
    """Services commit internally; savepoint mode keeps those commits
    inside the outer transaction that is rolled back at the end."""
    engine = create_engine(settings.database_url, future=True)
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
        engine.dispose()


def test_qualification_round_trips_and_detects_staleness(pg_session):
    admin_role = pg_session.query(Role).filter_by(name="admin").one()
    user = User(
        email=f"pg-qual-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        full_name="PG Test",
        role_id=admin_role.id,
    )
    source = Source(name=f"PG Qual Source {uuid.uuid4().hex[:8]}", source_type=SourceType.OTHER,
                    status=SourceStatus.DISABLED)
    pg_session.add_all([user, source])
    pg_session.flush()

    tender = Tender(
        source_id=source.id,
        fingerprint_hash=f"pg-qual-{uuid.uuid4()}",
        title="PG qualification integration",
        status=TenderStatus.OPEN,
        tender_value=Decimal("50000000.00"),
        closing_date=datetime.now(timezone.utc) + timedelta(days=20),
    )
    pg_session.add(tender)
    pg_session.flush()
    document = TenderDocument(tender_id=tender.id, file_name="RFP.pdf", document_type=DocumentType.RFP,
                              extraction_status=ExtractionStatus.DONE)
    pg_session.add(document)
    pg_session.flush()
    pg_session.add(
        TenderEligibility(
            tender_id=tender.id,
            document_id=document.id,
            criterion_type=EligibilityCriterionType.NET_WORTH,
            summary="Net worth ₹2 Cr",
            criterion_text="The bidder shall have a net worth of at least Rs. 2 Crore.",
            extracted_value={"amount_inr": 20000000},
            page_number=4,
            generated_by_model="test-model",
        )
    )
    pg_session.commit()

    profile_service.upsert_profile(
        pg_session, ProfileUpsert(company_name="PG Test Co", net_worth_inr=Decimal("30000000.50")), user
    )
    pg_session.refresh(tender)
    result = qualification_service.compute(pg_session, tender)

    pg_session.expire_all()
    stored = pg_session.get(Tender, tender.id).qualification
    assert stored.eligibility_status is EligibilityStatus.ELIGIBLE
    assert stored.reasons[0]["evidence"]["page_number"] == 4
    assert "₹3 Cr" in stored.reasons[0]["text"]
    assert stored.relevance_score == relevance_score(stored.relevance_factors)
    assert stored.computed_at.tzinfo is not None
    assert result.id == stored.id

    profile = profile_service.get_profile(pg_session)
    assert qualification_service.is_stale(stored.tender, stored, profile) is False

    profile_service.upsert_profile(
        pg_session, ProfileUpsert(company_name="PG Test Co", net_worth_inr=Decimal("1000000")), user
    )
    pg_session.expire_all()
    stored = pg_session.get(Tender, tender.id).qualification
    assert qualification_service.is_stale(stored.tender, stored, profile_service.get_profile(pg_session)) is True

    qualification_service.compute(pg_session, stored.tender)
    pg_session.expire_all()
    assert pg_session.get(Tender, tender.id).qualification.eligibility_status is EligibilityStatus.NOT_ELIGIBLE
