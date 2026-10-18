"""
Orchestrates one document's full pipeline: get bytes (from storage if
already uploaded, else download from `source_url`) -> validate -> store
(if not already stored) -> extract text -> OCR fallback for any page
that needs it. Always leaves the document in a terminal status
(DONE/FAILED) rather than letting a library exception propagate past
this boundary — this is the one place that's true, so API callers never
see a raw pypdf/pytesseract exception.
"""
import hashlib
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, OcrUnavailableError
from app.core.logging import get_logger
from app.document_processing import downloader, validators
from app.document_processing.extractors import extract_pages
from app.document_processing.ocr import ocr_pdf_page
from app.document_processing.storage import get_storage_backend
from app.models.enums import DocumentType, ExtractionStatus, OcrStatus
from app.models.tender_document import TenderDocument

logger = get_logger(__name__)


def upload_document(
    db: Session, tender_id: uuid.UUID, file_name: str, data: bytes, document_type: DocumentType
) -> TenderDocument:
    """
    The Rule 12 manual-upload path for an actual file (as opposed to
    `manual_tender_service`, which only records metadata/URLs). Validated
    and stored immediately — a bad upload never creates a row at all,
    rather than creating one and marking it failed.
    """
    content_type = validators.validate_file(data, file_name)

    document = TenderDocument(
        tender_id=tender_id,
        file_name=file_name,
        document_type=document_type,
        extraction_status=ExtractionStatus.PENDING,
    )
    db.add(document)
    db.flush()  # need document.id for the storage key

    key = _storage_key(document)
    get_storage_backend().put(key, data, content_type=content_type)
    document.storage_path = key
    document.checksum_sha256 = hashlib.sha256(data).hexdigest()
    document.file_size_bytes = len(data)

    db.commit()
    db.refresh(document)
    return document


def _storage_key(document: TenderDocument) -> str:
    return f"tenders/{document.tender_id}/documents/{document.id}/{document.file_name}"


def _get_bytes(document: TenderDocument) -> bytes:
    storage = get_storage_backend()
    if document.storage_path and storage.exists(document.storage_path):
        return storage.get(document.storage_path)
    if not document.source_url:
        raise DomainError(f"Document {document.id} has neither a stored file nor a source_url to download from")
    return downloader.download_document(document.source_url)


def process_document(db: Session, document: TenderDocument) -> TenderDocument:
    try:
        data = _get_bytes(document)
        content_type = validators.validate_file(data, document.file_name)

        if not document.storage_path:
            key = _storage_key(document)
            get_storage_backend().put(key, data, content_type=content_type)
            document.storage_path = key

        document.checksum_sha256 = hashlib.sha256(data).hexdigest()
        document.file_size_bytes = len(data)

        pages, needs_ocr = extract_pages(data, content_type)

        ocr_was_needed = any(needs_ocr)
        ocr_failed = False
        for page_index, needs in enumerate(needs_ocr):
            if not needs:
                continue
            try:
                pages[page_index] = ocr_pdf_page(data, page_index)
            except OcrUnavailableError as exc:
                ocr_failed = True
                document.last_processing_error = f"OCR unavailable for page {page_index + 1}: {exc}"
                logger.warning("OCR unavailable for document=%s page=%d: %s", document.id, page_index, exc)

        document.extracted_text = "\n\n".join(page.strip() for page in pages if page.strip()) or None
        document.extracted_pages = [page.strip() for page in pages] if document.extracted_text else None
        document.page_count = len(pages)
        document.extraction_status = (
            ExtractionStatus.DONE if document.extracted_text else ExtractionStatus.FAILED
        )
        if not ocr_was_needed:
            document.ocr_status = OcrStatus.NOT_REQUIRED
        elif ocr_failed:
            document.ocr_status = OcrStatus.FAILED
        else:
            document.ocr_status = OcrStatus.DONE
            document.last_processing_error = None

    except Exception as exc:  # noqa: BLE001 — this boundary always leaves a terminal status, never raises
        logger.exception("Document processing failed for document=%s", document.id)
        document.extraction_status = ExtractionStatus.FAILED
        document.last_processing_error = str(exc)

    db.add(document)
    db.commit()
    db.refresh(document)
    return document
