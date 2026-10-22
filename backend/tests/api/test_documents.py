from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "documents"


def _register_and_login(client, email, role_name):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": "Test User", "role_name": role_name},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


def test_upload_requires_appropriate_role(client, sample_tender, storage_backend):
    headers = _register_and_login(client, "viewer-doc@stackerbee.com", "viewer")
    with open(FIXTURES_DIR / "sample.xlsx", "rb") as f:
        response = client.post(
            f"/api/v1/tenders/{sample_tender.id}/documents",
            headers=headers,
            files={"file": ("sample.xlsx", f, "application/octet-stream")},
            data={"document_type": "boq"},
        )
    assert response.status_code == 403


def test_upload_process_and_download_round_trip(client, sample_tender, storage_backend):
    headers = _register_and_login(client, "bdmgr-doc@stackerbee.com", "bd_manager")

    with open(FIXTURES_DIR / "sample_native.pdf", "rb") as f:
        upload_response = client.post(
            f"/api/v1/tenders/{sample_tender.id}/documents",
            headers=headers,
            files={"file": ("sample_native.pdf", f, "application/pdf")},
            data={"document_type": "nit"},
        )
    assert upload_response.status_code == 201
    document = upload_response.json()
    assert document["extraction_status"] == "pending"
    assert document["checksum_sha256"] is not None

    process_response = client.post(
        f"/api/v1/tenders/{sample_tender.id}/documents/{document['id']}/process", headers=headers
    )
    assert process_response.status_code == 200
    processed = process_response.json()
    assert processed["extraction_status"] == "done"
    assert "Sample Tender Notice" in processed["extracted_text"]

    detail_response = client.get(f"/api/v1/tenders/{sample_tender.id}/documents/{document['id']}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["extraction_status"] == "done"

    download_response = client.get(
        f"/api/v1/tenders/{sample_tender.id}/documents/{document['id']}/download", headers=headers
    )
    assert download_response.status_code == 200
    assert download_response.content == (FIXTURES_DIR / "sample_native.pdf").read_bytes()
    assert "sample_native.pdf" in download_response.headers["content-disposition"]


def test_download_requires_authentication(client, sample_tender, storage_backend):
    headers = _register_and_login(client, "bdmgr-doc2@stackerbee.com", "bd_manager")
    with open(FIXTURES_DIR / "sample.xlsx", "rb") as f:
        upload_response = client.post(
            f"/api/v1/tenders/{sample_tender.id}/documents",
            headers=headers,
            files={"file": ("sample.xlsx", f, "application/octet-stream")},
            data={"document_type": "boq"},
        )
    document_id = upload_response.json()["id"]

    response = client.get(f"/api/v1/tenders/{sample_tender.id}/documents/{document_id}/download")
    assert response.status_code == 401


def test_document_detail_404_for_mismatched_tender(client, sample_tender, storage_backend):
    headers = _register_and_login(client, "viewer-doc2@stackerbee.com", "viewer")
    response = client.get(
        f"/api/v1/tenders/00000000-0000-0000-0000-000000000000/documents/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert response.status_code == 404


def test_upload_rejects_unsupported_file_type(client, sample_tender, storage_backend):
    headers = _register_and_login(client, "bdmgr-doc3@stackerbee.com", "bd_manager")
    response = client.post(
        f"/api/v1/tenders/{sample_tender.id}/documents",
        headers=headers,
        files={"file": ("notes.txt", b"just plain text", "text/plain")},
        data={"document_type": "other"},
    )
    assert response.status_code == 400


def _crawled_document(db_session, tender):
    """A document as the GeM connector stores it: a portal URL, no file yet."""
    from app.models.enums import DocumentType
    from app.models.tender_document import TenderDocument

    document = TenderDocument(
        tender_id=tender.id,
        file_name="GEM-2026-B-8174923.pdf",
        document_type=DocumentType.NIT,
        source_url="https://bidplus.gem.gov.in/showbidDocument/10051102",
    )
    db_session.add(document)
    db_session.commit()
    return document


def test_downloading_a_crawled_document_fetches_it_from_the_portal_first(
    client, sample_tender, storage_backend, db_session, monkeypatch
):
    pdf = (FIXTURES_DIR / "sample_native.pdf").read_bytes()
    fetched = []
    monkeypatch.setattr(
        "app.document_processing.downloader.download_document", lambda url: fetched.append(url) or pdf
    )
    document = _crawled_document(db_session, sample_tender)
    headers = _register_and_login(client, "viewer-doc3@stackerbee.com", "viewer")
    url = f"/api/v1/tenders/{sample_tender.id}/documents/{document.id}/download"

    first = client.get(url, headers=headers)

    assert first.status_code == 200
    assert first.content == pdf
    assert first.headers["content-type"] == "application/pdf"
    assert fetched == ["https://bidplus.gem.gov.in/showbidDocument/10051102"]
    db_session.refresh(document)
    assert document.storage_path and document.extraction_status.value == "done"

    # Stored now: the second download doesn't go back to the portal.
    assert client.get(url, headers=headers).content == pdf
    assert len(fetched) == 1


def test_a_portal_failure_is_reported_with_its_reason(client, sample_tender, storage_backend, db_session, monkeypatch):
    from app.core.exceptions import DocumentDownloadError

    def fail(url):
        raise DocumentDownloadError(f"Could not download {url}: [SSL: CERTIFICATE_VERIFY_FAILED]")

    monkeypatch.setattr("app.document_processing.downloader.download_document", fail)
    document = _crawled_document(db_session, sample_tender)
    headers = _register_and_login(client, "viewer-doc4@stackerbee.com", "viewer")

    response = client.get(f"/api/v1/tenders/{sample_tender.id}/documents/{document.id}/download", headers=headers)

    assert response.status_code == 502
    assert "CERTIFICATE_VERIFY_FAILED" in response.json()["detail"]
