"""Immutable hire dates and audited historical corrections."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select

from app.models.enums import ActivityAction
from app.models.models import Activity, TeamMembershipPeriod, User, UserJobEvent
from app.services.user_change_service import EVENT_HISTORICAL_CORRECTION, EVENT_TRANSFER
from tests.conftest import login


def _designer_role_id(client, headers) -> str:
    roles = client.get("/api/v1/roles", headers=headers).json()
    items = roles["items"] if isinstance(roles, dict) and "items" in roles else roles
    return next(role["id"] for role in items if role["name"] == "Designer")


def _create_employee(client, headers, *, email: str, **extra) -> dict:
    payload = {
        "role_id": _designer_role_id(client, headers),
        "email": email,
        "password": "TempPass@123",
        "first_name": "Hire",
        "last_name": "Date",
        "is_active": True,
        **extra,
    }
    created = client.post("/api/v1/users", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def test_designer_cannot_patch_users(client):
    admin = login(client, "admin@prosohm.com")
    employee = _create_employee(client, admin, email="imm.denied@prosohm.com")
    designer = login(client, "binil@prosohm.com")
    denied = client.patch(
        f"/api/v1/users/{employee['id']}",
        headers=designer,
        json={"joining_date": "2024-01-01"},
    )
    assert denied.status_code == 403


def test_admin_normal_patch_cannot_change_set_hire_dates(client):
    headers = login(client, "admin@prosohm.com")
    employee = _create_employee(
        client,
        headers,
        email="imm.lock@prosohm.com",
        joining_date="2025-01-15",
        first_job_date="2020-06-01",
    )

    blocked = client.patch(
        f"/api/v1/users/{employee['id']}",
        headers=headers,
        json={"joining_date": "2025-02-01", "first_name": "Still"},
    )
    assert blocked.status_code == 422, blocked.text

    same = client.patch(
        f"/api/v1/users/{employee['id']}",
        headers=headers,
        json={
            "joining_date": "2025-01-15",
            "first_job_date": "2020-06-01",
            "designation": "Designer",
        },
    )
    assert same.status_code == 200, same.text
    body = same.json()
    assert body["joining_date"] == "2025-01-15"
    assert body["first_job_date"] == "2020-06-01"
    assert body["designation"] == "Designer"


def test_blank_hire_dates_can_be_filled_once(client):
    headers = login(client, "admin@prosohm.com")
    employee = _create_employee(client, headers, email="imm.fill@prosohm.com")
    assert employee.get("joining_date") in (None, "")

    filled = client.patch(
        f"/api/v1/users/{employee['id']}",
        headers=headers,
        json={"joining_date": "2026-03-01", "first_job_date": "2018-04-10"},
    )
    assert filled.status_code == 200, filled.text
    assert filled.json()["joining_date"] == "2026-03-01"
    assert filled.json()["first_job_date"] == "2018-04-10"

    blocked = client.patch(
        f"/api/v1/users/{employee['id']}",
        headers=headers,
        json={"joining_date": "2026-03-02"},
    )
    assert blocked.status_code == 422


def test_historical_correction_is_audited(client, session):
    headers = login(client, "admin@prosohm.com")
    employee = _create_employee(
        client,
        headers,
        email="imm.correct@prosohm.com",
        joining_date="2025-01-15",
    )
    user_id = employee["id"]

    corrected = client.post(
        f"/api/v1/users/{user_id}/historical-corrections",
        headers=headers,
        json={
            "joining_date": "2025-01-20",
            "reason": "Offer letter shows 20 Jan, not 15 Jan.",
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["joining_date"] == "2025-01-20"

    session.expire_all()
    user = session.get(User, UUID(user_id))
    assert user is not None
    assert str(user.joining_date) == "2025-01-20"

    event = session.scalar(
        select(UserJobEvent).where(
            UserJobEvent.user_id == UUID(user_id),
            UserJobEvent.event_type == EVENT_HISTORICAL_CORRECTION,
        )
    )
    assert event is not None
    assert "Offer letter" in (event.notes or "")

    activity = session.scalar(
        select(Activity).where(
            Activity.entity_id == UUID(user_id),
            Activity.action == ActivityAction.user_historical_correction,
        )
    )
    assert activity is not None
    old_value = json.loads(activity.old_value or "{}")
    new_value = json.loads(activity.new_value or "{}")
    assert old_value["joining_date"] == "2025-01-15"
    assert new_value["joining_date"] == "2025-01-20"
    assert "Offer letter" in new_value["reason"]


def test_existing_employee_unchanged_and_create_with_joining_date(client, session):
    headers = login(client, "admin@prosohm.com")
    admin_before = client.get("/api/v1/auth/me", headers=headers).json()
    created = _create_employee(
        client,
        headers,
        email="imm.create@prosohm.com",
        joining_date="2024-11-01",
    )
    assert created["joining_date"] == "2024-11-01"

    admin_after = client.get("/api/v1/auth/me", headers=headers).json()
    assert admin_after["id"] == admin_before["id"]
    assert admin_after.get("joining_date") == admin_before.get("joining_date")

    session.expire_all()
    admin_row = session.get(User, UUID(admin_before["id"]))
    assert admin_row is not None
    assert admin_row.joining_date is None


def test_primary_team_change_records_transfer_history(client, session):
    headers = login(client, "admin@prosohm.com")
    team_a = client.post(
        "/api/v1/teams",
        json={"name": "Mold Design Imm", "colour": "#111111", "is_active": True},
        headers=headers,
    ).json()["id"]
    team_b = client.post(
        "/api/v1/teams",
        json={"name": "CAD Development Imm", "colour": "#222222", "is_active": True},
        headers=headers,
    ).json()["id"]
    employee = _create_employee(
        client,
        headers,
        email="imm.team@prosohm.com",
        team_id=team_a,
    )
    moved = client.patch(
        f"/api/v1/users/{employee['id']}",
        headers=headers,
        json={"team_id": team_b, "designation": "CAD Designer"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["team_id"] == team_b
    assert moved.json()["designation"] == "CAD Designer"

    session.expire_all()
    user_id = UUID(employee["id"])
    transfer = session.scalar(
        select(UserJobEvent).where(
            UserJobEvent.user_id == user_id,
            UserJobEvent.event_type == EVENT_TRANSFER,
        )
    )
    assert transfer is not None
    from_value = json.loads(transfer.from_value or "{}")
    to_value = json.loads(transfer.to_value or "{}")
    assert from_value["team_id"] == team_a
    assert to_value["team_id"] == team_b

    periods = list(
        session.scalars(
            select(TeamMembershipPeriod)
            .where(TeamMembershipPeriod.user_id == user_id)
            .order_by(TeamMembershipPeriod.effective_from)
        ).all()
    )
    assert len(periods) >= 1
    open_period = next((row for row in periods if row.effective_to is None), None)
    assert open_period is not None
    assert str(open_period.team_id) == team_b
    closed = [row for row in periods if row.effective_to is not None]
    if closed:
        assert str(closed[-1].team_id) == team_a
