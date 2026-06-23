from app.core.auth import create_access_token, decode_access_token
from tests.conftest import DEFAULT_PASSWORD, IDS, login


def test_token_generation_and_validation():
    token = create_access_token(
        user_id=IDS["user_anurag"],
        email="anurag@prosohm.com",
    )
    payload = decode_access_token(token)
    assert payload.sub == IDS["user_anurag"]
    assert payload.email == "anurag@prosohm.com"


def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "anurag@prosohm.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_failure(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "anurag@prosohm.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_current_user_endpoint(client):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "binil@prosohm.com"
    assert body["role_name"] == "Designer"


def test_protected_endpoint_rejects_anonymous(client):
    assert client.get("/api/v1/dashboard/summary").status_code == 401


def test_role_authorization_for_users(client):
    designer_headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/users", headers=designer_headers)
    assert response.status_code == 403

    admin_headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/users", headers=admin_headers)
    assert response.status_code == 200


def test_token_validation(client):
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
