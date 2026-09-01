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


def test_designer_timesheet_includes_draft_excludes_rejected(session):
    team, week_start = _seed_timesheet_week(session)
    designer = session.get(User, IDS["user_binil"])
    assert designer
    draft_sheet = Timesheet(
        user_id=designer.id,
        week_start=date(2026, 7, 13),
        status=TimesheetStatus.draft,
    )
    rejected_sheet = Timesheet(
        user_id=designer.id,
        week_start=date(2026, 7, 20),
        status=TimesheetStatus.rejected,
    )
    session.add_all([draft_sheet, rejected_sheet])
    session.flush()
    session.add_all(
        [
            TimesheetEntry(
                timesheet_id=draft_sheet.id,
                entry_date=date(2026, 7, 13),
                hours=Decimal("5"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=IDS["project"],
            ),
            TimesheetEntry(
                timesheet_id=rejected_sheet.id,
                entry_date=date(2026, 7, 20),
                hours=Decimal("9"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=IDS["project"],
            ),
        ]
    )
    session.commit()

    admin = session.get(User, IDS["user_admin"])
    assert admin
    payload = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=date(2026, 7, 1),
        team_id=team.id,
    )
    binil = next(row for row in payload.designers if row.user_id == IDS["user_binil"])
    # Seeded approved 8h + draft 5h; rejected 9h must not count.
    assert float(binil.total_hours) == 13.0


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
    assert workbook.sheetnames == [
        "Designer Hours by Team",
        "Project Hours",
        "Cross-Team Hours",
        "Utilization Summary",
    ]


def test_omit_customer_column_for_customer_filter(session):
    team, week_start = _seed_timesheet_week(session)
    admin = session.get(User, IDS["user_admin"])
    assert admin
    payload = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=week_start.replace(day=1),
        customer_id=IDS["customer"],
        team_id=team.id,
    )
    assert payload.include_customer_columns is False
    workbook = load_workbook(
        filename=__import__("io").BytesIO(generate_designer_team_timesheet_excel(payload))
    )
    designers = workbook["Designer Hours by Team"]
    header_row = next(
        row
        for row in designers.iter_rows(min_row=1, max_row=40, values_only=True)
        if row and str(row[0]).upper() == "TEAM"
    )
    assert "Customers" not in header_row and "CUSTOMERS" not in header_row
    assert "Projects" in header_row or "PROJECTS" in header_row

    projects = workbook["Project Hours"]
    project_header = next(
        row
        for row in projects.iter_rows(min_row=1, max_row=40, values_only=True)
        if row and str(row[0]).upper().startswith("TOOL")
    )
    assert "Customer" not in project_header and "CUSTOMER" not in project_header


def test_omit_customer_column_for_retainer_team(session):
    from app.models.enums import TeamBillingMode, WorkingModelCode
    from app.models.finance import TeamCommercialTerms
    from app.models.models import WorkingModel

    team, week_start = _seed_timesheet_week(session)
    admin = session.get(User, IDS["user_admin"])
    assert admin
    model = WorkingModel(
        id=uuid.uuid4(),
        code=f"ret_ts_{uuid.uuid4().hex[:6]}",
        strategy_key=WorkingModelCode.retainer,
        name="Retainer Timesheet",
        is_active=True,
        is_archived=False,
    )
    session.add(model)
    session.flush()
    session.add(
        TeamCommercialTerms(
            team_id=team.id,
            working_model_id=model.id,
            billing_mode=TeamBillingMode.subscription,
            customer_fee_amount=Decimal("5000"),
            currency_code="INR",
            base_fee_inr=Decimal("5000"),
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
    )
    session.commit()

    payload = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="monthly-timesheet",
        anchor=week_start.replace(day=1),
        team_id=team.id,
    )
    assert payload.include_customer_columns is False
    workbook = load_workbook(
        filename=__import__("io").BytesIO(generate_designer_team_timesheet_excel(payload))
    )
    designers = workbook["Designer Hours by Team"]
    header_row = next(
        row
        for row in designers.iter_rows(min_row=1, max_row=40, values_only=True)
        if row and str(row[0]).upper() == "TEAM"
    )
    assert "Customers" not in header_row and "CUSTOMERS" not in header_row


def test_keep_customer_column_for_non_retainer_team_without_customer(session):
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
    assert payload.include_customer_columns is True
    workbook = load_workbook(
        filename=__import__("io").BytesIO(generate_designer_team_timesheet_excel(payload))
    )
    designers = workbook["Designer Hours by Team"]
    header_row = next(
        row
        for row in designers.iter_rows(min_row=1, max_row=40, values_only=True)
        if row and str(row[0]).upper() == "TEAM"
    )
    assert "CUSTOMERS" in header_row


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
