"""Performance July–June cycle dossier."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import select

from app.core.security import hash_password
from app.models.models import Role, User
from app.services.performance_dossier_service import build_performance_dossier
from app.services.performance_review_service import current_review_year, review_period_bounds
from tests.conftest import DEFAULT_PASSWORD, login


def test_dossier_self_access(client, session):
    headers = login(client, "admin@prosohm.com")
    year = current_review_year()
    start, end = review_period_bounds(year)
    assert start.month == 7 and start.day == 1
    assert end.month == 6 and end.day == 30

    response = client.get(
        f"/api/v1/hr/performance/dossier?review_year={year}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["review_year"] == year
    assert body["period_start"] == start.isoformat()
    assert body["period_end"] == end.isoformat()
    assert "capacity" in body
    assert "projects" in body
    assert "leave_source_note" in body
    assert body["capacity"]["months_in_period"] == 12
    assert len(body["months"]) == 12


def test_dossier_roster(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/hr/performance/dossier-roster", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert body["review_year"] == current_review_year()


def test_dossier_forbidden_for_unrelated_user(client, session):
    role = session.scalar(select(Role).where(Role.name == "Designer"))
    assert role is not None
    outsider = User(
        id=uuid4(),
        role_id=role.id,
        email="dossier.outsider@prosohm.com",
        password_hash=hash_password(DEFAULT_PASSWORD),
        first_name="Out",
        last_name="Sider",
        designation="Designer",
        is_active=True,
    )
    session.add(outsider)
    session.commit()

    designer_headers = login(client, "dossier.outsider@prosohm.com")
    admin = login(client, "admin@prosohm.com")
    me = client.get("/api/v1/auth/me", headers=admin).json()

    # Designer viewing admin dossier should be denied unless they manage admin
    denied = client.get(
        f"/api/v1/hr/performance/dossier?user_id={me['id']}",
        headers=designer_headers,
    )
    assert denied.status_code in (403, 404)


def test_build_dossier_service_shape(session):
    admin = session.scalar(select(User).where(User.email == "admin@prosohm.com"))
    assert admin is not None
    payload = build_performance_dossier(
        session, subject=admin, viewer=admin, review_year=current_review_year()
    )
    assert payload["employee"]["email"] == admin.email
    assert isinstance(payload["projects"]["owned"], list)
    assert isinstance(payload["projects"]["supported"], list)
