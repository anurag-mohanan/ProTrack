"""Customer timesheet pack — Prosohm-style weekly/monthly customer report."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.enums import TimesheetStatus, WorkCategory
from app.models.models import Timesheet, TimesheetEntry
from app.services.reporting.customer_timesheet_pack import build_customer_timesheet_pack
from app.services.reporting.excel.customer_timesheet import generate_customer_timesheet_excel
from app.services.reporting.registry import get_report_definition
from tests.conftest import IDS, login


def _seed_customer_week_entries(session, *, status=TimesheetStatus.approved, set_entry_customer=True):
    week_start = date(2026, 6, 8)  # Monday
    timesheet = Timesheet(
        user_id=IDS["user_binil"],
        week_start=week_start,
        status=status,
    )
    session.add(timesheet)
    session.flush()
    session.add_all(
        [
            TimesheetEntry(
                timesheet_id=timesheet.id,
                entry_date=week_start,
                hours=Decimal("8"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"] if set_entry_customer else None,
                project_id=IDS["project"],
                description="Mold design",
            ),
            TimesheetEntry(
                timesheet_id=timesheet.id,
                entry_date=week_start + timedelta(days=1),
                hours=Decimal("4"),
                work_category=WorkCategory.non_productive,
                is_billable=False,
                customer_id=IDS["customer"] if set_entry_customer else None,
                description="Training",
            ),
        ]
    )
    session.commit()
    return week_start


def test_customer_timesheet_pack_in_catalog():
    definition = get_report_definition("customer-timesheet-pack")
    assert definition is not None
    assert definition.category == "customers"
    assert "weekly" in definition.supported_periods


def test_build_customer_timesheet_pack(session):
    week_start = _seed_customer_week_entries(session)
    admin = session.get(__import__("app.models.models", fromlist=["User"]).User, IDS["user_admin"])
    pack = build_customer_timesheet_pack(
        session,
        customer_id=IDS["customer"],
        current_user=admin,
        period_type="weekly",
        anchor=week_start,
    )
    assert pack.customer_name
    assert pack.week_number == week_start.isocalendar()[1]
    assert pack.working_hours_target > 0
    assert len(pack.associates) == 1
    assert pack.associates[0].productive_hours == Decimal("8.00")
    assert pack.associates[0].non_productive_hours == Decimal("4.00")
    assert pack.associates[0].total_hours == Decimal("12.00")
    assert any(row.tool_number for row in pack.tools)
    content = generate_customer_timesheet_excel(pack)
    assert content[:2] == b"PK"


def test_customer_timesheet_pack_api_preview(client, session):
    week_start = _seed_customer_week_entries(session)
    headers = login(client, "admin@prosohm.com")
    response = client.get(
        "/api/v1/reports/customer-timesheet-pack/preview",
        headers=headers,
        params={
            "customer_id": str(IDS["customer"]),
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "WEEKLY TIME SHEET"
    assert len(body["associates"]) >= 1


def test_customer_timesheet_pack_api_export(client, session):
    week_start = _seed_customer_week_entries(session)
    headers = login(client, "pm@prosohm.com")
    response = client.get(
        "/api/v1/reports/customer-timesheet-pack/export.xlsx",
        headers=headers,
        params={
            "customer_id": str(IDS["customer"]),
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.content[:2] == b"PK"
    disposition = response.headers.get("content-disposition", "")
    assert disposition.startswith("attachment;")
    assert "PP_" in disposition
    assert "_Week_" in disposition
    assert week_start.isoformat() in disposition


def test_designer_forbidden_from_customer_timesheet_pack(client, session):
    week_start = _seed_customer_week_entries(session)
    headers = login(client, "binil@prosohm.com")
    response = client.get(
        "/api/v1/reports/customer-timesheet-pack/preview",
        headers=headers,
        params={
            "customer_id": str(IDS["customer"]),
            "period_type": "weekly",
            "anchor": week_start.isoformat(),
        },
    )
    assert response.status_code == 403


def test_customer_timesheet_pack_includes_draft_hours(session):
    week_start = _seed_customer_week_entries(session, status=TimesheetStatus.draft)
    admin = session.get(__import__("app.models.models", fromlist=["User"]).User, IDS["user_admin"])
    pack = build_customer_timesheet_pack(
        session,
        customer_id=IDS["customer"],
        current_user=admin,
        period_type="weekly",
        anchor=week_start,
    )
    assert pack.total_hours == Decimal("12.00")
    assert pack.associates[0].utilization_percent > 0


def test_customer_timesheet_pack_matches_project_customer_when_entry_customer_null(session):
    week_start = _seed_customer_week_entries(session, set_entry_customer=False)
    admin = session.get(__import__("app.models.models", fromlist=["User"]).User, IDS["user_admin"])
    pack = build_customer_timesheet_pack(
        session,
        customer_id=IDS["customer"],
        current_user=admin,
        period_type="weekly",
        anchor=week_start,
    )
    # Productive row has project → customer; NP row without project/customer is excluded.
    assert pack.associates[0].productive_hours == Decimal("8.00")
    assert pack.total_productive_hours == Decimal("8.00")
    assert any(row.tool_number for row in pack.tools)
