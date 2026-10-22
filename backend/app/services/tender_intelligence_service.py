"""
Runs the Sprint 4 intelligence pipeline for one tender:

    ensure each document has per-page text (re-processing documents from
    before migration 0005) -> extract + verify facts per document ->
    replace the tender's fact rows -> generate the AI summary and
    AI-assigned categories -> record the run on `tender_analysis`.

A run is all-or-nothing for facts: they are replaced in the same
transaction as the summary, so a failure part-way leaves the previous
run's facts intact and the `tender_analysis` row says FAILED with the
reason (brief Rule 6 — never silently swallowed).

Runs synchronously inside the request for now, matching Sprint 3's
document processing; moving both onto Celery workers is Sprint 8 work.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.logging import get_logger
from app.intelligence.extraction.extractor import DocumentExtraction, extract_document
from app.intelligence.llm import LLMClient, get_llm_client
from app.intelligence.summary import generate_summary
from app.models.enums import AnalysisStatus, ExtractionStatus
from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.tender import Tender
from app.models.tender_analysis import TenderAnalysis
from app.models.tender_category import TenderCategory
from app.models.tender_document import TenderDocument
from app.models.tender_eligibility import TenderEligibility
from app.models.tender_requirement import TenderRequirement
from app.models.tender_submission_document import TenderSubmissionDocument
from app.services import document_processing_service

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _start_run(db: Session, tender: Tender) -> TenderAnalysis:
    analysis = db.query(TenderAnalysis).filter_by(tender_id=tender.id).one_or_none()
    if analysis is None:
        analysis = TenderAnalysis(tender_id=tender.id, status=AnalysisStatus.RUNNING, started_at=_utcnow())
        db.add(analysis)
    analysis.status = AnalysisStatus.RUNNING
    analysis.started_at = _utcnow()
    analysis.finished_at = None
    analysis.error = None
    db.commit()
    return analysis


def _ensure_pages(db: Session, document: TenderDocument) -> list[str] | None:
    if document.extracted_pages is None and (document.storage_path or document.source_url):
        document_processing_service.process_document(db, document)
    if document.extraction_status != ExtractionStatus.DONE:
        return None
    return document.extracted_pages


def analyse_tender(db: Session, tender: Tender, llm: LLMClient | None = None) -> TenderAnalysis:
    tender_id = tender.id
    _start_run(db, tender)

    try:
        llm = llm or get_llm_client()
        settings = get_settings()

        extractions: list[tuple[TenderDocument, DocumentExtraction]] = []
        skipped_documents: list[str] = []
        for document in list(tender.documents):
            pages = _ensure_pages(db, document)
            if not pages:
                skipped_documents.append(document.file_name)
                continue
            extraction = extract_document(
                llm,
                document_id=str(document.id),
                file_name=document.file_name,
                tender_title=tender.title,
                pages=pages,
                max_chars_per_call=settings.llm_max_chars_per_call,
            )
            extractions.append((document, extraction))

        if not extractions:
            raise DomainError(
                "No document text available to analyse — upload and process at least one tender document"
                + (f" (unreadable: {', '.join(skipped_documents)})" if skipped_documents else "")
            )

        requirements, eligibility = _replace_facts(db, tender_id, extractions, llm.model_name)
        summary, summary_response = generate_summary(llm, tender, requirements, eligibility)
        _replace_ai_categories(db, tender, summary.get("categories", []))

        analysis = db.query(TenderAnalysis).filter_by(tender_id=tender_id).one()
        analysis.status = AnalysisStatus.DONE
        analysis.summary = summary
        analysis.documents_analysed = len(extractions)
        analysis.generated_by_model = summary_response.model
        analysis.run_stats = _run_stats(extractions, skipped_documents, summary_response.usage)
        analysis.finished_at = _utcnow()
        db.commit()

    except Exception as exc:  # noqa: BLE001 — recorded on the analysis row, then surfaced to the caller
        logger.exception("Tender analysis failed for tender=%s", tender_id)
        db.rollback()
        analysis = db.query(TenderAnalysis).filter_by(tender_id=tender_id).one()
        analysis.status = AnalysisStatus.FAILED
        analysis.error = str(exc)
        analysis.finished_at = _utcnow()
        db.commit()

    db.refresh(analysis)
    return analysis


def _replace_facts(
    db: Session,
    tender_id: uuid.UUID,
    extractions: list[tuple[TenderDocument, DocumentExtraction]],
    model_name: str,
) -> tuple[list[TenderRequirement], list[TenderEligibility]]:
    db.execute(delete(TenderRequirement).where(TenderRequirement.tender_id == tender_id))
    db.execute(delete(TenderEligibility).where(TenderEligibility.tender_id == tender_id))
    db.execute(delete(TenderSubmissionDocument).where(TenderSubmissionDocument.tender_id == tender_id))

    requirements: list[TenderRequirement] = []
    eligibility: list[TenderEligibility] = []
    for document, extraction in extractions:
        for item in extraction.requirements:
            requirements.append(
                TenderRequirement(
                    tender_id=tender_id,
                    document_id=document.id,
                    category=item.category,
                    summary=item.summary,
                    requirement_text=item.quote,
                    details=item.details,
                    page_number=item.page_number,
                    generated_by_model=model_name,
                )
            )
        for item in extraction.eligibility:
            eligibility.append(
                TenderEligibility(
                    tender_id=tender_id,
                    document_id=document.id,
                    criterion_type=item.criterion_type,
                    summary=item.summary,
                    criterion_text=item.quote,
                    extracted_value=item.value,
                    page_number=item.page_number,
                    generated_by_model=model_name,
                )
            )
        db.add_all(
            TenderSubmissionDocument(
                tender_id=tender_id,
                document_id=document.id,
                kind=item.kind,
                document_name=item.document_name,
                mandatory=item.mandatory,
                format_instructions=item.format_instructions,
                form_reference=item.form_reference,
                clause_text=item.quote,
                page_number=item.page_number,
                generated_by_model=model_name,
            )
            for item in extraction.submission_documents
        )
    db.add_all(requirements + eligibility)
    db.flush()  # assigns ids, which the summary's fact_refs point at
    return requirements, eligibility


def _replace_ai_categories(db: Session, tender: Tender, categories: list[dict]) -> None:
    """Only rows the engine owns (confidence set) are replaced; manually
    set categories (confidence null) are never touched or duplicated."""
    manual = {row.category for row in tender.categories if row.confidence is None}
    for row in [row for row in tender.categories if row.confidence is not None]:
        tender.categories.remove(row)

    best: dict[TenderCategoryEnum, float] = {}
    for entry in categories:
        category = TenderCategoryEnum(entry["category"])
        confidence = min(max(float(entry["confidence"]), 0.0), 1.0)
        best[category] = max(confidence, best.get(category, 0.0))

    for category, confidence in best.items():
        if category in manual:
            continue
        tender.categories.append(
            TenderCategory(category=category, confidence=Decimal(str(round(confidence, 2))))
        )
    db.flush()


def _run_stats(
    extractions: list[tuple[TenderDocument, DocumentExtraction]],
    skipped_documents: list[str],
    summary_usage: dict[str, int],
) -> dict:
    per_document = [
        {
            "document_id": str(document.id),
            "file_name": document.file_name,
            "pages_read": e.pages_read,
            "llm_calls": e.llm_calls,
            "requirements": len(e.requirements),
            "eligibility": len(e.eligibility),
            "submission_documents": len(e.submission_documents),
            "dropped_unverified": e.dropped_unverified,
            "dropped_duplicates": e.dropped_duplicates,
            "dropped_examples": e.dropped_examples,
        }
        for document, e in extractions
    ]
    return {
        "documents": per_document,
        "skipped_documents": skipped_documents,
        "llm_calls": sum(e.llm_calls for _, e in extractions) + 1,
        "input_tokens": sum(e.input_tokens for _, e in extractions) + summary_usage.get("input_tokens", 0),
        "output_tokens": sum(e.output_tokens for _, e in extractions) + summary_usage.get("output_tokens", 0),
        "dropped_unverified": sum(e.dropped_unverified for _, e in extractions),
    }
