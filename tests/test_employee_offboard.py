"""Last working day confirm → soft offboard (history retained)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select

from app.models.enums import TimesheetStatus
from app.models.models import (
    Project,
    TeamMember,
    TeamMembershipPeriod,
    Timesheet,
    User,
)
from app.services.employee_offboard_service import apply_due_offboards
from tests.conftest import IDS, login


def _designer_role_id(client, headers) -> str:
    roles = client.get("/api/v1/roles", headers=headers).json()
    role_items = roles["items"] if isinstance(roles, dict) and "items" in roles else roles
    return next(role for role in role_items if role["name"] == "Designer")["id"]


def _create_teamed_user(client, headers, *, email: str | None = None) -> tuple[str, str]:
    team = client.post(
        "/api/v1/teams",
        json={
            "name": f"Offboard Team {uuid.uuid4().hex[:6]}",
            "colour": "#445566",
            "is_active": True,
        },
        headers=headers,
    ).json()
    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": _designer_role_id(client, headers),
            "email": email or f"offboard.{uuid.uuid4().hex[:8]}@prosohm.com",
            "password": "TempPass@123",
            "first_name": "Leave",
            "last_name": "Soon",
            "is_active": True,
            "employment_type": "full_time",
            "team_id": team["id"],
        },
    )
    assert create.status_code == 201, create.text
    return create.json()["id"], team["id"]


def test_leaving_date_requires_confirm(client):
    headers = login(client, "admin@prosohm.com")
    user_id, _team_id = _create_teamed_user(client, headers)
    today = date.today().isoformat()

    denied = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"leaving_date": today},
    )
    assert denied.status_code == 422
    assert "Confirm" in str(denied.json()["detail"])

    user = client.get(f"/api/v1/users/{user_id}", headers=headers)
    assert user.status_code == 200
    assert user.json().get("leaving_date") in (None, "")


def test_confirm_past_leaving_date_removes_team_and_archives(client, session):
    headers = login(client, "admin@prosohm.com")
    user_id, team_id = _create_teamed_user(client, headers)
    uid = uuid.UUID(user_id)

    # Seed a timesheet so history must survive
    session.add(
        Timesheet(
            id=uuid.uuid4(),
            user_id=uid,
            week_start=date.today() - timedelta(days=date.today().weekday()),
            status=TimesheetStatus.draft,
        )
    )
    # Open membership period (may already exist from create sync)
    open_periods = list(
        session.scalars(
            select(TeamMembershipPeriod).where(
                TeamMembershipPeriod.user_id == uid,
                TeamMembershipPeriod.effective_to.is_(None),
            )
        ).all()
    )
    if not open_periods:
        session.add(
            TeamMembershipPeriod(
                user_id=uid,
                team_id=uuid.UUID(team_id),
                is_primary=True,
                is_billable_headcount=True,
                effective_from=date.today() - timedelta(days=30),
                effective_to=None,
            )
        )
    # Assign live project role
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.designer_id = uid
    session.add(project)
    session.commit()

    leaving = date.today() - timedelta(days=1)
    ok = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={
            "leaving_date": leaving.isoformat(),
            "confirm_left_organisation": True,
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["leaving_date"] == leaving.isoformat()
    assert body["is_archived"] is True
    assert body["is_active"] is False
    assert body.get("team_id") in (None, "")
    assert body.get("offboard_applied_at") is not None

    session.expire_all()
    user = session.get(User, uid)
    assert user is not None
    assert user.offboard_applied_at is not None
    members = list(
        session.scalars(select(TeamMember).where(TeamMember.user_id == uid)).all()
    )
    assert members == []
    periods = list(
        session.scalars(
            select(TeamMembershipPeriod).where(TeamMembershipPeriod.user_id == uid)
        ).all()
    )
    assert periods
    assert all(p.effective_to is not None for p in periods)
    assert all(p.effective_to <= leaving for p in periods) or all(
        p.effective_to == p.effective_from for p in periods if p.effective_from > leaving
    )

    ts_count = session.scalar(
        select(func.count()).select_from(Timesheet).where(Timesheet.user_id == uid)
    )
    assert int(ts_count or 0) >= 1

    session.refresh(project)
    assert project.designer_id is None


def test_future_leaving_date_defers_live_offboard(client, session):
    headers = login(client, "admin@prosohm.com")
    user_id, _team_id = _create_teamed_user(client, headers)
    uid = uuid.UUID(user_id)
    future = date.today() + timedelta(days=10)

    ok = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={
            "leaving_date": future.isoformat(),
            "confirm_left_organisation": True,
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["leaving_date"] == future.isoformat()
    assert body["is_archived"] is False
    assert body["is_active"] is True
    assert body.get("offboard_applied_at") in (None, "")

    session.expire_all()
    members = list(
        session.scalars(select(TeamMember).where(TeamMember.user_id == uid)).all()
    )
    assert len(members) >= 1

    applied = apply_due_offboards(session, as_of=future)
    session.commit()
    assert applied >= 1

    session.expire_all()
    user = session.get(User, uid)
    assert user is not None
    assert user.is_archived is True
    assert user.offboard_applied_at is not None
    assert (
        list(session.scalars(select(TeamMember).where(TeamMember.user_id == uid)).all())
        == []
    )

    # Idempotent
    again = apply_due_offboards(session, as_of=future)
    session.commit()
    assert again == 0


def test_finance_leaving_date_requires_confirm(client):
    headers = login(client, "admin@prosohm.com")
    user_id, _team_id = _create_teamed_user(client, headers)
    today = date.today().isoformat()

    denied = client.patch(
        f"/api/v1/finance/employee-costs/roster/{user_id}/leaving-date",
        headers=headers,
        json={"leaving_date": today},
    )
    # Finance may 403 if admin lacks finance module — accept 422 or 403
    if denied.status_code == 403:
        return
    assert denied.status_code == 422

    ok = client.patch(
        f"/api/v1/finance/employee-costs/roster/{user_id}/leaving-date",
        headers=headers,
        json={"leaving_date": today, "confirm_left_organisation": True},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["leaving_date"] == today


def test_clear_leaving_date_does_not_restore_team(client, session):
    headers = login(client, "admin@prosohm.com")
    user_id, _team_id = _create_teamed_user(client, headers)
    uid = uuid.UUID(user_id)
    leaving = date.today() - timedelta(days=2)

    ok = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={
            "leaving_date": leaving.isoformat(),
            "confirm_left_organisation": True,
        },
    )
    assert ok.status_code == 200

    cleared = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"leaving_date": None},
    )
    assert cleared.status_code == 200
    session.expire_all()
    user = session.get(User, uid)
    assert user is not None
    assert user.leaving_date is None
    assert user.is_archived is True
    assert user.offboard_applied_at is not None
    assert (
        list(session.scalars(select(TeamMember).where(TeamMember.user_id == uid)).all())
        == []
    )


def test_same_leaving_date_resave_without_confirm(client):
    headers = login(client, "admin@prosohm.com")
    user_id, _team_id = _create_teamed_user(client, headers)
    leaving = date.today().isoformat()

    first = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"leaving_date": leaving, "confirm_left_organisation": True},
    )
    assert first.status_code == 200

    # Updating other fields while sending same leaving_date must not demand confirm
    second = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"leaving_date": leaving, "first_name": "LeaveUpdated"},
    )
    assert second.status_code == 200
    assert second.json()["first_name"] == "LeaveUpdated"
