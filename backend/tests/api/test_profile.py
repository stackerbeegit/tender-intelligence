import uuid

from app.models.audit_log import AuditLog


def _register_and_login(client, email, role_name):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": "Test User", "role_name": role_name},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


PROFILE = {
    "company_name": "Stackerbee Technologies",
    "msme_registered": True,
    "msme_certificate_ref": "UDYAM-PB-00-0000000",
    "turnover_by_year": [
        {"financial_year": "2023-24", "amount_inr": 120000000},
        {"financial_year": "2024-25", "amount_inr": 140000000},
    ],
    "net_worth_inr": "60000000.00",
    "years_in_business": 9,
    "employee_count": 120,
    "locations": ["Punjab", " punjab ", "Haryana", ""],
    "certifications": ["ISO 27001"],
}


def test_profile_is_empty_until_an_admin_creates_it(client):
    headers = _register_and_login(client, "viewer-p@stackerbee.com", "viewer")
    response = client.get("/api/v1/profile", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"profile": None, "capabilities": [], "experience": []}


def test_admin_creates_then_updates_the_single_profile(client, db_session):
    headers = _register_and_login(client, "admin-p@stackerbee.com", "admin")

    created = client.put("/api/v1/profile", headers=headers, json=PROFILE)
    assert created.status_code == 200
    body = created.json()
    assert body["locations"] == ["Punjab", "Haryana"]  # trimmed, de-duplicated, blanks dropped
    assert [y["financial_year"] for y in body["turnover_by_year"]] == ["2024-25", "2023-24"]  # newest first

    updated = client.put("/api/v1/profile", headers=headers, json={**PROFILE, "employee_count": 150})
    assert updated.json()["id"] == body["id"]
    assert updated.json()["employee_count"] == 150

    actions = [a.action for a in db_session.query(AuditLog).order_by(AuditLog.created_at)]
    assert actions[-2:] == ["profile.created", "profile.updated"]


def test_duplicate_financial_years_are_rejected(client):
    headers = _register_and_login(client, "admin-p2@stackerbee.com", "admin")
    payload = {**PROFILE, "turnover_by_year": [{"financial_year": "2024-25", "amount_inr": 1}] * 2}
    assert client.put("/api/v1/profile", headers=headers, json=payload).status_code == 422


def test_only_admins_can_edit_the_profile(client):
    for role in ("bd_manager", "technical", "viewer"):
        headers = _register_and_login(client, f"{role}-p@stackerbee.com", role)
        assert client.put("/api/v1/profile", headers=headers, json=PROFILE).status_code == 403
        assert client.post(
            "/api/v1/profile/capabilities", headers=headers, json={"capability": "cybersecurity"}
        ).status_code == 403


def test_capabilities_need_a_profile_and_are_unique(client):
    headers = _register_and_login(client, "admin-p3@stackerbee.com", "admin")
    capability = {"capability": "software_development", "technologies": ["Python", "React"]}

    assert client.post("/api/v1/profile/capabilities", headers=headers, json=capability).status_code == 409

    client.put("/api/v1/profile", headers=headers, json=PROFILE)
    created = client.post("/api/v1/profile/capabilities", headers=headers, json=capability)
    assert created.status_code == 201
    assert client.post("/api/v1/profile/capabilities", headers=headers, json=capability).status_code == 409

    cap_id = created.json()["id"]
    patched = client.patch(
        f"/api/v1/profile/capabilities/{cap_id}", headers=headers, json={"technologies": ["Python", "Django"]}
    )
    assert patched.json()["technologies"] == ["Python", "Django"]
    assert client.delete(f"/api/v1/profile/capabilities/{cap_id}", headers=headers).status_code == 204
    assert client.get("/api/v1/profile", headers=headers).json()["capabilities"] == []


def test_experience_crud(client):
    headers = _register_and_login(client, "admin-p4@stackerbee.com", "admin")
    client.put("/api/v1/profile", headers=headers, json=PROFILE)

    created = client.post(
        "/api/v1/profile/experience",
        headers=headers,
        json={
            "project_name": "Citizen services portal",
            "client_name": "Department of Governance Reforms",
            "customer_type": "government",
            "capability": "software_development",
            "technologies": ["Java", "PostgreSQL"],
            "project_value_inr": "30000000",
            "year": 2024,
        },
    )
    assert created.status_code == 201
    exp_id = created.json()["id"]

    patched = client.patch(f"/api/v1/profile/experience/{exp_id}", headers=headers, json={"year": 2025})
    assert patched.json()["year"] == 2025
    assert patched.json()["project_name"] == "Citizen services portal"

    listed = client.get("/api/v1/profile", headers=headers).json()["experience"]
    assert [e["id"] for e in listed] == [exp_id]

    assert client.delete(f"/api/v1/profile/experience/{exp_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/profile/experience/{exp_id}", headers=headers).status_code == 404


def test_unknown_capability_is_404(client):
    headers = _register_and_login(client, "admin-p5@stackerbee.com", "admin")
    response = client.patch(f"/api/v1/profile/capabilities/{uuid.uuid4()}", headers=headers, json={})
    assert response.status_code == 404
