"""
End-to-end through the intelligence service: the representative RFP
(tests/fixtures/documents/sample_rfp.pdf, a real 4-page PDF) is uploaded
and processed by the real Sprint 3 pipeline, then analysed with the
scripted FakeLLMClient. Stored facts must match
tests/fixtures/intelligence/sample_rfp_expected.json exactly (Sprint 4
exit criterion), and every stored fact must carry a citation whose quote
really is on that page of that document.
"""
import json
from decimal import Decimal
from pathlib import Path

from app.core.config import get_settings
from app.intelligence.extraction.citations import quote_on_page
from app.models.enums import AnalysisStatus, DocumentType
from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.tender_category import TenderCategory
from app.models.tender_document import TenderDocument
from app.models.tender_eligibility import TenderEligibility
from app.models.tender_requirement import TenderRequirement
from app.models.tender_submission_document import TenderSubmissionDocument
from app.services import document_processing_service, tender_intelligence_service
from tests.support.fake_llm import FakeLLMClient

FIXTURES = Path(__file__).parent.parent / "fixtures"
EXPECTED = json.loads((FIXTURES / "intelligence" / "sample_rfp_expected.json").read_text())


def _upload_rfp(db_session, tender, process: bool = True) -> TenderDocument:
    data = (FIXTURES / "documents" / "sample_rfp.pdf").read_bytes()
    document = document_processing_service.upload_document(db_session, tender.id, "RFP.pdf", data, DocumentType.RFP)
    if process:
        document = document_processing_service.process_document(db_session, document)
    return document


def _facts(db_session, tender_id):
    requirements = db_session.query(TenderRequirement).filter_by(tender_id=tender_id).all()
    eligibility = db_session.query(TenderEligibility).filter_by(tender_id=tender_id).all()
    return requirements, eligibility


def _sort_key(fact: dict) -> tuple:
    return (fact["page_number"], fact.get("requirement_text") or fact.get("criterion_text"))


def test_processing_now_keeps_per_page_text(db_session, sample_tender, storage_backend):
    document = _upload_rfp(db_session, sample_tender)
    assert document.page_count == 4
    assert len(document.extracted_pages) == 4
    assert document.extracted_pages[2].startswith("Section 5: Pre-Qualification Criteria")
    assert document.extracted_pages[3].startswith("Section 6: Documents to be Submitted")


def test_sample_rfp_produces_expected_structured_facts(db_session, sample_tender, storage_backend):
    _upload_rfp(db_session, sample_tender)

    analysis = tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())

    assert analysis.status == AnalysisStatus.DONE, analysis.error
    requirements, eligibility = _facts(db_session, sample_tender.id)

    actual_requirements = sorted(
        (
            {
                "category": r.category.value,
                "page_number": r.page_number,
                "requirement_text": r.requirement_text,
                "details": r.details,
            }
            for r in requirements
        ),
        key=_sort_key,
    )
    actual_eligibility = sorted(
        (
            {
                "criterion_type": e.criterion_type.value,
                "page_number": e.page_number,
                "criterion_text": e.criterion_text,
                "extracted_value": e.extracted_value,
            }
            for e in eligibility
        ),
        key=_sort_key,
    )
    assert actual_requirements == sorted(EXPECTED["requirements"], key=_sort_key)
    assert actual_eligibility == sorted(EXPECTED["eligibility"], key=_sort_key)
    submission_documents = db_session.query(TenderSubmissionDocument).filter_by(tender_id=sample_tender.id).all()
    actual_submission = sorted(
        (
            {
                "kind": d.kind.value,
                "document_name": d.document_name,
                "page_number": d.page_number,
                "clause_text": d.clause_text,
                "mandatory": d.mandatory,
                "format_instructions": d.format_instructions,
                "form_reference": d.form_reference,
            }
            for d in submission_documents
        ),
        key=lambda d: d["clause_text"],
    )
    assert actual_submission == sorted(EXPECTED["submission_documents"], key=lambda d: d["clause_text"])
    assert "CMMI" not in " ".join(d.clause_text for d in submission_documents)  # invented item dropped
    assert analysis.run_stats["dropped_unverified"] == EXPECTED["dropped_unverified"]
    assert analysis.run_stats["documents"][0]["dropped_duplicates"] == EXPECTED["dropped_duplicates"]


def test_every_stored_fact_cites_a_page_that_contains_its_quote(db_session, sample_tender, storage_backend):
    document = _upload_rfp(db_session, sample_tender)
    tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())

    requirements, eligibility = _facts(db_session, sample_tender.id)
    submission_documents = db_session.query(TenderSubmissionDocument).filter_by(tender_id=sample_tender.id).all()
    assert requirements and eligibility and submission_documents
    for fact, quote in [
        *((r, r.requirement_text) for r in requirements),
        *((e, e.criterion_text) for e in eligibility),
        *((d, d.clause_text) for d in submission_documents),
    ]:
        assert fact.document_id == document.id
        assert 1 <= fact.page_number <= document.page_count
        assert quote_on_page(quote, document.extracted_pages[fact.page_number - 1])
        assert fact.generated_by_model == "fake-model"


def test_summary_is_stored_with_fact_refs_pointing_at_stored_rows(db_session, sample_tender, storage_backend):
    _upload_rfp(db_session, sample_tender)
    analysis = tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())

    summary = analysis.summary
    assert summary["project"] == "Integrated Citizen Services Portal"
    requirements, eligibility = _facts(db_session, sample_tender.id)
    stored_ids = {str(r.id) for r in requirements} | {str(e.id) for e in eligibility}
    assert set(summary["fact_refs"].values()) == stored_ids
    assert len(summary["fact_refs"]) == 12
    assert analysis.generated_by_model == "fake-model"
    assert analysis.documents_analysed == 1
    assert analysis.run_stats["llm_calls"] == 2  # one extraction call + one summary call


def test_summary_prompt_receives_facts_not_raw_document_text(db_session, sample_tender, storage_backend):
    _upload_rfp(db_session, sample_tender)
    llm = FakeLLMClient()
    tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=llm)

    summary_prompt = llm.calls[-1]["user"]
    assert '"id": "E1"' in summary_prompt
    assert "=== PAGE" not in summary_prompt
    assert "AWS GovCloud" not in summary_prompt  # a dropped fact never reaches the summary


def test_ai_categories_added_with_confidence_and_manual_ones_preserved(db_session, sample_tender, storage_backend):
    sample_tender.categories.append(TenderCategory(category=TenderCategoryEnum.SOFTWARE_DEVELOPMENT))
    db_session.commit()
    _upload_rfp(db_session, sample_tender)

    tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())
    db_session.refresh(sample_tender)

    by_category = {c.category: c.confidence for c in sample_tender.categories}
    assert by_category == {
        TenderCategoryEnum.SOFTWARE_DEVELOPMENT: None,  # manual row kept, AI duplicate not added
        TenderCategoryEnum.WEB_MOBILE_DEVELOPMENT: Decimal("0.90"),
    }


def test_rerun_replaces_facts_and_ai_categories_instead_of_duplicating(db_session, sample_tender, storage_backend):
    _upload_rfp(db_session, sample_tender)
    tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())
    tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())

    requirements, eligibility = _facts(db_session, sample_tender.id)
    assert (len(requirements), len(eligibility)) == (7, 5)
    db_session.refresh(sample_tender)
    assert len(sample_tender.categories) == 2


def test_failed_run_keeps_previous_facts_and_records_error(db_session, sample_tender, storage_backend):
    _upload_rfp(db_session, sample_tender)
    tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())

    # Extraction succeeds, then the summary call (call 2) fails.
    analysis = tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient(fail_on_call=2))

    assert analysis.status == AnalysisStatus.FAILED
    assert "simulated provider outage" in analysis.error
    assert analysis.finished_at is not None
    requirements, eligibility = _facts(db_session, sample_tender.id)
    assert (len(requirements), len(eligibility)) == (7, 5)
    assert analysis.summary["project"] == "Integrated Citizen Services Portal"  # previous summary intact


def test_tender_without_documents_fails_with_clear_reason(db_session, sample_tender, storage_backend):
    analysis = tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())
    assert analysis.status == AnalysisStatus.FAILED
    assert "upload and process at least one tender document" in analysis.error


def test_unreadable_document_is_named_in_the_failure(db_session, sample_tender, storage_backend):
    data = (FIXTURES / "documents" / "sample_scanned.pdf").read_bytes()  # OCR unavailable here -> no text
    document_processing_service.upload_document(db_session, sample_tender.id, "scan.pdf", data, DocumentType.NIT)

    analysis = tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())

    assert analysis.status == AnalysisStatus.FAILED
    assert "scan.pdf" in analysis.error


def test_document_processed_before_page_split_is_reprocessed(db_session, sample_tender, storage_backend):
    """Simulates a document processed by the Sprint 3 code (before
    migration 0005): text present, extracted_pages null."""
    document = _upload_rfp(db_session, sample_tender)
    document.extracted_pages = None
    db_session.commit()

    analysis = tender_intelligence_service.analyse_tender(db_session, sample_tender, llm=FakeLLMClient())

    assert analysis.status == AnalysisStatus.DONE
    db_session.refresh(document)
    assert len(document.extracted_pages) == 4


def test_unconfigured_provider_fails_run_with_configuration_message(
    db_session, sample_tender, storage_backend, monkeypatch
):
    _upload_rfp(db_session, sample_tender)
    monkeypatch.setattr(get_settings(), "llm_provider", "anthropic")
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")

    analysis = tender_intelligence_service.analyse_tender(db_session, sample_tender)

    assert analysis.status == AnalysisStatus.FAILED
    assert "ANTHROPIC_API_KEY is not set" in analysis.error
