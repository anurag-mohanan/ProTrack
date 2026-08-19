"""Resource movement must not rewrite historical timesheet team attribution."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select

from app.db.phase36_team_membership_periods_schema_sync import backfill_membership_periods
from app.models.enums import (
    ExecutionStatus,
    TeamRelationshipType,
    TimesheetStatus,
    WorkCategory,
)
from app.models.models import (
    Customer,
    NonProductiveCode,
    Project,
    TaskType,
    Team,
    TeamMember,
    Timesheet,
    TimesheetEntry,
    User,
)
from app.services.reporting.data_service import build_engineering_report
from app.services.reporting.designer_team_timesheet import build_designer_team_timesheet
from app.services.reporting.report_scope import resolve_report_scope
from app.services.reporting.timesheet_attribution import (
    resolve_home_team_id,
    stamp_home_team_on_entry,
    work_context_team_id,
)
from tests.conftest import IDS


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def test_resolve_home_team_id_prefers_snapshot_and_skips_live_team_when_timeline_exists():
    snap = uuid.uuid4()
    old = uuid.uuid4()
    current = uuid.uuid4()
    timeline = [(date(2026, 1, 1), date(2026, 7, 31), old)]
    user = SimpleNamespace(team_id=current)

    assert (
        resolve_home_team_id(
            snapshot_home_team_id=snap,
            entry_date=date(2026, 6, 1),
            user=user,
            timeline=timeline,
        )
        == snap
    )
    assert (
        resolve_home_team_id(
            snapshot_home_team_id=None,
            entry_date=date(2026, 6, 1),
            user=user,
            timeline=timeline,
        )
        == old
    )
    assert (
        resolve_home_team_id(
            snapshot_home_team_id=None,
            entry_date=date(2025, 12, 1),
            user=user,
            timeline=timeline,
        )
        is None
    )
    assert (
        resolve_home_team_id(
            snapshot_home_team_id=None,
            entry_date=date(2026, 6, 1),
            user=user,
            timeline=None,
        )
        == current
    )


def _seed_mold_cad_transfer(session, client):
    mold = Team(id=uuid.uuid4(), name="Mold Team", is_active=True)
    cad = Team(id=uuid.uuid4(), name="CAD Development", is_active=True)
    session.add_all([mold, cad])
    session.flush()

    john = session.get(User, IDS["user_binil"])
    leader = session.get(User, IDS["user_anurag"])
    assert john is not None and leader is not None
    john.team_id = mold.id
    john.is_active = True
    leader.team_id = cad.id
    session.add_all(
        [
            TeamMember(
                team_id=mold.id,
                user_id=john.id,
                is_primary=True,
                is_billable_headcount=True,
                effective_from=date(2020, 1, 1),
            ),
            TeamMember(
                team_id=cad.id,
                user_id=leader.id,
                relationship_type=TeamRelationshipType.team_leader,
                is_primary=True,
                is_billable_headcount=True,
                effective_from=date(2020, 1, 1),
            ),
        ]
    )
    session.commit()
    backfill_membership_periods(session)
    session.commit()

    member = session.scalar(
        select(TeamMember).where(
            TeamMember.team_id == mold.id,
            TeamMember.user_id == john.id,
        )
    )
    assert member is not None

    customer_b = Customer(name="Customer B CAD", code="CUST-B-CAD", is_active=True)
    session.add(customer_b)
    session.flush()

    mold_project = Project(
        id=uuid.uuid4(),
        tool_number="MOLD-A-100",
        part_description="Customer A mold",
        customer_id=IDS["customer"],
        team_id=mold.id,
        stream_id=IDS["stream"],
        quoted_hours=Decimal("200"),
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    cad_project = Project(
        id=uuid.uuid4(),
        tool_number="CAD-B-030",
        part_description="Customer B CAD",
        customer_id=customer_b.id,
        team_id=cad.id,
        stream_id=IDS["stream"],
        quoted_hours=Decimal("80"),
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    session.add_all([mold_project, cad_project])
    session.flush()

    training = session.scalar(
        select(NonProductiveCode).where(NonProductiveCode.code == "C504")
    )
    task = session.scalar(select(TaskType).where(TaskType.name == "Design"))
    assert training is not None and task is not None

    sheets: dict[date, Timesheet] = {}

    def sheet_for(day: date) -> Timesheet:
        week = _monday(day)
        existing = sheets.get(week)
        if existing is not None:
            return existing
        row = Timesheet(
            user_id=john.id,
            week_start=week,
            status=TimesheetStatus.approved,
        )
        session.add(row)
        session.flush()
        sheets[week] = row
        return row

    # Legacy rows: no home_team_id snapshot (NULL).
    session.add(
        TimesheetEntry(
            timesheet_id=sheet_for(date(2026, 7, 6)).id,
            entry_date=date(2026, 7, 6),
            hours=Decimal("10"),
            work_category=WorkCategory.non_productive,
            non_productive_code_id=training.id,
            is_billable=False,
        )
    )
    project_days = [
        date(2026, 7, 7),
        date(2026, 7, 8),
        date(2026, 7, 9),
        date(2026, 7, 10),
        date(2026, 7, 13),
        date(2026, 7, 14),
        date(2026, 7, 15),
        date(2026, 7, 16),
        date(2026, 7, 17),
        date(2026, 7, 20),
    ]
    for day in project_days:
        session.add(
            TimesheetEntry(
                timesheet_id=sheet_for(day).id,
                entry_date=day,
                hours=Decimal("10"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=mold_project.id,
                task_type_id=task.id,
            )
        )
    session.commit()

    transfer_on = date(2026, 8, 1)
    response = client.post(
        f"/api/v1/teams/{mold.id}/members/{member.id}/transfer",
        json={"target_team_id": str(cad.id), "effective_from": transfer_on.isoformat()},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    session.refresh(john)
    assert john.team_id == cad.id

    # Historical NULL snapshots must stay NULL after the transfer.
    july_nulls = session.scalars(
        select(TimesheetEntry.home_team_id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.user_id == john.id,
            TimesheetEntry.entry_date <= date(2026, 7, 31),
        )
    ).all()
    assert all(value is None for value in july_nulls)

    for day in (date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)):
        session.add(
            TimesheetEntry(
                timesheet_id=sheet_for(day).id,
                entry_date=day,
                hours=Decimal("10"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=customer_b.id,
                project_id=cad_project.id,
                task_type_id=task.id,
            )
        )
    session.commit()

    sept_sheet = sheet_for(date(2026, 9, 7))
    np_resp = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": str(sept_sheet.id),
            "work_category": "non_productive",
            "non_productive_code_id": str(training.id),
            "entry_date": "2026-09-07",
            "hours": "5",
            "description": "Training after transfer",
        },
    )
    assert np_resp.status_code == 201, np_resp.text
    assert np_resp.json()["home_team_id"] == str(cad.id)

    later_mold = TimesheetEntry(
        timesheet_id=sheet_for(date(2026, 9, 11)).id,
        entry_date=date(2026, 9, 11),
        hours=Decimal("8"),
        work_category=WorkCategory.productive,
        is_billable=True,
        customer_id=IDS["customer"],
        project_id=mold_project.id,
        task_type_id=task.id,
    )
    session.add(later_mold)
    session.flush()
    stamp_home_team_on_entry(session, later_mold)
    session.commit()
    assert later_mold.home_team_id == cad.id
    assert work_context_team_id(later_mold, mold_project) == mold.id

    return {
        "mold": mold,
        "cad": cad,
        "john": john,
        "leader": leader,
        "mold_project": mold_project,
        "cad_project": cad_project,
        "customer_b": customer_b,
        "later_mold": later_mold,
    }


def _hours_for(rows, user_id: UUID, team_id: UUID) -> tuple[float, float]:
    match = next(
        (row for row in rows if row.user_id == user_id and row.team_id == team_id),
        None,
    )
    if match is None:
        return 0.0, 0.0
    return float(match.non_productive_hours), float(match.productive_hours)


def test_mold_to_cad_training_and_customer_hours_stay_on_historical_teams(client, session):
    ctx = _seed_mold_cad_transfer(session, client)
    mold, cad, john = ctx["mold"], ctx["cad"], ctx["john"]
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None

    yearly_mold = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="yearly-timesheet",
        anchor=date(2026, 9, 1),
        team_id=mold.id,
    )
    yearly_cad = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="yearly-timesheet",
        anchor=date(2026, 9, 1),
        team_id=cad.id,
    )
    np_mold, prod_mold = _hours_for(yearly_mold.designers, john.id, mold.id)
    np_cad, prod_cad = _hours_for(yearly_cad.designers, john.id, cad.id)
    assert np_mold == 10.0
    assert prod_mold == 100.0
    assert np_cad == 5.0
    # 30h CAD project + 8h post-transfer Mold project booked while on CAD
    assert prod_cad == 38.0

    org = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="yearly-timesheet",
        anchor=date(2026, 9, 1),
    )
    np_org_mold, prod_org_mold = _hours_for(org.designers, john.id, mold.id)
    np_org_cad, prod_org_cad = _hours_for(org.designers, john.id, cad.id)
    assert (np_org_mold, prod_org_mold) == (10.0, 100.0)
    assert (np_org_cad, prod_org_cad) == (5.0, 38.0)

    mold_summary = next(row for row in yearly_mold.designers if row.user_id == john.id)
    assert mold_summary.team_id == mold.id

    mold_eng = build_engineering_report(
        session,
        period_type="yearly",
        anchor=date(2026, 9, 1),
        scope=resolve_report_scope(session, admin, team_id=mold.id),
    )
    customer_a = next(
        row for row in mold_eng.customer_summary if row.customer_id == IDS["customer"]
    )
    assert float(customer_a.productive_hours) == 100.0

    cad_eng = build_engineering_report(
        session,
        period_type="yearly",
        anchor=date(2026, 9, 1),
        scope=resolve_report_scope(session, admin, team_id=cad.id),
    )
    customer_b = next(
        row for row in cad_eng.customer_summary if row.customer_id == ctx["customer_b"].id
    )
    assert float(customer_b.productive_hours) == 30.0
    customer_a_on_cad = next(
        (row for row in cad_eng.customer_summary if row.customer_id == IDS["customer"]),
        None,
    )
    assert customer_a_on_cad is None or float(customer_a_on_cad.productive_hours) == 8.0

    cad_only = build_designer_team_timesheet(
        session,
        current_user=ctx["leader"],
        report_id="yearly-timesheet",
        anchor=date(2026, 9, 1),
        team_id=cad.id,
    )
    cad_np, cad_prod = _hours_for(cad_only.designers, john.id, cad.id)
    assert cad_np == 5.0
    assert cad_prod == 38.0
    assert all(row.team_id != mold.id for row in cad_only.designers if row.user_id == john.id)
    assert all(row.tool_number != "MOLD-A-100" for row in cad_only.projects)

    july_cad = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=date(2026, 7, 1),
        team_id=cad.id,
    )
    assert _hours_for(july_cad.designers, john.id, cad.id) == (0.0, 0.0)

    outbound = [
        row
        for row in yearly_cad.cross_team_hours
        if row.project_id == ctx["mold_project"].id
    ]
    assert outbound
    assert float(sum((row.hours for row in outbound), Decimal("0"))) == 8.0
    assert all(row.home_team_id == cad.id for row in outbound)
    assert all(row.project_team_id == mold.id for row in outbound)


def test_existing_null_snapshots_are_not_rewritten_when_live_team_changes(client, session):
    ctx = _seed_mold_cad_transfer(session, client)
    john = ctx["john"]
    values = session.scalars(
        select(TimesheetEntry.home_team_id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.user_id == john.id,
            TimesheetEntry.entry_date == date(2026, 7, 6),
        )
    ).all()
    assert values == [None]
