import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import SourceType
from app.models.source import Source


class SourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, source_id: uuid.UUID) -> Source | None:
        return self.db.get(Source, source_id)

    def get_by_type(self, source_type: SourceType) -> Source | None:
        return self.db.scalar(select(Source).where(Source.source_type == source_type))

    def list_all(self) -> list[Source]:
        return list(self.db.scalars(select(Source).order_by(Source.name)))

    def create(self, source: Source) -> Source:
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source
