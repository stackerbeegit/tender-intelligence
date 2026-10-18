import uuid
from pathlib import Path

import pytest

from tests.support.fake_llm import FakeLLMClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "documents"


def _register_and_login(client, email, role_name):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": "Test User", "role_name": role_name},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


@pytest.fixture()
def fake_llm(monkeypatch) -> FakeLLMClient:
    llm = FakeLLMClient()
    monkeypatch.setattr("app.services.tender_intelligence_service.get_llm_client", lambda: llm)
    return llm


def _upload_rfp(client, tender_id, headers):
    with open(FIXTURES_DIR / "sample_rfp.pdf", "rb") as f:
        response = client.post(
            f"/api/v1/tenders/{tender_id}/documents",
            headers=headers,
            files={"file": ("RFP.pdf", f, "application/pdf")},
            data={"document_type": "rfp"},
        )
    assert response.status_code == 201
    return response.json()


def test_analysis_is_empty_before_first_run(client, sample_tender):
    headers = _register_and_login(client, "viewer-an@stackerbee.com", "viewer")
    response = client.get(f"/api/v1/tenders/{sample_tender.id}/analysis", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "tender_id": str(sample_tender.id),
        "analysis": None,
        "requirements": [],
        "eligibility": [],
    }


def test_run_analysis_returns_cited_facts_and_summary(client, sample_tender, storage_backend, fake_llm):
    headers = _register_and_login(client, "tech-an@stackerbee.com", "technical")
    document = _upload_rfp(client, sample_tender.id, headers)

    response = client.post(f"/api/v1/tenders/{sample_tender.id}/analysis", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["status"] == "done"
    assert body["analysis"]["summary"]["project"] == "Integrated Citizen Services Portal"
    assert len(body["requirements"]) == 7
    assert len(body["eligibility"]) == 5
    for fact in body["requirements"] + body["eligibility"]:
        assert fact["citation"]["document_id"] == document["id"]
        assert fact["citation"]["file_name"] == "RFP.pdf"
        assert 1 <= fact["citation"]["page_number"] <= 3

    turnover = next(e for e in body["eligibility"] if e["criterion_type"] == "turnover")
    assert turnover["extracted_value"]["amount_inr"] == 100000000
    assert turnover["citation"]["page_number"] == 3

    # GET returns the same stored result without calling the model again.
    calls_before = len(fake_llm.calls)
    again = client.get(f"/api/v1/tenders/{sample_tender.id}/analysis", headers=headers).json()
    assert again["requirements"] == body["requirements"]
    assert len(fake_llm.calls) == calls_before


def test_eligibility_endpoint_returns_only_eligibility_facts(client, sample_tender, storage_backend, fake_llm):
    headers = _register_and_login(client, "bd-an@stackerbee.com", "bd_manager")
    _upload_rfp(client, sample_tender.id, headers)
    client.post(f"/api/v1/tenders/{sample_tender.id}/analysis", headers=headers)

    response = client.get(f"/api/v1/tenders/{sample_tender.id}/eligibility", headers=headers)

    assert response.status_code == 200
    assert {e["criterion_type"] for e in response.json()} == {
        "turnover",
        "similar_projects",
        "certification",
        "emd",
        "msme_startup",
    }


def test_failed_run_is_reported_in_body_not_as_server_error(client, sample_tender, storage_backend, fake_llm):
    headers = _register_and_login(client, "admin-an@stackerbee.com", "admin")
    response = client.post(f"/api/v1/tenders/{sample_tender.id}/analysis", headers=headers)  # no documents
    assert response.status_code == 200
    assert response.json()["analysis"]["status"] == "failed"
    assert "upload and process" in response.json()["analysis"]["error"]


def test_viewer_cannot_run_analysis(client, sample_tender):
    headers = _register_and_login(client, "viewer-an2@stackerbee.com", "viewer")
    assert client.post(f"/api/v1/tenders/{sample_tender.id}/analysis", headers=headers).status_code == 403


def test_analysis_requires_authentication(client, sample_tender):
    assert client.get(f"/api/v1/tenders/{sample_tender.id}/analysis").status_code == 401


def test_unknown_tender_is_404(client):
    headers = _register_and_login(client, "viewer-an3@stackerbee.com", "viewer")
    assert client.get(f"/api/v1/tenders/{uuid.uuid4()}/analysis", headers=headers).status_code == 404
