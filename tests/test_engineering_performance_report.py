"""Engineering Performance report: periods, completed-only rule, KPIs, export."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from app.models.enums import ExecutionStatus, TimesheetStatus, WorkCategory
from app.models.models import Project, Timesheet, TimesheetEntry
from app.services.reporting.periods import financial_period_bounds
from tests.conftest import IDS, login


def test_financial_year_periods_follow_april_to_march():
    start, end, label = financial_period_bounds("quarterly", anchor=date(2026, 10, 19), fy_start_month=4)
    assert (start, end) == (date(2026, 10, 1), date(2026, 12, 31))
    assert label.startswith("Q3 FY 2026-27")
    start, end, _ = financial_period_bounds("quarterly", anchor=date(2027, 2, 10), fy_start_month=4)
    assert (start, end) == (date(2027, 1, 1), date(2027, 3, 31))
    start, end, label = financial_period_bounds("yearly", anchor=date(2027, 2, 10), fy_start_month=4)
    assert (start, end) == (date(2026, 4, 1), date(2027, 3, 31))
    assert "FY 2026-27" in label
    start, end, _ = financial_period_bounds("weekly", anchor=date(2026, 10, 21))
    assert (start, end) == (date(2026, 10, 19), date(2026, 10, 25))
    start, end, _ = financial_period_bounds("monthly", anchor=date(2026, 2, 14))
    assert (start, end) == (date(2026, 2, 1), date(2026, 2, 28))


def _project(session, *, code: str, status: ExecutionStatus, completed_at: datetime | None,
             quoted: str = "100", due: date | None = None, deleted: bool = False) -> Project:
    row = Project(
        id=uuid.uuid4(),
        tool_number=f"T-{code}",
        part_description=f"Part {code}",
        customer_id=IDS["customer"],
        customer_contact_id=IDS["contact"],
        design_leader_id=IDS["user_anurag"],
        designer_id=IDS["user_binil"],
        stream_id=IDS["stream"],
        code=code,
        quoted_hours=Decimal(quoted),
        actual_hours=Decimal("0"),
        due_date=due,
        execution_status=status,
        completed_at=completed_at,
        is_deleted=deleted,
    )
    session.add(row)
    return row


def _book_hours(session, project: Project, hours: str, day: date) -> None:
    """Book ``hours`` as 8-hour days starting at ``day``."""
    from sqlalchemy import select

    remaining = Decimal(hours)
    current = day
    while remaining > 0:
        chunk = min(remaining, Decimal("8"))
        week_start = current - timedelta(days=current.weekday())
        sheet = session.scalar(
            select(Timesheet).where(
                Timesheet.user_id == IDS["user_binil"], Timesheet.week_start == week_start
            )
        )
        if sheet is None:
            sheet = Timesheet(
                id=uuid.uuid4(),
                user_id=IDS["user_binil"],
                week_start=week_start,
                status=TimesheetStatus.approved,
            )
            session.add(sheet)
            session.flush()
        session.add(
            TimesheetEntry(
                timesheet_id=sheet.id,
                entry_date=current,
                hours=chunk,
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=project.id,
            )
        )
        session.flush()
        remaining -= chunk
        current += timedelta(days=1)


def _seed_period(session):
    in_period_on_time = _project(
        session, code="EP-1", status=ExecutionStatus.completed,
        completed_at=datetime(2025, 5, 10, 12), due=date(2025, 5, 15),
    )
    in_period_late = _project(
        session, code="EP-2", status=ExecutionStatus.completed,
        completed_at=datetime(2025, 5, 20, 9), quoted="50", due=date(2025, 5, 12),
    )
    _project(session, code="EP-3", status=ExecutionStatus.completed, completed_at=datetime(2025, 7, 1, 9))
    _project(session, code="EP-4", status=ExecutionStatus.cancelled, completed_at=datetime(2025, 5, 11, 9))
    _project(session, code="EP-5", status=ExecutionStatus.currently_being_worked_on, completed_at=None)
    _project(session, code="EP-6", status=ExecutionStatus.completed, completed_at=None)
    _project(session, code="EP-7", status=ExecutionStatus.completed,
             completed_at=datetime(2025, 5, 12, 9), deleted=True)
    session.flush()
    _book_hours(session, in_period_on_time, "120", date(2025, 4, 2))
    _book_hours(session, in_period_late, "40", date(2025, 5, 2))
    session.commit()


def test_only_completed_projects_with_completion_date_in_period_count(client, session):
    _seed_period(session)
    response = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "monthly", "anchor": "2025-05-15"},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    codes = sorted(row["code"] for row in body["projects"])
    assert codes == ["EP-1", "EP-2"]
    summary = body["summary"]
    assert summary["projects_completed"] == 2
    assert summary["planned_hours"] == 150.0
    assert summary["actual_hours"] == 160.0
    assert summary["variance_hours"] == 10.0
    assert summary["variance_percent"] == 6.67
    assert summary["on_time_projects"] == 1
    assert summary["late_projects"] == 1
    assert summary["on_time_rate"] == 50.0
    assert summary["average_days_late"] == 8.0
    late = next(row for row in body["projects"] if row["code"] == "EP-2")
    assert late["reference_source"] == "legacy_due_date"
    assert late["days_late"] == 8
    warnings = {w["code"]: w for w in body["warnings"]}
    assert "EP-6" in warnings["completed_without_date"]["project_codes"]
    assert body["empty_message"] is None

    # Breakdowns reconcile with the summary.
    for breakdown in body["breakdowns"]:
        assert sum(row["projects"] for row in breakdown["rows"]) == 2, breakdown["dimension"]
        assert round(sum(row["actual_hours"] for row in breakdown["rows"]), 2) == 160.0
        assert round(sum(row["planned_hours"] for row in breakdown["rows"]), 2) == 150.0


def test_empty_period_returns_message_not_error(client, session):
    response = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "custom", "start_date": "2019-01-01", "end_date": "2019-01-31"},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["projects"] == []
    assert body["summary"]["projects_completed"] == 0
    assert body["empty_message"] == "No projects were completed during the selected period."


def test_invalid_periods_are_rejected(client):
    bad_range = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "custom", "start_date": "2025-02-01", "end_date": "2025-01-01"},
        headers=client.auth_headers,
    )
    assert bad_range.status_code == 422
    missing = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "custom"},
        headers=client.auth_headers,
    )
    assert missing.status_code == 422
    unknown = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "fortnightly"},
        headers=client.auth_headers,
    )
    assert unknown.status_code == 422


def test_export_matches_screen_and_requires_permission(client, session):
    _seed_period(session)
    params = {"period_type": "yearly", "anchor": "2025-06-01"}
    screen = client.get(
        "/api/v1/reports/engineering-performance", params=params, headers=client.auth_headers
    ).json()
    response = client.get(
        "/api/v1/reports/engineering-performance/export.xlsx",
        params=params,
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == [
        "Summary", "Stage Performance", "Breakdowns", "Project Details", "Definitions",
    ]
    details = workbook["Project Details"]
    codes = [details.cell(row=r, column=1).value for r in range(2, 2 + len(screen["projects"]))]
    assert sorted(codes) == sorted(row["code"] for row in screen["projects"])
    total_row = 2 + len(screen["projects"])
    assert details.cell(row=total_row, column=23).value == screen["summary"]["actual_hours"]
    assert details.cell(row=total_row, column=21).value == screen["summary"]["planned_hours"]

    read_only = login(client, "readonly@prosohm.com")
    forbidden = client.get(
        "/api/v1/reports/engineering-performance/export.xlsx", params=params, headers=read_only
    )
    assert forbidden.status_code == 403


def test_report_access_follows_reports_module_not_role_names(client, session):
    """Root cause of "Unable to load data": UI allowed Reports by module, API by role list."""
    from app.models.models import User

    designer_headers = login(client, "binil@prosohm.com")
    denied = client.get("/api/v1/reports/catalog", headers=designer_headers)
    assert denied.status_code == 403
    assert "Reports" in denied.json()["detail"]

    designer = session.get(User, IDS["user_binil"])
    designer.module_access = '["dashboard", "projects", "timesheets", "reports"]'
    session.commit()
    granted = client.get("/api/v1/reports/catalog", headers=designer_headers)
    assert granted.status_code == 200, granted.text
    report = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "monthly"},
        headers=designer_headers,
    )
    assert report.status_code == 200, report.text


def test_template_lookup_and_fy_start_available_to_report_viewers(client):
    viewer = login(client, "readonly@prosohm.com")
    templates = client.get("/api/v1/lookups/project-templates", headers=viewer)
    assert templates.status_code == 200, templates.text
    families = [row["template_family_id"] for row in templates.json()]
    assert len(families) == len(set(families))
    public = client.get("/api/v1/settings/public").json()
    assert 1 <= public["company"]["financial_year_start_month"] <= 12
