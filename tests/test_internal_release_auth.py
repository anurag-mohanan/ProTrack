"""Internal Release mode: login without forced password change redirect."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.conftest import login
from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.security import hash_password, verify_password
from app.models.models import User

ROLE_CASES = [
    ("admin@prosohm.com", "Admin", "/api/v1/dashboard/summary"),
    ("pm@prosohm.com", "Engineering Manager", "/api/v1/dashboard/summary"),
    ("anurag@prosohm.com", "Design Leader", "/api/v1/dashboard/summary"),
    ("binil@prosohm.com", "Designer", "/api/v1/dashboard/summary"),
    ("ranjith@prosohm.com", "Surfacer", "/api/v1/dashboard/summary"),
    ("readonly@prosohm.com", "Read Only", "/api/v1/dashboard/summary"),
]

ROLE_RESTRICTIONS = [
    ("pm@prosohm.com", "/api/v1/users", 403),
    ("binil@prosohm.com", "/api/v1/users", 403),
    ("binil@prosohm.com", "/api/v1/dashboard/workload", 403),
    ("readonly@prosohm.com", "/api/v1/dashboard/workload", 403),
]


def _prepare_soft_launch_user(session, email: str) -> None:
    user = session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.password_hash = hash_password(SOFT_LAUNCH_PASSWORD)
    user.must_change_password = True
    user.is_active = True
    user.is_deleted = False
    session.add(user)
    session.commit()


def test_health_reports_internal_release(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["internal_release"] is True


def test_auth_me_bypasses_must_change_password(client, session):
    _prepare_soft_launch_user(session, "binil@prosohm.com")
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "binil@prosohm.com", "password": SOFT_LAUNCH_PASSWORD},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False

    user = session.scalar(select(User).where(User.email == "binil@prosohm.com"))
    assert user.must_change_password is True
    assert verify_password(SOFT_LAUNCH_PASSWORD, user.password_hash)


@pytest.mark.parametrize("email,role_name,dashboard_path", ROLE_CASES)
def test_internal_release_role_login_flow(client, session, email, role_name, dashboard_path):
    _prepare_soft_launch_user(session, email)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
    )
    assert login_response.status_code == 200, f"{role_name}: login failed"
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role_name"] == role_name
    assert me.json()["must_change_password"] is False

    dashboard = client.get(dashboard_path, headers=headers)
    assert dashboard.status_code == 200, f"{role_name}: dashboard failed"

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200


@pytest.mark.parametrize("email,path,expected_status", ROLE_RESTRICTIONS)
def test_internal_release_role_permissions(client, session, email, path, expected_status):
    _prepare_soft_launch_user(session, email)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    response = client.get(path, headers=headers)
    assert response.status_code == expected_status


def test_admin_can_toggle_must_change_password(client, session):
    _prepare_soft_launch_user(session, "binil@prosohm.com")
    admin_headers = login(client, "admin@prosohm.com")
    user = session.scalar(select(User).where(User.email == "binil@prosohm.com"))
    assert user is not None

    clear = client.post(
        f"/api/v1/users/{user.id}/must-change-password",
        headers=admin_headers,
        json={"required": False},
    )
    assert clear.status_code == 200
    assert clear.json()["must_change_password"] is False

    enable = client.post(
        f"/api/v1/users/{user.id}/must-change-password",
        headers=admin_headers,
        json={"required": True},
    )
    assert enable.status_code == 200
    assert enable.json()["must_change_password"] is True


def test_internal_release_login_report(client, session, capsys):
    rows: list[tuple[str, str, str, str, str]] = []

    for email, role_name, dashboard_path in ROLE_CASES:
        _prepare_soft_launch_user(session, email)
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
        )
        if login_response.status_code != 200:
            rows.append((role_name, "FAIL", "SKIP", "SKIP", email))
            continue

        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        me = client.get("/api/v1/auth/me", headers=headers)
        change_page = "PASS" if me.json().get("must_change_password") is False else "FAIL"

        dashboard = client.get(dashboard_path, headers=headers)
        dashboard_ok = "PASS" if dashboard.status_code == 200 else "FAIL"

        logout = client.post("/api/v1/auth/logout", headers=headers)
        logout_ok = "PASS" if logout.status_code == 200 else "FAIL"

        rows.append((role_name, "PASS", change_page, dashboard_ok, logout_ok))

    print("\nInternal Release Login Report")
    print("-" * 78)
    print(f"{'Role':<24} {'Login':<8} {'No Force Change':<16} {'Dashboard':<10} {'Logout':<8}")
    print("-" * 78)
    for role_name, login_ok, change_ok, dashboard_ok, logout_ok in rows:
        print(f"{role_name:<24} {login_ok:<8} {change_ok:<16} {dashboard_ok:<10} {logout_ok:<8}")
    print("-" * 78)

    assert all(
        login_ok == "PASS" and change_ok == "PASS" and dashboard_ok == "PASS" and logout_ok == "PASS"
        for _, login_ok, change_ok, dashboard_ok, logout_ok in rows
    )


def test_production_mode_enforces_must_change_password(client, session, production_release):
    _prepare_soft_launch_user(session, "binil@prosohm.com")
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "binil@prosohm.com", "password": SOFT_LAUNCH_PASSWORD},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["must_change_password"] is True
