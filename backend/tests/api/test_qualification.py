"""
Qualification API end to end: facts stored the way Sprint 4 stores them,
a profile created through the API, and results read back with their
evidence. The last test runs the real analysis pipeline (scripted model)
on the representative RFP and checks qualification follows automatically.
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.matching.relevance import relevance_score
from app.models.enums import DocumentType, EligibilityCriterionType, ExtractionStatus
from app.models.enums import TenderCategory as TenderCategoryEnum
from app.models.tender_category import TenderCategory
from app.models.tender_document import TenderDocument
from app.models.tender_eligibility import TenderEligibility
from tests.support.fake_llm import FakeLLMClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "documents"
TURNOVER_CLAUSE = (
    "The bidder must have an average annual turnover of at least Rs. 10 Crore during the last three financial years."
)


def _register_and_login(client, email, role_name):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": "Test User", "role_name": role_name},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


def _profile(turnover_cr: float) -> dict:
    return {
        "company_name": "Stackerbee Technologies",
        "msme_registered": True,
        "turnover_by_year": [
            {"financial_year": fy, "amount_inr": turnover_cr * 10_000_000} for fy in ("2024-25", "2023-24", "2022-23")
        ],
        "employee_count": 120,
        "locations": ["Punjab"],
        "certifications": ["ISO 27001"],
    }


@pytest.fixture()
def tender_with_turnover_fact(db_session, sample_tender):
    document = TenderDocument(
        tender_id=sample_tender.id,
        file_name="RFP.pdf",
        document_type=DocumentType.RFP,
        extraction_status=ExtractionStatus.DONE,
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        TenderEligibility(
            tender_id=sample_tender.id,
            document_id=document.id,
            criterion_type=EligibilityCriterionType.TURNOVER,
            summary="Average turnover ₹10 Cr over 3 years",
            criterion_text=TURNOVER_CLAUSE,
            extracted_value={"amount_inr": 100000000, "period_years": 3, "is_average": True},
            page_number=3,
            generated_by_model="test-model",
        )
    )
    db_session.add(TenderCategory(tender_id=sample_tender.id, category=TenderCategoryEnum.SOFTWARE_DEVELOPMENT))
    sample_tender.closing_date = datetime.now(timezone.utc) + timedelta(days=20)
    db_session.commit()
    return sample_tender


def test_nothing_is_computed_before_a_profile_exists(client, tender_with_turnover_fact):
    headers = _register_and_login(client, "bd-q@stackerbee.com", "bd_manager")
    url = f"/api/v1/tenders/{tender_with_turnover_fact.id}/qualification"

    response = client.get(url, headers=headers)
    assert response.json() == {
        "tender_id": str(tender_with_turnover_fact.id),
        "profile_configured": False,
        "is_stale": False,
        "qualification": None,
    }
    assert client.post(url, headers=headers).status_code == 409


def test_compute_stores_an_evidence_linked_result(client, tender_with_turnover_fact):
    admin = _register_and_login(client, "admin-q@stackerbee.com", "admin")
    client.put("/api/v1/profile", headers=admin, json=_profile(turnover_cr=12))
    url = f"/api/v1/tenders/{tender_with_turnover_fact.id}/qualification"

    body = client.post(url, headers=admin).json()

    result = body["qualification"]
    assert body["profile_configured"] is True and body["is_stale"] is False
    assert result["eligibility_status"] == "ELIGIBLE"
    [reason] = result["reasons"]
    assert reason["outcome"] == "MET" and reason["polarity"] == "support"
    assert reason["evidence"]["quote"] == TURNOVER_CLAUSE
    assert reason["evidence"]["page_number"] == 3
    assert reason["evidence"]["file_name"] == "RFP.pdf"
    assert result["relevance_score"] == relevance_score(result["relevance_factors"])
    assert set(result["relevance_factors"]) == {
        "technical", "eligibility", "experience", "manpower", "commercial", "location", "msme", "deadline",
    }

    # GET returns the stored row as-is.
    assert client.get(url, headers=admin).json() == body


def test_profile_change_marks_the_result_stale_until_recomputed(client, tender_with_turnover_fact):
    admin = _register_and_login(client, "admin-q2@stackerbee.com", "admin")
    client.put("/api/v1/profile", headers=admin, json=_profile(turnover_cr=12))
    url = f"/api/v1/tenders/{tender_with_turnover_fact.id}/qualification"
    client.post(url, headers=admin)

    client.put("/api/v1/profile", headers=admin, json=_profile(turnover_cr=4))
    stale = client.get(url, headers=admin).json()
    assert stale["is_stale"] is True
    assert stale["qualification"]["eligibility_status"] == "ELIGIBLE"  # not silently recomputed on read

    fresh = client.post(url, headers=admin).json()
    assert fresh["is_stale"] is False
    assert fresh["qualification"]["eligibility_status"] == "NOT_ELIGIBLE"
    assert fresh["qualification"]["risks"][0]["severity"] == "high"
    assert fresh["qualification"]["risks"][0]["page"] == 3


def test_viewer_can_read_but_not_compute(client, tender_with_turnover_fact):
    viewer = _register_and_login(client, "viewer-q@stackerbee.com", "viewer")
    url = f"/api/v1/tenders/{tender_with_turnover_fact.id}/qualification"
    assert client.get(url, headers=viewer).status_code == 200
    assert client.post(url, headers=viewer).status_code == 403


def test_qualification_requires_authentication_and_a_real_tender(client):
    assert client.get(f"/api/v1/tenders/{uuid.uuid4()}/qualification").status_code == 401
    headers = _register_and_login(client, "viewer-q2@stackerbee.com", "viewer")
    assert client.get(f"/api/v1/tenders/{uuid.uuid4()}/qualification", headers=headers).status_code == 404


def test_successful_analysis_recomputes_qualification(client, sample_tender, storage_backend, monkeypatch):
    llm = FakeLLMClient()
    monkeypatch.setattr("app.services.tender_intelligence_service.get_llm_client", lambda: llm)
    admin = _register_and_login(client, "admin-q3@stackerbee.com", "admin")
    client.put("/api/v1/profile", headers=admin, json=_profile(turnover_cr=12))
    with open(FIXTURES_DIR / "sample_rfp.pdf", "rb") as f:
        client.post(
            f"/api/v1/tenders/{sample_tender.id}/documents",
            headers=admin,
            files={"file": ("RFP.pdf", f, "application/pdf")},
            data={"document_type": "rfp"},
        )

    analysis = client.post(f"/api/v1/tenders/{sample_tender.id}/analysis", headers=admin).json()
    assert analysis["analysis"]["status"] == "done"

    body = client.get(f"/api/v1/tenders/{sample_tender.id}/qualification", headers=admin).json()
    result = body["qualification"]
    assert body["is_stale"] is False
    eligibility_ids = {e["id"] for e in analysis["eligibility"]}
    assert {r["evidence"]["fact_id"] for r in result["reasons"]} == eligibility_ids
    # No past projects recorded, so the similar-projects clause can't be confirmed either way.
    similar = next(r for r in result["reasons"] if r["criterion_type"] == "similar_projects")
    assert similar["outcome"] == "UNKNOWN"
    assert result["eligibility_status"] == "UNCERTAIN"
