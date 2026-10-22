import io
import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.exceptions import DomainError
from app.document_processing.storage import get_storage_backend
from app.models.enums import DocumentType
from app.models.tender_document import TenderDocument
from app.models.user import User
from app.schemas.tender import DocumentRead
from app.services import document_processing_service

router = APIRouter(prefix="/tenders/{tender_id}/documents", tags=["documents"])


def _get_document_or_404(db: Session, tender_id: uuid.UUID, document_id: uuid.UUID) -> TenderDocument:
    document = db.get(TenderDocument, document_id)
    if document is None or document.tender_id != tender_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    tender_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(default=DocumentType.OTHER),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "bd_manager", "technical")),
):
    data = await file.read()
    try:
        return document_processing_service.upload_document(db, tender_id, file.filename, data, document_type)
    except DomainError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{document_id}/process", response_model=DocumentRead)
def process_document(
    tender_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("admin", "bd_manager", "technical")),
):
    document = _get_document_or_404(db, tender_id, document_id)
    return document_processing_service.process_document(db, document)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    tender_id: uuid.UUID, document_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return _get_document_or_404(db, tender_id, document_id)


@router.get("/{document_id}/download")
def download_document(
    tender_id: uuid.UUID, document_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    """Always streamed through this authenticated endpoint — documents are
    never served from a public/unauthenticated path (brief §20).

    A crawled document (e.g. a GeM bid PDF) is only known by its
    `source_url` until someone processes it; downloading it fetches it from
    the portal through the server first, then stores and processes it, so
    the user never depends on reaching the portal from their own browser.
    If the portal fetch fails, the reason is returned instead of a bare 404.
    """
    document = _get_document_or_404(db, tender_id, document_id)
    if not document.storage_path and document.source_url:
        document = document_processing_service.process_document(db, document)
    if not document.storage_path:
        if document.source_url:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not fetch this document from the portal: {document.last_processing_error}",
            )
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This document has no stored file")

    try:
        data = get_storage_backend().get(document.storage_path)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Stored file is missing")

    return StreamingResponse(
        io.BytesIO(data),
        media_type=mimetypes.guess_type(document.file_name)[0] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{document.file_name}"'},
    )
