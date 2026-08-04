"""Individual designer timesheet Excel export."""

from datetime import date
from decimal import Decimal

from app.models.enums import TimesheetStatus, WorkCategory
from app.models.models import Timesheet, TimesheetEntry, User
from app.services.reporting.excel.designer_individual_timesheet import (
    generate_designer_individual_timesheet_excel,
)
from tests.conftest import IDS


def test_generate_designer_individual_timesheet_excel(session):
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None

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
            hours=Decimal("7"),
            work_category=WorkCategory.productive,
            is_billable=True,
            customer_id=IDS["customer"],
            project_id=IDS["project"],
            description="assembly",
        )
    )
    session.commit()

    content, filename = generate_designer_individual_timesheet_excel(
        session,
        user_id=designer.id,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        period_label="July 2026",
    )
    assert content[:2] == b"PK"
    assert "2026-07-01" in filename
    assert "2026-07-31" in filename


def test_export_designer_timesheet_endpoint(client, auth_headers, session):
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.requires_timesheet = True
    session.commit()

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
            hours=Decimal("4"),
            work_category=WorkCategory.productive,
            is_billable=True,
            customer_id=IDS["customer"],
            project_id=IDS["project"],
        )
    )
    session.commit()

    response = client.get(
        "/api/v1/timesheets/export/designer.xlsx",
        params={
            "user_id": str(designer.id),
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_label": "July 2026",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.content[:2] == b"PK"
    assert "attachment" in response.headers.get("content-disposition", "")
