"""
Regression test for a Postgres-only bug: plain `json` columns have no
equality operator, which breaks `SELECT DISTINCT` once a json column is
in the selected row — exactly what tender search hit once `raw_metadata`
was added. SQLite's permissive typing let this slip through the
SQLite-backed unit/API test suite entirely; it only showed up against a
real Postgres database. Fixed by switching those columns to `jsonb`
(app/models/base.py `sa_json()`), and this test exists so the fix can't
silently regress back to plain `json`.

Skipped unless DATABASE_URL points at a real Postgres — this is not part
of the fast default test run.
"""
import uuid
from decimal import Decimal

import pytest
import sqlalchemy.exc
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.connectors.base.types import NormalisedTender
from app.core.config import get_settings
from app.models.enums import SourceStatus, SourceType
from app.models.source import Source
from app.repositories.tender_repository import TenderFilter, TenderRepository
from app.services import tender_ingestion_service

settings = get_settings()

if "postgresql" not in settings.database_url:
    pytest.skip("Requires a real Postgres DATABASE_URL — not part of the default sqlite test run", allow_module_level=True)

try:
    _probe_engine = create_engine(settings.database_url, future=True)
    with _probe_engine.connect() as _probe_conn:
        _probe_conn.execute(text("SELECT 1"))
    _probe_engine.dispose()
except sqlalchemy.exc.OperationalError:
    pytest.skip(
        "DATABASE_URL names Postgres but no server is reachable — skipping rather than erroring "
        "(e.g. a fresh clone or CI without a live Postgres instance)",
        allow_module_level=True,
    )


@pytest.fixture()
def pg_session():
    """
    `tender_ingestion_service.ingest_tender()` calls `db.commit()`
    internally — a plain connection.begin()/rollback() wrapper would let
    those commits through to the real transaction, permanently writing
    test data into this dev database. `join_transaction_mode="create_savepoint"`
    makes every internal commit only end a SAVEPOINT (auto-restarting a new
    one), so the single outer transaction we roll back here is the only
    thing that actually touches the database.
    """
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


def test_keyword_search_does_not_error_on_distinct_with_json_columns(pg_session):
    source = Source(
        name=f"PG Integration Test Source {uuid.uuid4().hex[:8]}",
        source_type=SourceType.OTHER,
        status=SourceStatus.DISABLED,
    )
    pg_session.add(source)
    pg_session.flush()

    tender_ingestion_service.ingest_tender(
        pg_session,
        source.id,
        NormalisedTender(
            source_tender_id="PG-IT-001",
            title="Integration test keyword distinctness",
            tender_value=Decimal("12345.00"),
        ),
    )

    items, total = TenderRepository(pg_session).search(TenderFilter(keyword="distinctness"))

    assert total == 1
    assert items[0].title == "Integration test keyword distinctness"


def test_relevance_sort_with_category_filter_runs_on_postgres(pg_session):
    """Sprint 6: ordering by the relevance subquery. Postgres rejects that
    combined with SELECT DISTINCT, which is why the category filter is an
    EXISTS rather than a join — this pins that down on the real database."""
    from datetime import datetime, timezone

    from app.models.enums import EligibilityStatus
    from app.models.enums import TenderCategory as TenderCategoryEnum
    from app.models.qualification_result import QualificationResult
    from app.models.tender import Tender
    from app.models.tender_category import TenderCategory

    source = Source(name=f"PG Sort Source {uuid.uuid4().hex[:8]}", source_type=SourceType.OTHER, status=SourceStatus.DISABLED)
    pg_session.add(source)
    pg_session.flush()
    marker = uuid.uuid4().hex[:8]
    for title, score in (("low", 10), ("high", 95), ("none", None)):
        tender = Tender(source_id=source.id, fingerprint_hash=uuid.uuid4().hex, title=f"pgsort-{marker}-{title}")
        pg_session.add(tender)
        pg_session.flush()
        # Two categories, so a join would have returned each tender twice.
        pg_session.add_all(
            [
                TenderCategory(tender_id=tender.id, category=TenderCategoryEnum.SOFTWARE_DEVELOPMENT),
                TenderCategory(tender_id=tender.id, category=TenderCategoryEnum.CLOUD_DEVOPS, confidence=0.9),
            ]
        )
        if score is not None:
            pg_session.add(
                QualificationResult(
                    tender_id=tender.id, eligibility_status=EligibilityStatus.UNCERTAIN, relevance_score=score,
                    relevance_factors={}, reasons=[], risks=[], engine_version="1.0",
                    computed_at=datetime.now(timezone.utc),
                )
            )
    pg_session.flush()

    items, total = TenderRepository(pg_session).search(
        TenderFilter(keyword=f"pgsort-{marker}", category=TenderCategoryEnum.SOFTWARE_DEVELOPMENT, sort="relevance")
    )

    assert total == 3
    assert [t.title.rsplit("-", 1)[1] for t in items] == ["high", "low", "none"]
