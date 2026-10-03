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

    # --- Object storage ---
    storage_provider: str = "minio"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket_name: str = "tender-documents"
    s3_region: str = "ap-south-1"
    s3_use_ssl: bool = False

    # --- LLM abstraction (Sprint 4+) ---
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # --- Notifications (Sprint 6+) ---
    notifications_email_enabled: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@stackerbee.com"
    smtp_use_tls: bool = True


@lru_cache
def get_settings() -> Settings:
    """Settings are cached for the process lifetime; tests override via
    dependency_overrides or by constructing `Settings()` directly."""
    return Settings()
