"""
Source CRUD plus the one rule that matters architecturally: a source
cannot have `crawler_enabled=True` unless `terms_access_notes` is filled
in (docs/database.md §2) — this is where that's enforced, not a DB
constraint, so the rule has one readable home.
"""
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.enums import SourceStatus
from app.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.schemas.source import SourceCreate, SourceUpdate


class CrawlerEnableWithoutAccessNotesError(DomainError):
    pass


def create_source(db: Session, payload: SourceCreate) -> Source:
    source = Source(
        name=payload.name,
        organisation=payload.organisation,
        url=payload.url,
        source_type=payload.source_type,
        country=payload.country,
        state=payload.state,
        auth_required=payload.auth_required,
        api_available=payload.api_available,
        crawler_enabled=False,
        frequency=payload.frequency,
        status=SourceStatus.DISABLED,
        terms_access_notes=payload.terms_access_notes,
    )
    return SourceRepository(db).create(source)


def update_source(db: Session, source: Source, payload: SourceUpdate) -> Source:
    data = payload.model_dump(exclude_unset=True)

    wants_crawler_enabled = data.get("crawler_enabled")
    effective_notes = data.get("terms_access_notes", source.terms_access_notes)
    if wants_crawler_enabled and not effective_notes:
        raise CrawlerEnableWithoutAccessNotesError(
            "terms_access_notes must be filled in before crawler_enabled can be set to true (Rule 11)"
        )

    for field, value in data.items():
        setattr(source, field, value)

    db.add(source)
    db.commit()
    db.refresh(source)
    return source
