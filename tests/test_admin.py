import uuid

from tests.conftest import DEFAULT_PASSWORD, IDS, list_items, login


def test_admin_can_list_users(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 200
    assert len(list_items(response)) >= 1


def test_engineering_manager_forbidden_from_admin_users(client):
    headers = login(client, "pm@prosohm.com")
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 403


def test_designer_forbidden_from_admin_users(client):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 403


def test_designer_can_use_lookup_users(client):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/lookups/users", headers=headers)
    assert response.status_code == 200


def test_create_user_and_login(client, production_release):
    headers = login(client, "admin@prosohm.com")
    roles = client.get("/api/v1/roles", headers=headers)
    designer_role = next(r for r in list_items(roles) if r["name"] == "Designer")

    email = f"new.user.{uuid.uuid4().hex[:8]}@prosohm.com"
    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": designer_role["id"],
            "email": email,
            "password": "TempPass@123",
            "first_name": "New",
            "last_name": "User",
            "is_active": True,
            "must_change_password": True,
        },
    )
    assert create.status_code == 201
    user_id = create.json()["id"]
    assert create.json()["must_change_password"] is True

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TempPass@123"},
    )
    assert login_response.status_code == 200

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_response.json()['access_token']}"},
    )
    assert me.json()["must_change_password"] is True

    reset = client.post(
        f"/api/v1/users/{user_id}/reset-password",
        headers=headers,
        json={"generate_temporary": True},
    )
    assert reset.status_code == 200
    assert reset.json()["temporary_password"]


def test_reset_password_and_change_password(client):
    headers = login(client, "admin@prosohm.com")
    roles = client.get("/api/v1/roles", headers=headers)
    designer_role = next(r for r in list_items(roles) if r["name"] == "Designer")
    email = f"reset.user.{uuid.uuid4().hex[:8]}@prosohm.com"
    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": designer_role["id"],
            "email": email,
            "password": "TempPass@123",
            "first_name": "Reset",
            "last_name": "User",
            "is_active": True,
        },
    )
    user_id = create.json()["id"]

    reset = client.post(
        f"/api/v1/users/{user_id}/reset-password",
        headers=headers,
        json={"password": "ResetPass@123"},
    )
    assert reset.status_code == 200

    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "ResetPass@123"},
    ).json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}

    change = client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={
            "current_password": "ResetPass@123",
            "new_password": "NewPass@1234",
            "confirm_password": "NewPass@1234",
        },
    )
    assert change.status_code == 200

    me = client.get("/api/v1/auth/me", headers=user_headers)
    assert me.json()["must_change_password"] is False


def test_user_delete_disabled(client):
    headers = login(client, "admin@prosohm.com")
    response = client.delete(f"/api/v1/users/{IDS['user_binil']}", headers=headers)
    assert response.status_code == 403


def test_deactivate_user(client):
    headers = login(client, "admin@prosohm.com")
    roles = client.get("/api/v1/roles", headers=headers)
    designer_role = next(r for r in list_items(roles) if r["name"] == "Designer")
    email = f"inactive.{uuid.uuid4().hex[:8]}@prosohm.com"
    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": designer_role["id"],
            "email": email,
            "password": "TempPass@123",
            "first_name": "Inactive",
            "last_name": "User",
            "is_active": True,
        },
    )
    user_id = create.json()["id"]
    update = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert update.status_code == 200
    assert update.json()["is_active"] is False


def test_system_role_delete_forbidden(client):
    headers = login(client, "admin@prosohm.com")
    roles = client.get("/api/v1/roles", headers=headers)
    admin_role = next(r for r in list_items(roles) if r["name"] == "Admin")
    response = client.delete(f"/api/v1/roles/{admin_role['id']}", headers=headers)
    assert response.status_code == 403


def test_customers_admin_only(client):
    designer_headers = login(client, "binil@prosohm.com")
    assert client.get("/api/v1/customers", headers=designer_headers).status_code == 403

    admin_headers = login(client, "admin@prosohm.com")
    create = client.post(
        "/api/v1/customers",
        headers=admin_headers,
        json={"name": "Admin Test Customer", "code": "ATC", "is_active": True},
    )
    assert create.status_code == 201
