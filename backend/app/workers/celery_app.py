"""
Celery app + Beat schedule. Run both processes alongside the API:

    celery -A app.workers.celery_app worker --loglevel=INFO
    celery -A app.workers.celery_app beat --loglevel=INFO

(docker-compose runs them as the `worker` and `beat` services.)
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "stackerbee",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    timezone=settings.scheduler_timezone,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # A full crawl takes minutes; keep results around long enough to inspect.
    result_expires=7 * 24 * 60 * 60,
)

celery_app.conf.beat_schedule = (
    {
        "daily-crawl-all-sources": {
            "task": "app.workers.tasks.crawl_all_sources",
            "schedule": crontab(hour=settings.scheduled_crawl_hour, minute=settings.scheduled_crawl_minute),
        }
    }
    if settings.scheduled_crawl_enabled
    else {}
)
