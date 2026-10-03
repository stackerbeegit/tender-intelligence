def _register(client, email="user@stackerbee.com", password="StrongPass123", role_name="viewer"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User", "role_name": role_name},
    )


def test_register_creates_user(client):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@stackerbee.com"
    assert body["role"]["name"] == "viewer"
    assert "hashed_password" not in body  # never leak the hash


def test_register_duplicate_email_rejected(client):
    _register(client)
    response = _register(client)
    assert response.status_code == 409


def test_register_unknown_role_rejected(client):
    response = _register(client, role_name="does-not-exist")
    assert response.status_code == 400


def test_login_success_returns_tokens(client):
    _register(client, email="login@stackerbee.com", password="StrongPass123")
    response = client.post(
        "/api/v1/auth/login", json={"email": "login@stackerbee.com", "password": "StrongPass123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_wrong_password_rejected(client):
    _register(client, email="wrongpw@stackerbee.com", password="StrongPass123")
    response = client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@stackerbee.com", "password": "nope"}
    )
    assert response.status_code == 401


def test_login_unknown_user_rejected(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@stackerbee.com", "password": "whatever123"}
    )
    assert response.status_code == 401


def test_me_requires_bearer_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client):
    _register(client, email="me@stackerbee.com", password="StrongPass123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "me@stackerbee.com", "password": "StrongPass123"}
    ).json()
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@stackerbee.com"


def test_refresh_issues_new_access_token(client):
    _register(client, email="refresh@stackerbee.com", password="StrongPass123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "refresh@stackerbee.com", "password": "StrongPass123"}
    ).json()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_rejects_access_token_used_as_refresh(client):
    _register(client, email="badrefresh@stackerbee.com", password="StrongPass123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "badrefresh@stackerbee.com", "password": "StrongPass123"}
    ).json()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": login["access_token"]})
    assert response.status_code == 401


def test_users_list_requires_admin_role(client):
    _register(client, email="plainuser@stackerbee.com", password="StrongPass123", role_name="viewer")
    login = client.post(
        "/api/v1/auth/login", json={"email": "plainuser@stackerbee.com", "password": "StrongPass123"}
    ).json()
    response = client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {login['access_token']}"}
    )
    assert response.status_code == 403


def test_users_list_allowed_for_admin(client):
    _register(client, email="admin@stackerbee.com", password="StrongPass123", role_name="admin")
    login = client.post(
        "/api/v1/auth/login", json={"email": "admin@stackerbee.com", "password": "StrongPass123"}
    ).json()
    response = client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {login['access_token']}"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_dashboard_summary_requires_auth_and_labels_placeholder_data(client):
    unauthenticated = client.get("/api/v1/dashboard/summary")
    assert unauthenticated.status_code == 401

    _register(client, email="dash@stackerbee.com", password="StrongPass123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "dash@stackerbee.com", "password": "StrongPass123"}
    ).json()
    response = client.get(
        "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {login['access_token']}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["new_tenders"] == 0
    assert "placeholder" in body["note"].lower()
