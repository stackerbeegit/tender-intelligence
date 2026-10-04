"""
Drives one connector end-to-end: discover() once, then
fetch/parse/normalise/ingest per discovered reference, with per-step retry,
inter-item rate limiting, and failure isolation — one bad tender logs an
error and moves on rather than aborting the whole run. Every run is
recorded as a `CrawlerRun` row and rolls up into the owning `Source`'s
health status, which is what the admin "Source Health" view reads.
"""
import time
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.connectors.base.base_connector import BaseConnector
from app.connectors.base.types import DiscoveredTenderRef, NormalisedTender
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.crawler_run import CrawlerRun
from app.models.enums import CrawlerRunStatus, SourceStatus
from app.models.source import Source
from app.services import tender_ingestion_service

logger = get_logger(__name__)


class CrawlerRunner:
    def __init__(
        self,
        db: Session,
        source: Source,
        connector: BaseConnector,
        rate_limit_seconds: float | None = None,
        retry_attempts: int | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        settings = get_settings()
        self.db = db
        self.source = source
        self.connector = connector
        self.rate_limit_seconds = (
            rate_limit_seconds if rate_limit_seconds is not None else settings.crawler_default_rate_limit_seconds
        )
        self.retry_attempts = (
            retry_attempts if retry_attempts is not None else settings.crawler_default_retry_attempts
        )
        self._sleep = sleep_fn

    def run(self) -> CrawlerRun:
        run = CrawlerRun(
            source_id=self.source.id,
            started_at=datetime.now(timezone.utc),
            status=CrawlerRunStatus.RUNNING,
        )
        self.db.add(run)
        self.db.commit()

        try:
            refs = self._with_retry(self.connector.discover)
        except Exception as exc:
            logger.exception("discover() failed for source=%s", self.source.name)
            self._finalize(run, status=CrawlerRunStatus.FAILED, discovered=0, new=0, updated=0, errors=[str(exc)])
            return run

        errors: list[str] = []
        tenders_new = 0
        tenders_updated = 0

        for index, ref in enumerate(refs):
            if index > 0 and self.rate_limit_seconds:
                self._sleep(self.rate_limit_seconds)
            try:
                normalised = self._with_retry(lambda: self._process_ref(ref))
                _, created = tender_ingestion_service.ingest_tender(self.db, self.source.id, normalised)
                if created:
                    tenders_new += 1
                else:
                    tenders_updated += 1
            except Exception as exc:
                logger.exception("Failed to process ref=%s for source=%s", ref, self.source.name)
                errors.append(f"{ref.source_tender_id}: {exc}")

        if errors and (tenders_new + tenders_updated) == 0:
            status = CrawlerRunStatus.FAILED
        elif errors:
            status = CrawlerRunStatus.PARTIAL
        else:
            status = CrawlerRunStatus.SUCCESS

        self._finalize(
            run, status=status, discovered=len(refs), new=tenders_new, updated=tenders_updated, errors=errors
        )
        return run

    def _process_ref(self, ref: DiscoveredTenderRef) -> NormalisedTender:
        raw_tender = self.connector.fetch_tender(ref)
        raw_documents = self.connector.fetch_documents(ref, raw_tender)
        parsed = self.connector.parse(raw_tender, raw_documents)
        return self.connector.normalise(parsed)

    def _with_retry(self, fn: Callable):
        return retry(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=0.1, max=2),
            reraise=True,
        )(fn)()

    def _finalize(
        self,
        run: CrawlerRun,
        *,
        status: CrawlerRunStatus,
        discovered: int,
        new: int,
        updated: int,
        errors: list[str],
    ) -> None:
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.tenders_discovered = discovered
        run.tenders_new = new
        run.tenders_updated = updated
        run.error_summary = "\n".join(errors[:20]) if errors else None

        if status == CrawlerRunStatus.SUCCESS:
            self.source.last_successful_crawl_at = run.finished_at
            self.source.status = SourceStatus.HEALTHY
        elif status == CrawlerRunStatus.PARTIAL:
            self.source.last_successful_crawl_at = run.finished_at
            self.source.status = SourceStatus.DEGRADED
        else:
            self.source.last_failure_at = run.finished_at
            self.source.status = SourceStatus.DOWN

        self.db.add(run)
        self.db.add(self.source)
        self.db.commit()
