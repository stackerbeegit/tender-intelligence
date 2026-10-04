"""
Exercises document_processing_service against real files, a real
(throwaway) local storage backend, and the real database session — the
only things stubbed are network calls (document download) and the OCR
engine, which genuinely isn't installed in this environment (see
tests/fixtures/documents and scripts/generate_doc_fixtures.py for how the
fixtures were produced). The missing-tesseract condition is exercised for
real, not mocked — this environment really doesn't have it, which is
exactly the "OCR failure" scenario the project brief asks to test.
"""
from pathlib import Path

import pytest

from app.core.exceptions import DocumentDownloadError
from app.models.enums import DocumentType, ExtractionStatus, OcrStatus
from app.models.tender_document import TenderDocument
from app.services import document_processing_service

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "documents"


def _read(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def test_upload_then_process_native_pdf_succeeds(db_session, sample_tender, storage_backend):
    document = document_processing_service.upload_document(
        db_session, sample_tender.id, "sample_native.pdf", _read("sample_native.pdf"), DocumentType.NIT
    )
    assert document.storage_path is not None
    assert document.checksum_sha256 is not None
    assert document.file_size_bytes == len(_read("sample_native.pdf"))

    processed = document_processing_service.process_document(db_session, document)

    assert processed.extraction_status == ExtractionStatus.DONE
    assert processed.ocr_status == OcrStatus.NOT_REQUIRED
    assert "Sample Tender Notice" in processed.extracted_text
    assert processed.page_count == 1
    assert processed.last_processing_error is None


def test_upload_then_process_xlsx_succeeds(db_session, sample_tender, storage_backend):
    document = document_processing_service.upload_document(
        db_session, sample_tender.id, "sample.xlsx", _read("sample.xlsx"), DocumentType.BOQ
    )
    processed = document_processing_service.process_document(db_session, document)

    assert processed.extraction_status == ExtractionStatus.DONE
    assert "Laptop - 16GB RAM" in processed.extracted_text


def test_scanned_pdf_triggers_genuine_ocr_failure_in_this_environment(db_session, sample_tender, storage_backend):
    """Real OCR-unavailable condition (tesseract isn't installed here) —
    not mocked. extraction_status still ends up FAILED (no text at all
    was recovered), ocr_status specifically says OCR failed, and the
    reason is recorded rather than silently lost."""
    document = document_processing_service.upload_document(
        db_session, sample_tender.id, "sample_scanned.pdf", _read("sample_scanned.pdf"), DocumentType.NIT
    )
    processed = document_processing_service.process_document(db_session, document)

    assert processed.ocr_status == OcrStatus.FAILED
    assert processed.extraction_status == ExtractionStatus.FAILED
    assert processed.extracted_text is None
    assert "OCR unavailable" in processed.last_processing_error


def test_document_with_neither_storage_nor_source_url_fails_cleanly(db_session, sample_tender, storage_backend):
    """A document record with no way to fetch bytes at all — the
    orchestrator's guard clause, not a network failure."""
    document = TenderDocument(
        tender_id=sample_tender.id,
        file_name="orphaned.pdf",
        document_type=DocumentType.OTHER,
        extraction_status=ExtractionStatus.PENDING,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    processed = document_processing_service.process_document(db_session, document)

    assert processed.extraction_status == ExtractionStatus.FAILED
    assert "neither a stored file nor a source_url" in processed.last_processing_error


def test_download_failure_is_recorded_not_raised(db_session, sample_tender, storage_backend, monkeypatch):
    def _boom(url):
        raise DocumentDownloadError(f"Could not download {url}: connection refused")

    monkeypatch.setattr("app.services.document_processing_service.downloader.download_document", _boom)

    document = TenderDocument(
        tender_id=sample_tender.id,
        file_name="unreachable.pdf",
        document_type=DocumentType.NIT,
        source_url="https://example.invalid/does-not-exist.pdf",
        extraction_status=ExtractionStatus.PENDING,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    processed = document_processing_service.process_document(db_session, document)

    assert processed.extraction_status == ExtractionStatus.FAILED
    assert "connection refused" in processed.last_processing_error
    assert processed.storage_path is None  # never got far enough to store anything


def test_upload_rejects_unsupported_file_type_before_creating_a_row(db_session, sample_tender, storage_backend):
    from app.core.exceptions import UnsupportedFileTypeError
    from sqlalchemy import select
    from app.models.tender_document import TenderDocument as TD

    with pytest.raises(UnsupportedFileTypeError):
        document_processing_service.upload_document(
            db_session, sample_tender.id, "not_a_real_doc.txt", b"plain text content", DocumentType.OTHER
        )

    assert db_session.scalar(select(TD).where(TD.tender_id == sample_tender.id)) is None
