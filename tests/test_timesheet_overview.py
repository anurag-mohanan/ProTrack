"""Timesheet overview team scoping for leaders and managers."""

import uuid

from app.core.security import hash_password
from app.models.models import Role, User
from app.services.timesheet_overview_service import (
    build_timesheet_overview,
    get_timesheet_leader_team_ids,
    get_timesheet_visible_user_ids,
)
from tests.conftest import DEFAULT_PASSWORD


def test_timesheet_overview_endpoint(client, auth_headers):
    response = client.get("/api/v1/timesheets/overview", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "teams" in body
    assert "users" in body
    assert isinstance(body["teams"], list)
    assert isinstance(body["users"], list)


def test_timesheet_overview_user_includes_working_hours(client, auth_headers):
    body = client.get("/api/v1/timesheets/overview", headers=auth_headers).json()
    assert body["users"]
    assert "working_hours_per_day" in body["users"][0]


def test_office_administrator_sees_all_teams_overview(session, client):
    role = session.query(Role).filter_by(name="Office Administrator").one_or_none()
    if role is None:
        role = Role(
            id=uuid.uuid4(),
            name="Office Administrator",
            description="Office administration — timesheet completion monitoring",
        )
        session.add(role)
        session.flush()

    office_admin = User(
        id=uuid.uuid4(),
        email="office.admin@prosohm.com",
        first_name="Office",
        last_name="Admin",
        password_hash=hash_password(DEFAULT_PASSWORD),
        role_id=role.id,
        is_active=True,
        requires_timesheet=False,
    )
    session.add(office_admin)
    session.commit()

    assert get_timesheet_leader_team_ids(session, office_admin) is None
    assert get_timesheet_visible_user_ids(session, office_admin) is None

    overview = build_timesheet_overview(session, office_admin)
    assert overview["scope_all_teams"] is True
    assert len(overview["teams"]) >= 1
    assert len(overview["users"]) >= 1
    assert "requires_timesheet" in overview["users"][0]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": office_admin.email, "password": DEFAULT_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/timesheets/overview", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["scope_all_teams"] is True
    assert body["teams"]
    assert body["users"]

    # Month list must not be filtered down to only the Office Admin's empty sheet.
    month_list = client.get("/api/v1/timesheets", params={"month": "2026-06", "limit": 500}, headers=headers)
    assert month_list.status_code == 200
