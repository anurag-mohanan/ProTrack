"""Tests for role-based KPI participation."""

from tests.conftest import login


def test_operational_roles_lookup(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/lookups/operational-roles", headers=headers)
    assert response.status_code == 200
    roles = response.json()
    codes = {row["code"] for row in roles}
    assert "engineering" in codes
    assert "management" in codes
    assert "administration" in codes


def test_dashboard_role_kpis(client):
    admin_headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/dashboard/role-kpis", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["dashboard_profile"] in {"engineering", "management", "administration"}
    assert payload["engineering_productivity_user_count"] >= 0


def test_engineering_manager_excluded_from_productivity_users(client, session):
    from app.models.models import User
    from app.services.kpi_participation import engineering_productivity_users

    pm = session.scalar(
        __import__("sqlalchemy").select(User).where(User.email == "pm@prosohm.com")
    )
    assert pm is not None
    assert pm.kpi_engineering_productivity is False

    included_ids = {user.id for user in engineering_productivity_users(session)}
    assert pm.id not in included_ids
