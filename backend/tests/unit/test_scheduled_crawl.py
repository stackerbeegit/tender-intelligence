from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from app.connectors.base.base_connector import BaseConnector
from app.connectors.base.types import DiscoveredTenderRef, NormalisedTender
from app.models.enums import SourceStatus, SourceType
from app.models.source import Source
from app.models.tender import Tender
from app.workers import tasks
from app.workers.celery_app import celery_app


class _OneTenderConnector(BaseConnector):
    def discover(self):
        return [DiscoveredTenderRef(source_tender_id=f"{self.source.name}-1")]

    def fetch_tender(self, ref):
        return {"id": ref.source_tender_id}

    def fetch_documents(self, ref, raw_tender):
        return []

    def parse(self, raw_tender, raw_documents):
        return raw_tender

    def normalise(self, parsed):
        return NormalisedTender(
            source_tender_id=parsed["id"],
            title=f"Tender {parsed['id']}",
            tender_value=Decimal("1.00"),
            published_date=datetime(2026, 1, 1).date(),
        )


class _BrokenConnector(_OneTenderConnector):
    def __init__(self, source):
        raise RuntimeError("connector misconfigured")


@pytest.fixture()
def fake_registry(monkeypatch):
    fake = {SourceType.STATE: _OneTenderConnector, SourceType.PSU: _BrokenConnector}
    monkeypatch.setattr(tasks, "get_connector_class", fake.get)


def _source(db, name, source_type, enabled):
    db.add(
        Source(
            name=name,
            source_type=source_type,
            status=SourceStatus.HEALTHY,
            crawler_enabled=enabled,
            terms_access_notes="test",
        )
    )
    db.commit()


def test_beat_runs_the_crawl_daily_at_1am_ist():
    entry = celery_app.conf.beat_schedule["daily-crawl-all-sources"]
    assert entry["task"] == "app.workers.tasks.crawl_all_sources"
    assert entry["schedule"].hour == {1}
    assert entry["schedule"].minute == {0}
    assert celery_app.conf.timezone == "Asia/Kolkata"


def test_run_all_crawls_covers_enabled_sources_and_isolates_failures(db_engine, db_session, fake_registry):
    _source(db_session, "State Portal", SourceType.STATE, enabled=True)
    _source(db_session, "Disabled Portal", SourceType.STATE, enabled=False)
    _source(db_session, "Broken PSU", SourceType.PSU, enabled=True)
    _source(db_session, "No Connector", SourceType.DEPARTMENT, enabled=True)

    results = tasks.run_all_crawls(sessionmaker(bind=db_engine, future=True))

    by_source = {r["source"]: r for r in results}
    assert set(by_source) == {"State Portal", "Broken PSU", "No Connector"}
    assert by_source["State Portal"]["status"] == "success"
    assert by_source["State Portal"]["new"] == 1
    assert by_source["Broken PSU"]["status"] == "error"
    assert by_source["No Connector"]["status"] == "skipped"
    db_session.expire_all()
    assert db_session.query(Tender).filter_by(source_tender_id="State Portal-1").count() == 1


def test_overlapping_run_is_skipped(monkeypatch):
    class _HeldLock:
        def acquire(self):
            return False

    class _FakeRedis:
        def lock(self, *args, **kwargs):
            return _HeldLock()

    monkeypatch.setattr(tasks, "_redis", lambda: _FakeRedis())
    monkeypatch.setattr(tasks, "run_all_crawls", lambda: pytest.fail("must not crawl while locked"))

    assert tasks.crawl_all_sources() == {"status": "skipped", "reason": "previous run still in progress"}
