import pytest

from app.core.exceptions import LLMResponseError
from app.intelligence.extraction.extractor import batch_pages, extract_document
from app.models.enums import EligibilityCriterionType, RequirementCategory
from tests.support.fake_llm import FakeLLMClient

RFP_PAGES = [
    "Request for Proposal\nThe contract period shall be 36 months from the date of Go-Live, including \n"
    "12 months of warranty support.",
    "The solution shall be developed using an open-source technology stack with \nPostgreSQL as the database.\n"
    "The portal shall integrate with the State Payment Gateway and DigiLocker \nthrough secure REST APIs.\n"
    "The bidder shall provide 24x7 helpdesk support with a maximum resolution \ntime of 4 hours for critical incidents.\n"
    "The application must undergo a security audit by a CERT-In empanelled \nauditor before Go-Live.\n"
    "Project Manager - 1 resource with minimum 10 years of experience in IT \nproject delivery.\n"
    "Java Developer - 4 resources with minimum 5 years of experience each.",
    "The bidder must have an average annual turnover of at least Rs. 10 Crore \nduring the last three financial years.\n"
    "The bidder must have successfully completed at least 3 similar projects, \neach of value not less than Rs. 2 "
    "Crore, for Government or PSU clients.\nThe bidder must hold a valid ISO 27001 certification.\n"
    "Earnest Money Deposit of Rs. 5,00,000 shall be submitted along with the \nbid.\n"
    "Micro and Small Enterprises registered with NSIC or Udyam are exempted \nfrom payment of EMD as per the "
    "Public Procurement Policy for MSEs Order,\n2012.",
]


# --- batch_pages ---


def test_batch_pages_groups_pages_up_to_limit_and_keeps_page_numbers():
    batches = batch_pages(["a" * 40, "b" * 40, "c" * 40], max_chars=100)
    assert [[n for n, _ in b] for b in batches] == [[1, 2], [3]]


def test_batch_pages_skips_empty_pages_without_renumbering():
    batches = batch_pages(["first", "   ", "third"], max_chars=100)
    assert [[n for n, _ in b] for b in batches] == [[1, 3]]


def test_batch_pages_splits_oversized_page_and_every_piece_keeps_its_page_number():
    batches = batch_pages(["small", "x" * 250, "tail"], max_chars=100)
    assert [[n for n, _ in b] for b in batches] == [[1], [2], [2], [2], [3]]
    assert "".join(text for b in batches[1:4] for _, text in b) == "x" * 250


# --- extract_document ---


def _extract(llm, max_chars=24000):
    return extract_document(
        llm, document_id="doc-1", file_name="RFP.pdf", tender_title="ICSP", pages=RFP_PAGES, max_chars_per_call=max_chars
    )


def test_verified_items_are_kept_and_bad_items_dropped():
    result = _extract(FakeLLMClient())

    assert len(result.requirements) == 7
    assert len(result.eligibility) == 5
    assert result.dropped_unverified == 2  # invented AWS clause + wrong-page citation
    assert result.dropped_duplicates == 1
    assert {d["quote"][:30] for d in result.dropped_examples} == {
        "The solution shall be hosted o",
        "Java Developer - 4 resources w",
    }
    quotes = [r.quote for r in result.requirements]
    assert not any("AWS" in q for q in quotes)
    assert result.llm_calls == 1


def test_every_kept_fact_quote_is_on_its_cited_page():
    from app.intelligence.extraction.citations import quote_on_page

    result = _extract(FakeLLMClient())
    for fact in [*result.requirements, *result.eligibility]:
        assert quote_on_page(fact.quote, RFP_PAGES[fact.page_number - 1])


def test_structured_fields_are_typed_and_nulls_dropped():
    result = _extract(FakeLLMClient())
    pm = next(r for r in result.requirements if r.details.get("role") == "Project Manager")
    assert pm.category == RequirementCategory.MANPOWER
    assert pm.details == {"role": "Project Manager", "resource_count": 1, "min_experience_years": 10}

    turnover = next(e for e in result.eligibility if e.criterion_type == EligibilityCriterionType.TURNOVER)
    assert turnover.value == {"amount_inr": 100000000, "period_years": 3, "is_average": True}


def test_small_call_budget_makes_one_call_per_page_with_same_result():
    result = _extract(FakeLLMClient(), max_chars=len(max(RFP_PAGES, key=len)))
    assert result.llm_calls == 3
    assert len(result.requirements) == 7
    assert len(result.eligibility) == 5


def test_each_call_receives_only_its_own_pages():
    llm = FakeLLMClient()
    _extract(llm, max_chars=len(max(RFP_PAGES, key=len)))
    for index, call in enumerate(llm.calls, start=1):
        assert f"=== PAGE {index} ===" in call["user"]
        assert call["user"].count("=== PAGE") == 1


def test_provider_failure_propagates_rather_than_returning_partial_result():
    with pytest.raises(LLMResponseError):
        _extract(FakeLLMClient(fail_on_call=2), max_chars=len(max(RFP_PAGES, key=len)))


def test_citation_outside_document_page_range_is_dropped():
    responses = {
        "requirements": [
            {
                "category": "other",
                "summary": "x",
                "quote": "Java Developer - 4 resources with minimum 5 years of experience each.",
                "page_number": 9,
                "_seen_on_page": 2,
                "details": {},
            }
        ],
        "eligibility": [],
    }
    result = _extract(FakeLLMClient(responses))
    assert result.requirements == []
    assert result.dropped_unverified == 1
