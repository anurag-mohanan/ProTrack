"""Timesheet reports respect dated team membership / transfers."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.phase36_team_membership_periods_schema_sync import backfill_membership_periods
from app.models.enums import TimesheetStatus, WorkCategory
from app.models.models import Team, TeamMember, Timesheet, TimesheetEntry, User
from app.services.reporting.designer_team_timesheet import build_designer_team_timesheet
from app.services.reporting.team_membership_windows import (
    membership_windows_for_teams,
    users_on_teams_during,
)
from tests.conftest import IDS


def _seed_transfer_scenario(session, *, transfer_on: date):
    source = Team(id=uuid.uuid4(), name="Source Hours Team", is_active=True)
    target = Team(id=uuid.uuid4(), name="Target Hours Team", is_active=True)
    session.add_all([source, target])
    session.flush()

    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.team_id = source.id
    designer.is_active = True
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
    return source, target, designer, member


def test_future_transfer_excluded_from_target_roster(client, session):
    source, target, designer, member = _seed_transfer_scenario(
        session, transfer_on=date(2026, 7, 20)
    )
    future = date.today().replace(year=date.today().year + 1, month=3, day=1)
    response = client.post(
        f"/api/v1/teams/{source.id}/members/{member.id}/transfer",
        json={"target_team_id": str(target.id), "effective_from": future.isoformat()},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text

    as_of = date.today()
    target_members = users_on_teams_during(
        session, frozenset({target.id}), range_start=as_of, range_end=as_of
    )
    source_members = users_on_teams_during(
        session, frozenset({source.id}), range_start=as_of, range_end=as_of
    )
    assert designer.id not in target_members
    assert designer.id in source_members


def test_team_timesheet_hours_start_from_transfer_date(client, session):
    source, target, designer, member = _seed_transfer_scenario(
        session, transfer_on=date(2026, 7, 20)
    )
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

    week_start = date(2026, 7, 13)  # Monday before transfer
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
                entry_date=date(2026, 7, 14),  # before transfer — source only
                hours=Decimal("8"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=IDS["project"],
            ),
            TimesheetEntry(
                timesheet_id=timesheet.id,
                entry_date=date(2026, 7, 21),  # after transfer — target
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

    target_report = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=date(2026, 7, 1),
        team_id=target.id,
    )
    target_row = next(
        (row for row in target_report.designers if row.user_id == designer.id), None
    )
    assert target_row is not None
    assert float(target_row.productive_hours) == 6.0
    assert float(target_row.total_hours) == 6.0

    source_report = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=date(2026, 7, 1),
        team_id=source.id,
    )
    source_row = next(
        (row for row in source_report.designers if row.user_id == designer.id), None
    )
    assert source_row is not None
    assert float(source_row.productive_hours) == 8.0

    windows = membership_windows_for_teams(
        session,
        frozenset({target.id}),
        range_start=date(2026, 7, 1),
        range_end=date(2026, 7, 31),
    )
    assert windows[designer.id][0][0] == transfer_on


def test_future_transfer_not_listed_on_target_timesheet(client, session):
    source, target, designer, member = _seed_transfer_scenario(
        session, transfer_on=date(2026, 7, 20)
    )
    future = date(2026, 12, 1)
    # Keep "today" before future for the transfer service live-home rule.
    response = client.post(
        f"/api/v1/teams/{source.id}/members/{member.id}/transfer",
        json={"target_team_id": str(target.id), "effective_from": future.isoformat()},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text

    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    # July report is before the Dec transfer — designer must not appear on target.
    target_report = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=date(2026, 7, 1),
        team_id=target.id,
    )
    assert all(row.user_id != designer.id for row in target_report.designers)
