"""Simplified timesheet reports — designer hours by team + project hours to date."""

from datetime import date
from decimal import Decimal
import uuid

from openpyxl import load_workbook

from app.models.enums import TeamRelationshipType, TimesheetStatus, WorkCategory
from app.models.models import Team, TeamMember, Timesheet, TimesheetEntry, User
from app.services.reporting.designer_team_timesheet import (
    build_designer_team_timesheet,
    is_designer_team_timesheet_report,
)
from app.services.reporting.excel.designer_team_timesheet import generate_designer_team_timesheet_excel
from app.services.reporting.registry import get_report_catalog, get_report_definition
from tests.conftest import IDS, login


def _seed_timesheet_week(session):
    team = Team(id=uuid.uuid4(), name="Timesheet Team", is_active=True)
    session.add(team)
    session.flush()
    designer = session.get(User, IDS["user_binil"])
    leader = session.get(User, IDS["user_anurag"])
    assert designer and leader
    designer.team_id = team.id
    leader.team_id = team.id
    project = session.get(__import__("app.models.models", fromlist=["Project"]).Project, IDS["project"])
    if project is not None:
        project.team_id = team.id
    session.add_all(
        [
            TeamMember(
                team_id=team.id,
                user_id=leader.id,
                relationship_type=TeamRelationshipType.team_leader,
                is_primary=True,
            ),
            TeamMember(
                team_id=team.id,
                user_id=designer.id,
                relationship_type=TeamRelationshipType.member,
                is_primary=True,
            ),
        ]
    )
    week_start = date(2026, 7, 6)
    timesheet = Timesheet(
        user_id=designer.id,
        week_start=week_start,
        status=TimesheetStatus.approved,
    )
    session.add(timesheet)
    session.flush()
    session.add(
        TimesheetEntry(
            timesheet_id=timesheet.id,
            entry_date=week_start,
            hours=Decimal("8"),
            work_category=WorkCategory.productive,
            is_billable=True,
            customer_id=IDS["customer"],
            project_id=IDS["project"],
        )
    )
    session.commit()
    return team, week_start


def test_timesheet_catalog_only_period_reports():
    catalog = get_report_catalog()
    timesheet_ids = {r.id for r in catalog.reports if r.category == "timesheets"}
    assert timesheet_ids == {
        "weekly-timesheet",
        "monthly-timesheet",
        "quarterly-timesheet",
        "yearly-timesheet",
    }
    assert get_report_definition("detailed-entries") is None
    assert get_report_definition("designer-summary") is None
    assert is_designer_team_timesheet_report("monthly-timesheet")


def test_build_monthly_timesheet_has_designers_and_projects(session):
    team, week_start = _seed_timesheet_week(session)
    admin = session.get(User, IDS["user_admin"])
    assert admin
    payload = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="weekly-timesheet",
        anchor=week_start,
        team_id=team.id,
    )
    assert payload.period.period_type == "weekly"
    assert payload.designer_count >= 1
    assert any(row.user_id == IDS["user_binil"] for row in payload.designers)
    assert payload.project_count >= 1
    assert float(payload.total_designer_hours) >= 8


def test_timesheet_excel_has_two_sheets(session):
    team, week_start = _seed_timesheet_week(session)
    admin = session.get(User, IDS["user_admin"])
    assert admin
    payload = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=week_start.replace(day=1),
        team_id=team.id,
    )
    content = generate_designer_team_timesheet_excel(payload)
    assert content[:2] == b"PK"
    workbook = load_workbook(filename=__import__("io").BytesIO(content))
    assert workbook.sheetnames == ["Designer Hours by Team", "Project Hours To Date"]


def test_timesheet_preview_api(client, session):
    team, week_start = _seed_timesheet_week(session)
    headers = login(client, "admin@prosohm.com")
    response = client.get(
        "/api/v1/reports/engine/weekly-timesheet/preview",
        headers=headers,
        params={"anchor": week_start.isoformat(), "team_id": str(team.id)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["report_id"] == "weekly-timesheet"
    assert "designers" in body
    assert "projects" in body
    assert "executive" not in body


def test_timesheet_export_api(client, session):
    _, week_start = _seed_timesheet_week(session)
    headers = login(client, "pm@prosohm.com")
    response = client.get(
        "/api/v1/reports/engine/monthly-timesheet/export.xlsx",
        headers=headers,
        params={"anchor": week_start.replace(day=1).isoformat()},
    )
    assert response.status_code == 200, response.text
    assert response.content[:2] == b"PK"


def test_leader_forbidden_foreign_team_on_timesheet(client, session):
    team, week_start = _seed_timesheet_week(session)
    foreign = Team(id=uuid.uuid4(), name="Other Team", is_active=True)
    session.add(foreign)
    session.commit()
    headers = login(client, "anurag@prosohm.com")
    ok = client.get(
        "/api/v1/reports/engine/weekly-timesheet/preview",
        headers=headers,
        params={"anchor": week_start.isoformat(), "team_id": str(team.id)},
    )
    assert ok.status_code == 200, ok.text
    forbidden = client.get(
        "/api/v1/reports/engine/weekly-timesheet/preview",
        headers=headers,
        params={"anchor": week_start.isoformat(), "team_id": str(foreign.id)},
    )
    assert forbidden.status_code == 403
