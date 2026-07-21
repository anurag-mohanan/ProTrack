"""Security hardening foundation tests.

Covers edge headers, field-level security helpers, path-traversal sandboxing,
authorization on the Security Center, stateless force-logout, automatic account
lockout, and password-reuse prevention.
"""

from pathlib import Path

from app.core.field_security import (
    can_view_budget,
    can_view_cost,
    can_view_profitability,
    can_view_salary,
)
from app.core.path_safety import is_within, resolve_within
from app.models.models import User
from tests.conftest import DEFAULT_PASSWORD, IDS, login


def test_security_headers_present(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert "Content-Security-Policy" in response.headers


def test_field_security_salary_visibility(session):
    admin = session.get(User, IDS["user_admin"])
    em = session.get(User, IDS["user_pm"])
    leader = session.get(User, IDS["user_anurag"])
    designer = session.get(User, IDS["user_binil"])

    assert can_view_salary(admin, "Admin") is True
    assert can_view_salary(em, "Engineering Manager") is True
    # A Design Leader / Designer has neither finance access nor the special.
    assert can_view_salary(leader, "Design Leader") is False
    assert can_view_salary(designer, "Designer") is False


def test_field_security_cost_and_budget_and_profitability(session):
    em = session.get(User, IDS["user_pm"])
    designer = session.get(User, IDS["user_binil"])

    assert can_view_cost(em, "Engineering Manager") is True
    assert can_view_cost(designer, "Designer") is False
    assert can_view_budget(em, "Engineering Manager") is True
    assert can_view_budget(designer, "Designer") is False
    assert can_view_profitability(designer, "Designer") is False


def test_path_safety_rejects_traversal(tmp_path: Path):
    base = tmp_path / "sandbox"
    base.mkdir()
    (base / "ok.txt").write_text("hello")

    assert resolve_within(base, "ok.txt") is not None
    assert resolve_within(base, "sub/nested.txt") is not None
    # Escape attempts must be rejected.
    assert resolve_within(base, "../outside.txt") is None
    assert resolve_within(base, "../../etc/passwd") is None

    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    assert is_within(base / "ok.txt", [base]) is True
    assert is_within(outside, [base]) is False


def test_security_overview_admin_only(client):
    designer_headers = login(client, "binil@prosohm.com")
    denied = client.get("/api/v1/admin/security/overview", headers=designer_headers)
    assert denied.status_code == 403

    admin_headers = login(client, "admin@prosohm.com")
    allowed = client.get("/api/v1/admin/security/overview", headers=admin_headers)
    assert allowed.status_code == 200
    body = allowed.json()
    assert "security_score" in body
    assert "config_warnings" in body
    assert "recent_events" in body


def test_security_policy_update_persists(client):
    admin_headers = login(client, "admin@prosohm.com")
    response = client.put(
        "/api/v1/admin/security/policy",
        headers=admin_headers,
        json={"lockout_duration_minutes": 45, "password_history_count": 7},
    )
    assert response.status_code == 200

    fetched = client.get("/api/v1/admin/security/policy", headers=admin_headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["lockout_duration_minutes"] == 45
    assert body["password_history_count"] == 7


def test_logout_all_devices_invalidates_existing_token(client):
    headers = login(client, "admin@prosohm.com")
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    logout = client.post("/api/v1/auth/logout-all-devices", headers=headers)
    assert logout.status_code == 200

    # The previously issued token now carries a stale token_version.
    stale = client.get("/api/v1/auth/me", headers=headers)
    assert stale.status_code == 401


def test_account_lockout_after_failed_attempts(client):
    for _ in range(5):
        bad = client.post(
            "/api/v1/auth/login",
            json={"email": "ranjith@prosohm.com", "password": "wrong-password"},
        )
        assert bad.status_code == 401

    # Even the correct password is now refused while the lock is active.
    locked = client.post(
        "/api/v1/auth/login",
        json={"email": "ranjith@prosohm.com", "password": DEFAULT_PASSWORD},
    )
    assert locked.status_code == 401


def test_password_reuse_blocked(client):
    headers = login(client, "binil@prosohm.com")
    new_password = "NewPass@2026"

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert changed.status_code == 200

    # Attempting to change back to the original (in-history) password is rejected.
    reuse = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": new_password,
            "new_password": DEFAULT_PASSWORD,
            "confirm_password": DEFAULT_PASSWORD,
        },
    )
    assert reuse.status_code == 422
