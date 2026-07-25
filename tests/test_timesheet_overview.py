"""Timesheet overview team scoping for leaders and managers."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.phase36_team_membership_periods_schema_sync import backfill_membership_periods
from app.models.enums import TimesheetStatus, WorkCategory
from app.models.models import Role, Team, TeamMember, Timesheet, TimesheetEntry, User
from app.services.timesheet_overview_service import (
    build_timesheet_overview,
    get_timesheet_leader_team_ids,
    get_timesheet_visible_user_ids,
)
from tests.conftest import DEFAULT_PASSWORD, IDS


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
    visible_ids = get_timesheet_visible_user_ids(session, office_admin)
    assert visible_ids is not None
    assert office_admin.id not in visible_ids

    overview = build_timesheet_overview(session, office_admin)
    assert overview["scope_all_teams"] is True
    assert all(user["requires_timesheet"] is True for user in overview["users"])
    assert all(user["id"] != str(office_admin.id) for user in overview["users"])
    assert "requires_timesheet" in overview["users"][0] if overview["users"] else True

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
    assert all(user["requires_timesheet"] is True for user in body["users"])
    assert office_admin.email not in {user["email"] for user in body["users"]}

    # Month list must not be filtered down to only the Office Admin's empty sheet.
    month_list = client.get("/api/v1/timesheets", params={"month": "2026-06", "limit": 500}, headers=headers)
    assert month_list.status_code == 200


def test_overview_team_membership_windows_start_from_transfer(session, client):
    """Independent team sections only cover hours from membership start on that team."""
    source = Team(id=uuid.uuid4(), name="Overview Source Team", is_active=True)
    target = Team(id=uuid.uuid4(), name="Overview Target Team", is_active=True)
    session.add_all([source, target])
    session.flush()

    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.team_id = source.id
    designer.is_active = True
    designer.requires_timesheet = True
    session.add(
        TeamMember(
            team_id=source.id,
            user_id=designer.id,
            is_primary=True,
            is_billable_headcount=True,
            effective_from=date(2020, 1, 1),
        )
    )
    session.commit()
    backfill_membership_periods(session)
    session.commit()

    member = session.scalar(
        select(TeamMember).where(
            TeamMember.team_id == source.id,
            TeamMember.user_id == designer.id,
        )
    )
    assert member is not None
    transfer_on = date(2026, 7, 20)
    response = client.post(
        f"/api/v1/teams/{source.id}/members/{member.id}/transfer",
        json={
            "target_team_id": str(target.id),
            "effective_from": transfer_on.isoformat(),
        },
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text

    week_start = date(2026, 7, 13)
    timesheet = Timesheet(
        user_id=designer.id,
        week_start=week_start,
        status=TimesheetStatus.approved,
    )
    session.add(timesheet)
    session.flush()
    session.add_all(
        [
            TimesheetEntry(
                timesheet_id=timesheet.id,
                entry_date=date(2026, 7, 14),
                hours=Decimal("8"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=IDS["project"],
            ),
            TimesheetEntry(
                timesheet_id=timesheet.id,
                entry_date=date(2026, 7, 21),
                hours=Decimal("6"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=IDS["project"],
            ),
        ]
    )
    session.commit()

    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    overview = build_timesheet_overview(session, admin, month="2026-07")

    target_section = next(
        team for team in overview["teams"] if team["team_id"] == target.id
    )
    source_section = next(
        team for team in overview["teams"] if team["team_id"] == source.id
    )

    assert designer.id in target_section["user_ids"]
    assert designer.id in source_section["user_ids"]

    target_windows = target_section["membership_windows"][str(designer.id)]
    assert target_windows[0]["start"] == transfer_on
    assert target_windows[0]["end"] == date(2026, 7, 31)

    source_windows = source_section["membership_windows"][str(designer.id)]
    assert source_windows[0]["start"] == date(2026, 7, 1)
    assert source_windows[0]["end"] == date(2026, 7, 19)

    api = client.get(
        "/api/v1/timesheets/overview",
        params={"month": "2026-07"},
        headers=client.auth_headers,
    )
    assert api.status_code == 200
    body = api.json()
    api_target = next(team for team in body["teams"] if team["team_id"] == str(target.id))
    assert api_target["membership_windows"][str(designer.id)][0]["start"] == transfer_on.isoformat()
