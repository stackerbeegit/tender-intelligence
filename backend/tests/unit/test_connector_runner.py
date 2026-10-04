from datetime import datetime, timezone
from decimal import Decimal

from app.connectors.base.base_connector import BaseConnector
from app.connectors.base.runner import CrawlerRunner
from app.connectors.base.types import DiscoveredTenderRef, NormalisedTender
from app.models.enums import CrawlerRunStatus, SourceStatus


class _FakeConnector(BaseConnector):
    """A connector that never touches the network — proves the runner's
    retry/rate-limit/failure-isolation behaviour deterministically."""

    def __init__(self, source, refs, fail_source_tender_ids=frozenset(), flaky_source_tender_ids=frozenset()):
        super().__init__(source)
        self._refs = refs
        self._fail_ids = fail_source_tender_ids
        self._flaky_ids = set(flaky_source_tender_ids)
        self.fetch_calls: list[str] = []

    def discover(self) -> list[DiscoveredTenderRef]:
        return self._refs

    def fetch_tender(self, ref: DiscoveredTenderRef) -> dict:
        self.fetch_calls.append(ref.source_tender_id)
        if ref.source_tender_id in self._fail_ids:
            raise RuntimeError(f"simulated permanent failure for {ref.source_tender_id}")
        if ref.source_tender_id in self._flaky_ids:
            self._flaky_ids.remove(ref.source_tender_id)  # fails once, then succeeds on retry
            raise ConnectionError("simulated transient failure")
        return {"id": ref.source_tender_id}

    def fetch_documents(self, ref, raw_tender) -> list[dict]:
        return []

    def parse(self, raw_tender, raw_documents) -> dict:
        return raw_tender

    def normalise(self, parsed) -> NormalisedTender:
        return NormalisedTender(
            source_tender_id=parsed["id"],
            title=f"Tender {parsed['id']}",
            tender_value=Decimal("1000.00"),
            published_date=datetime(2026, 1, 1).date(),
        )


def _refs(*ids: str) -> list[DiscoveredTenderRef]:
    return [DiscoveredTenderRef(source_tender_id=i) for i in ids]


def test_successful_run_ingests_all_and_marks_source_healthy(db_session, sample_source):
    connector = _FakeConnector(sample_source, _refs("A", "B", "C"))
    sleeps: list[float] = []
    runner = CrawlerRunner(db_session, sample_source, connector, rate_limit_seconds=0.01, sleep_fn=sleeps.append)

    run = runner.run()

    assert run.status == CrawlerRunStatus.SUCCESS
    assert run.tenders_discovered == 3
    assert run.tenders_new == 3
    assert run.tenders_updated == 0
    assert sample_source.status == SourceStatus.HEALTHY
    assert sample_source.last_successful_crawl_at is not None
    # rate limit sleeps between items, not before the first one
    assert sleeps == [0.01, 0.01]


def test_one_bad_item_does_not_abort_the_whole_run(db_session, sample_source):
    connector = _FakeConnector(sample_source, _refs("A", "B", "C"), fail_source_tender_ids={"B"})
    runner = CrawlerRunner(db_session, sample_source, connector, rate_limit_seconds=0, retry_attempts=1, sleep_fn=lambda _: None)

    run = runner.run()

    assert run.status == CrawlerRunStatus.PARTIAL
    assert run.tenders_discovered == 3
    assert run.tenders_new == 2
    assert "B" in run.error_summary
    assert sample_source.status == SourceStatus.DEGRADED


def test_all_items_failing_marks_run_failed_and_source_down(db_session, sample_source):
    connector = _FakeConnector(sample_source, _refs("A", "B"), fail_source_tender_ids={"A", "B"})
    runner = CrawlerRunner(db_session, sample_source, connector, rate_limit_seconds=0, retry_attempts=1, sleep_fn=lambda _: None)

    run = runner.run()

    assert run.status == CrawlerRunStatus.FAILED
    assert run.tenders_new == 0
    assert sample_source.status == SourceStatus.DOWN
    assert sample_source.last_failure_at is not None


def test_discover_failure_marks_run_failed_without_raising(db_session, sample_source):
    class _BrokenDiscoverConnector(_FakeConnector):
        def discover(self):
            raise ConnectionError("portal unreachable")

    connector = _BrokenDiscoverConnector(sample_source, [])
    runner = CrawlerRunner(db_session, sample_source, connector, retry_attempts=1, sleep_fn=lambda _: None)

    run = runner.run()

    assert run.status == CrawlerRunStatus.FAILED
    assert run.tenders_discovered == 0
    assert "portal unreachable" in run.error_summary


def test_transient_failure_is_retried_and_succeeds(db_session, sample_source):
    connector = _FakeConnector(sample_source, _refs("A"), flaky_source_tender_ids={"A"})
    runner = CrawlerRunner(db_session, sample_source, connector, retry_attempts=3, rate_limit_seconds=0, sleep_fn=lambda _: None)

    run = runner.run()

    assert run.status == CrawlerRunStatus.SUCCESS
    assert run.tenders_new == 1
    # fetch_tender was called twice for "A": once failing, once succeeding
    assert connector.fetch_calls.count("A") == 2
