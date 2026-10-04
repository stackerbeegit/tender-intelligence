import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SourceStatus, SourceType


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    organisation: str | None = None
    url: str | None = None
    source_type: SourceType
    country: str = "India"
    state: str | None = None
    auth_required: bool = False
    api_available: bool = False
    frequency: str | None = None
    terms_access_notes: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    organisation: str | None = None
    url: str | None = None
    state: str | None = None
    auth_required: bool | None = None
    api_available: bool | None = None
    crawler_enabled: bool | None = None
    frequency: str | None = None
    terms_access_notes: str | None = None


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    organisation: str | None
    url: str | None
    source_type: SourceType
    country: str
    state: str | None
    auth_required: bool
    api_available: bool
    crawler_enabled: bool
    frequency: str | None
    last_successful_crawl_at: datetime | None
    last_failure_at: datetime | None
    status: SourceStatus
    terms_access_notes: str | None
    created_at: datetime
