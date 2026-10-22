"""
Centralised application settings, loaded from environment variables (see
`.env.example` at the repo root). No module outside `core/config.py` should
read `os.environ` directly — this keeps configuration auditable in one place
and makes it possible to override settings cleanly in tests.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # --- API ---
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- Security ---
    secret_key: str = "changeme-generate-a-long-random-secret"
    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 10080
    jwt_algorithm: str = "HS256"

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://stackerbee:changeme-strong-password@localhost:5432/stackerbee_tender"
    )

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Scheduled crawls (Celery Beat) ---
    # Every crawler-enabled source is crawled once a day at this local time
    # (`scheduler_timezone`), when GeM and the app are both quiet.
    scheduled_crawl_enabled: bool = True
    scheduled_crawl_hour: int = 1
    scheduled_crawl_minute: int = 0
    scheduler_timezone: str = "Asia/Kolkata"
    # Upper bound on one all-sources run; the overlap lock expires after it
    # so a crashed worker can't block tomorrow's crawl forever.
    scheduled_crawl_lock_timeout_seconds: int = 4 * 60 * 60

    # --- Object storage ---
    # "minio" | "s3" (both via the S3 backend, just different endpoint/creds)
    # "local" (plain filesystem — for dev environments without a running
    # MinIO/S3, e.g. this project's native-Postgres local setup)
    storage_provider: str = "minio"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket_name: str = "tender-documents"
    s3_region: str = "ap-south-1"
    s3_use_ssl: bool = False
    local_storage_path: str = "storage/documents"

    # --- Document processing (Sprint 3+) ---
    max_document_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    allowed_document_mime_types: tuple[str, ...] = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/zip",  # some portals serve tender bundles as .zip
    )
    ocr_min_chars_per_page: int = 20  # below this, a PDF page is treated as scanned
    document_download_timeout_seconds: float = 60.0

    # --- LLM abstraction (Sprint 4+) ---
    # "anthropic" | "openai" (any OpenAI-compatible endpoint via
    # openai_base_url). See app/intelligence/llm/__init__.py.
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    # low | medium | high | xhigh | max — extraction is a fairly mechanical
    # read-and-quote task, so the model default (medium) is a sensible start.
    anthropic_effort: str = "medium"
    # Server-side refusal fallback (see anthropic_client.py). Supported on
    # current models such as claude-opus-5-5; turn off if ANTHROPIC_MODEL
    # is set to a model that rejects the `fallbacks` parameter.
    anthropic_refusal_fallback: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_request_timeout_seconds: float = 300.0
    llm_max_output_tokens: int = 16000
    # Upper bound on document text sent in a single extraction call. Pages
    # are batched up to this size (never split mid-page, unless one page
    # alone exceeds it), so a large tender is never sent to the LLM whole.
    llm_max_chars_per_call: int = 24000

    # --- Crawler / connector behaviour (Sprint 2+) ---
    crawler_default_rate_limit_seconds: float = 2.0
    crawler_default_retry_attempts: int = 3
    crawler_user_agent: str = "StackerbeeTenderBot/1.0 (+https://stackerbee.com/bot)"
    # CA bundle for outbound HTTPS (crawler + document downloads). Empty =
    # the OS bundle if present, else certifi — see app/core/http.py.
    outbound_ca_bundle: str = ""

    # --- GeM connector ---
    # bidplus.gem.gov.in/all-bids is GeM's own public bid-listing page; this
    # is the same JSON endpoint its frontend calls to render that page for
    # any anonymous visitor (no login, no CAPTCHA). `terms_access_notes` on
    # the `sources` row documents the access-policy review. discover()
    # searches per Stackerbee focus-area keyword rather than taking the
    # unfiltered "all ongoing bids" feed — `gem_pages_per_keyword` bounds
    # each keyword's share of the crawl to a polite request volume.
    gem_bidplus_base_url: str = "https://bidplus.gem.gov.in"
    gem_pages_per_keyword: int = 2
    gem_request_timeout_seconds: float = 30.0
    # Fetch each bid's PDF during the crawl to read the consignee (delivery)
    # pincode/city -> state. GeM's listing payload has no location field.
    gem_extract_consignee_locations: bool = True

    # --- Notifications (Sprint 6+) ---
    notifications_email_enabled: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@stackerbee.com"
    smtp_use_tls: bool = True
    # Used to build links in emails (e.g. https://tenders.stackerbee.com).
    app_base_url: str = "http://localhost:5173"
    # Daily digest e-mail (Beat schedule, `scheduler_timezone`).
    digest_enabled: bool = True
    digest_hour: int = 8
    digest_minute: int = 30

    # --- Opportunity CRM (Sprint 6) ---
    # A qualification at or above this relevance score, and not
    # NOT_ELIGIBLE, promotes an open tender to a NEW opportunity
    # automatically. 0 disables auto-promotion.
    opportunity_auto_promote_min_score: int = 70


@lru_cache
def get_settings() -> Settings:
    """Settings are cached for the process lifetime; tests override via
    dependency_overrides or by constructing `Settings()` directly."""
    return Settings()
