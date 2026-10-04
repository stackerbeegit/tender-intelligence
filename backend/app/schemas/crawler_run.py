import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CrawlerRunStatus


class CrawlerRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    status: CrawlerRunStatus
    tenders_discovered: int
    tenders_new: int
    tenders_updated: int
    error_summary: str | None
