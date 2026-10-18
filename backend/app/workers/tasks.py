"""
Scheduled tasks. `crawl_all_sources` is what Beat fires daily: it runs the
same CrawlerRunner as the admin "run crawl" endpoint, once per source that
has crawling enabled and a registered connector. Each source gets its own
DB session and failure boundary, so one broken portal never stops the rest;
its outcome is recorded on `crawler_runs` / `sources.status` as usual.
"""
from collections.abc import Callable

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

# Importing the connector packages registers them with the registry.
import app.connectors.gem  # noqa: F401
from app.connectors.base.runner import CrawlerRunner
from app.connectors.registry import get_connector_class
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.source import Source
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

_LOCK_NAME = "stackerbee:crawl_all_sources"


def _redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url)


def run_all_crawls(session_factory: Callable[[], Session] = SessionLocal) -> list[dict]:
    with session_factory() as db:
        sources = db.scalars(select(Source).where(Source.crawler_enabled.is_(True)).order_by(Source.name)).all()
        source_ids = [s.id for s in sources]

    results: list[dict] = []
    for source_id in source_ids:
        with session_factory() as db:
            source = db.get(Source, source_id)
            connector_cls = get_connector_class(source.source_type)
            if connector_cls is None:
                logger.warning("Skipping source=%s: no connector registered for %s", source.name, source.source_type)
                results.append({"source": source.name, "status": "skipped", "reason": "no connector"})
                continue
            try:
                run = CrawlerRunner(db, source, connector_cls(source)).run()
                results.append(
                    {
                        "source": source.name,
                        "status": run.status.value,
                        "discovered": run.tenders_discovered,
                        "new": run.tenders_new,
                        "updated": run.tenders_updated,
                    }
                )
                logger.info("Scheduled crawl finished for source=%s: %s", source.name, results[-1])
            except Exception as exc:  # noqa: BLE001 — CrawlerRunner already isolates per-tender errors
                logger.exception("Scheduled crawl crashed for source=%s", source.name)
                results.append({"source": source.name, "status": "error", "reason": str(exc)})
    return results


@celery_app.task(name="app.workers.tasks.crawl_all_sources")
def crawl_all_sources() -> list[dict] | dict:
    settings = get_settings()
    lock = _redis().lock(_LOCK_NAME, timeout=settings.scheduled_crawl_lock_timeout_seconds, blocking=False)
    if not lock.acquire():
        logger.warning("Skipping scheduled crawl: a previous run is still in progress")
        return {"status": "skipped", "reason": "previous run still in progress"}
    try:
        return run_all_crawls()
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass  # expired mid-run; nothing to release
