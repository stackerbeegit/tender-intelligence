import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.connectors.registry import get_connector_class
from app.connectors.base.runner import CrawlerRunner
from app.core.database import get_db
from app.models.source import Source
from app.models.user import User
from app.repositories.source_repository import SourceRepository
from app.schemas.crawler_run import CrawlerRunRead
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.services import source_service
from app.services.source_service import CrawlerEnableWithoutAccessNotesError

router = APIRouter(prefix="/sources", tags=["sources"])


def _get_source_or_404(db: Session, source_id: uuid.UUID) -> Source:
    source = SourceRepository(db).get_by_id(source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db), _user: User = Depends(require_roles("admin", "technical"))):
    """Also the data behind the admin 'Source Health' view (brief §21)."""
    return SourceRepository(db).list_all()


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: SourceCreate, db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))
):
    return source_service.create_source(db, payload)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(
    source_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(require_roles("admin", "technical"))
):
    return _get_source_or_404(db, source_id)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    source = _get_source_or_404(db, source_id)
    try:
        return source_service.update_source(db, source, payload)
    except CrawlerEnableWithoutAccessNotesError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{source_id}/crawl", response_model=CrawlerRunRead, status_code=status.HTTP_201_CREATED)
def run_crawl(
    source_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))
):
    """Synchronous for now — fine for an admin-triggered manual run against
    a handful of pages; a scheduled/async version via Celery is workers/
    territory for a later sprint."""
    source = _get_source_or_404(db, source_id)
    if not source.crawler_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="This source does not have crawling enabled")

    connector_cls = get_connector_class(source.source_type)
    if connector_cls is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"No connector is registered for source_type={source.source_type.value}"
        )

    connector = connector_cls(source)
    return CrawlerRunner(db, source, connector).run()
