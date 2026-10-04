def _register_and_login(client, email, role_name):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": "Test User", "role_name": role_name},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


def test_list_sources_includes_seeded_manual_source(client):
    headers = _register_and_login(client, "admin1@stackerbee.com", "admin")
    response = client.get("/api/v1/sources", headers=headers)
    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert "Manual Entry" in names


def test_list_sources_forbidden_for_viewer(client):
    headers = _register_and_login(client, "viewer1@stackerbee.com", "viewer")
    response = client.get("/api/v1/sources", headers=headers)
    assert response.status_code == 403


def test_create_source_requires_admin(client):
    headers = _register_and_login(client, "tech1@stackerbee.com", "technical")
    response = client.post(
        "/api/v1/sources",
        headers=headers,
        json={"name": "Test GeM", "source_type": "gem"},
    )
    assert response.status_code == 403


def test_create_source_as_admin(client):
    headers = _register_and_login(client, "admin2@stackerbee.com", "admin")
    response = client.post(
        "/api/v1/sources",
        headers=headers,
        json={"name": "Test GeM Portal", "source_type": "gem", "url": "https://example.gov.in"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["crawler_enabled"] is False
    assert body["status"] == "disabled"


def test_enabling_crawler_without_terms_notes_is_rejected(client):
    headers = _register_and_login(client, "admin3@stackerbee.com", "admin")
    created = client.post(
        "/api/v1/sources", headers=headers, json={"name": "No Notes Portal", "source_type": "state"}
    ).json()

    response = client.patch(
        f"/api/v1/sources/{created['id']}", headers=headers, json={"crawler_enabled": True}
    )
    assert response.status_code == 400
    assert "terms_access_notes" in response.json()["detail"]


def test_enabling_crawler_with_terms_notes_succeeds(client):
    headers = _register_and_login(client, "admin4@stackerbee.com", "admin")
    created = client.post(
        "/api/v1/sources",
        headers=headers,
        json={
            "name": "Documented Portal",
            "source_type": "state",
            "terms_access_notes": "Checked robots.txt and ToS on 2026-10-04; automated access permitted.",
        },
    ).json()

    response = client.patch(
        f"/api/v1/sources/{created['id']}", headers=headers, json={"crawler_enabled": True}
    )
    assert response.status_code == 200
    assert response.json()["crawler_enabled"] is True
