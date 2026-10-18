# Workers

Celery app (`celery_app.py`) and tasks (`tasks.py`).

## Daily crawl

Celery Beat fires `crawl_all_sources` every day at **01:00 Asia/Kolkata**
(`SCHEDULED_CRAWL_HOUR` / `SCHEDULED_CRAWL_MINUTE` / `SCHEDULER_TIMEZONE`;
`SCHEDULED_CRAWL_ENABLED=false` turns it off). It runs `CrawlerRunner` for every source
with `crawler_enabled = true` and a registered connector — the same code path as
`POST /api/v1/sources/{id}/crawl` — so results show up in `crawler_runs` and Source Health.
New bids are inserted; bids already stored are updated (deadline extensions, new
locations). A Redis lock skips a run if the previous one is still going.

Run alongside the API (docker-compose does this as the `worker` and `beat` services):

    celery -A app.workers.celery_app worker --loglevel=INFO --concurrency=1
    celery -A app.workers.celery_app beat --loglevel=INFO

Run exactly one `beat` process. Trigger a crawl now without waiting for 01:00:

    celery -A app.workers.celery_app call app.workers.tasks.crawl_all_sources

Still to come: document processing (Sprint 3 follow-up) and notifications/digests (Sprint 6).
