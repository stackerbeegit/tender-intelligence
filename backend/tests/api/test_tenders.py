def _register_and_login(client, email, role_name):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": "Test User", "role_name": role_name},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


def _manual_tender_payload(**overrides):
    payload = {
        "title": "Supply of laptops and networking equipment",
        "organisation_name": "Directorate of Example Services",
        "tender_value": "2500000.00",
        "published_date": "2026-01-10",
        "closing_date": "2026-02-10T17:00:00Z",
        "locations": [{"state": "Karnataka", "city": "Bengaluru"}],
        "categories": ["networking_infrastructure"],
        "documents": [{"file_name": "NIT.pdf", "source_url": "https://example.gov.in/nit.pdf"}],
    }
    payload.update(overrides)
    return payload


def test_manual_create_requires_appropriate_role(client):
    headers = _register_and_login(client, "viewer2@stackerbee.com", "viewer")
    response = client.post("/api/v1/tenders/manual", headers=headers, json=_manual_tender_payload())
    assert response.status_code == 403


def test_manual_create_succeeds_for_bd_manager(client):
    headers = _register_and_login(client, "bd1@stackerbee.com", "bd_manager")
    response = client.post("/api/v1/tenders/manual", headers=headers, json=_manual_tender_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Supply of laptops and networking equipment"
    assert body["organisation"]["name"] == "Directorate of Example Services"
    assert len(body["locations"]) == 1
    assert len(body["documents"]) == 1
    assert body["categories"][0]["category"] == "networking_infrastructure"
    assert body["categories"][0]["confidence"] is None  # fact, not an AI interpretation


def test_manual_create_twice_does_not_duplicate(client):
    headers = _register_and_login(client, "bd2@stackerbee.com", "bd_manager")
    first = client.post("/api/v1/tenders/manual", headers=headers, json=_manual_tender_payload()).json()
    second = client.post("/api/v1/tenders/manual", headers=headers, json=_manual_tender_payload()).json()

    assert first["id"] == second["id"]

    listing = client.get("/api/v1/tenders", headers=headers).json()
    matching = [t for t in listing["items"] if t["id"] == first["id"]]
    assert len(matching) == 1


def test_manual_create_with_extended_deadline_adds_history(client):
    headers = _register_and_login(client, "bd3@stackerbee.com", "bd_manager")
    created = client.post("/api/v1/tenders/manual", headers=headers, json=_manual_tender_payload()).json()
    assert len(created["deadlines"]) == 1

    updated = client.post(
        "/api/v1/tenders/manual",
        headers=headers,
        json=_manual_tender_payload(closing_date="2026-02-20T17:00:00Z"),
    ).json()

    assert updated["id"] == created["id"]
    assert updated["status"] == "corrigendum"
    assert len(updated["deadlines"]) == 2
    assert updated["deadlines"][-1]["deadline_type"] == "extended"


def test_tender_detail_not_found(client):
    headers = _register_and_login(client, "viewer3@stackerbee.com", "viewer")
    response = client.get("/api/v1/tenders/00000000-0000-0000-0000-000000000000", headers=headers)
    assert response.status_code == 404


def test_list_tenders_filters_by_keyword(client):
    headers = _register_and_login(client, "bd4@stackerbee.com", "bd_manager")
    client.post(
        "/api/v1/tenders/manual", headers=headers, json=_manual_tender_payload(title="Cybersecurity audit services")
    )
    client.post(
        "/api/v1/tenders/manual",
        headers=headers,
        json=_manual_tender_payload(title="ERP implementation project", organisation_name="Other Dept"),
    )

    response = client.get("/api/v1/tenders", headers=headers, params={"keyword": "cybersecurity"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert "Cybersecurity" in body["items"][0]["title"]


def test_list_tenders_filters_by_value_range(client):
    headers = _register_and_login(client, "bd5@stackerbee.com", "bd_manager")
    client.post(
        "/api/v1/tenders/manual",
        headers=headers,
        json=_manual_tender_payload(title="Small project", tender_value="10000.00"),
    )
    client.post(
        "/api/v1/tenders/manual",
        headers=headers,
        json=_manual_tender_payload(title="Large project", tender_value="9000000.00"),
    )

    response = client.get("/api/v1/tenders", headers=headers, params={"min_value": "1000000"})
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Large project"
