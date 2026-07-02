"""Forced password change flow — validation, persistence, and role coverage."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.password_policy import PASSWORD_REQUIREMENTS_MESSAGE
from app.core.security import hash_password, verify_password
from app.models.models import User
from tests.conftest import DEFAULT_PASSWORD, IDS, login

ROLE_FLOW_CASES = [
    ("admin@prosohm.com", "Admin", "Admin@2026A"),
    ("pm@prosohm.com", "Engineering Manager", "Manager@2026"),
    ("anurag@prosohm.com", "Design Leader", "Leader@2026"),
    ("binil@prosohm.com", "Designer", "Designer@2026"),
    ("ranjith@prosohm.com", "Surfacer", "Surfacer@2026"),
]


def _validation_detail(response) -> str:
    detail = response.json().get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            return str(first.get("msg", ""))
    return str(detail)


def _prepare_forced_change(session, email: str) -> None:
    user = session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.password_hash = hash_password(SOFT_LAUNCH_PASSWORD)
    user.must_change_password = True
    session.add(user)
    session.commit()


def test_password_policy_message_matches_validation():
    assert PASSWORD_REQUIREMENTS_MESSAGE == (
        "Password must be at least 8 characters and include uppercase, "
        "lowercase, number, and special character."
    )


def test_change_password_rejects_weak_password_with_exact_message(client, production_release):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "weakpass",
            "confirm_password": "weakpass",
        },
    )
    assert response.status_code == 422
    assert PASSWORD_REQUIREMENTS_MESSAGE in _validation_detail(response)


def test_change_password_rejects_incorrect_current_password(client, production_release):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": "WrongPass@123",
            "new_password": "NewPass@1234",
            "confirm_password": "NewPass@1234",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect."


def test_change_password_rejects_mismatch(client, production_release):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "NewPass@1234",
            "confirm_password": "Mismatch@1234",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "New password and confirmation do not match."


def test_change_password_rejects_same_as_current(client, production_release):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": DEFAULT_PASSWORD,
            "confirm_password": DEFAULT_PASSWORD,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "New password must be different from your current password."


def test_change_password_updates_hash_and_clears_flag(client, session, production_release):
    headers = login(client, "admin@prosohm.com")
    new_password = "AdminReset@2026"
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Password updated successfully."
    assert body["must_change_password"] is False

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False

    user = session.get(User, IDS["user_admin"])
    assert verify_password(new_password, user.password_hash)
    assert user.must_change_password is False


@pytest.mark.parametrize("email,role_name,new_password", ROLE_FLOW_CASES)
def test_role_forced_password_change_flow(client, session, email, role_name, new_password, production_release):
    _prepare_forced_change(session, email)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
    )
    assert login_response.status_code == 200, f"{role_name}: login failed"
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role_name"] == role_name
    assert me.json()["must_change_password"] is True

    change = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": SOFT_LAUNCH_PASSWORD,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert change.status_code == 200, f"{role_name}: change password failed — {change.text}"
    assert change.json()["must_change_password"] is False

    me_after = client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 200
    assert me_after.json()["must_change_password"] is False

    dashboard = client.get("/api/v1/dashboard/summary", headers=headers)
    assert dashboard.status_code == 200, f"{role_name}: dashboard access failed"

    user = session.scalar(select(User).where(User.email == email))
    assert verify_password(new_password, user.password_hash)
    assert user.must_change_password is False


def test_password_change_flow_report(client, session, production_release, capsys):
    """Print a role-by-role report for manual review in CI output."""
    rows: list[tuple[str, str, str, str, str]] = []

    for email, role_name, new_password in ROLE_FLOW_CASES:
        _prepare_forced_change(session, email)

        login_ok = "PASS"
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
        )
        if login_response.status_code != 200:
            rows.append((role_name, "FAIL", "SKIP", "SKIP", email))
            continue

        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        change_ok = "PASS"
        change = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": SOFT_LAUNCH_PASSWORD,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )
        if change.status_code != 200:
            change_ok = "FAIL"

        dashboard_ok = "PASS"
        me = client.get("/api/v1/auth/me", headers=headers)
        if me.status_code != 200 or me.json()["must_change_password"]:
            dashboard_ok = "FAIL"
        else:
            dashboard = client.get("/api/v1/dashboard/summary", headers=headers)
            if dashboard.status_code != 200:
                dashboard_ok = "FAIL"

        rows.append((role_name, login_ok, change_ok, dashboard_ok, email))

    print("\nForced Password Change Flow Report")
    print("-" * 72)
    print(f"{'Role':<24} {'Login':<8} {'Change':<8} {'Dashboard':<10} Email")
    print("-" * 72)
    for role_name, login_ok, change_ok, dashboard_ok, email in rows:
        print(f"{role_name:<24} {login_ok:<8} {change_ok:<8} {dashboard_ok:<10} {email}")
    print("-" * 72)

    assert all(row[1] == "PASS" and row[2] == "PASS" and row[3] == "PASS" for row in rows)
