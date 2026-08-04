"""Month timesheet / entry listing must not silently truncate org-wide data."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.enums import TimesheetStatus, WorkCategory
from app.models.models import Timesheet, TimesheetEntry, User
from tests.conftest import IDS


def _monday_on_or_before(day: date) -> date:
    return day - timedelta(days=day.weekday())


def test_month_timesheet_list_filters_in_sql_not_after_limit(client, session):
    """Regression: old code fetched a global page then filtered by month in Python."""
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    designers = [
        session.get(User, IDS["user_binil"]),
        session.get(User, IDS["user_senior_designer"]),
    ]
    assert all(person is not None for person in designers)

    # Older weeks outside the target month — would consume a global limit page.
    for offset in range(40):
        session.add(
            Timesheet(
                id=uuid4(),
                user_id=designers[offset % 2].id,
                week_start=date(2025, 1, 6) + timedelta(weeks=offset),
                status=TimesheetStatus.approved,
            )
        )

    target_weeks = [
        _monday_on_or_before(date(2026, 7, 6)),
        _monday_on_or_before(date(2026, 7, 13)),
        _monday_on_or_before(date(2026, 7, 20)),
        _monday_on_or_before(date(2026, 7, 27)),
    ]
    for person in designers:
        for week_start in target_weeks:
            session.add(
                Timesheet(
                    id=uuid4(),
                    user_id=person.id,
                    week_start=week_start,
                    status=TimesheetStatus.approved,
                )
            )
    session.commit()

    response = client.get(
        "/api/v1/timesheets",
        params={"month": "2026-07", "limit": 20},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) >= 8
    assert all(row["week_start"].startswith("2026-07") or row["week_start"].startswith("2026-06") for row in rows)
    user_ids = {row["user_id"] for row in rows}
    assert str(designers[0].id) in user_ids
    assert str(designers[1].id) in user_ids


def test_month_entries_support_high_limit_and_pagination(client, session):
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    week_start = _monday_on_or_before(date(2026, 7, 6))
    timesheet = Timesheet(
        id=uuid4(),
        user_id=designer.id,
        week_start=week_start,
        status=TimesheetStatus.approved,
    )
    session.add(timesheet)
    session.flush()

    for day_offset in range(5):
        session.add(
            TimesheetEntry(
                timesheet_id=timesheet.id,
                entry_date=week_start + timedelta(days=day_offset),
                hours=Decimal("8"),
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=IDS["project"],
            )
        )
    session.commit()

    page = client.get(
        "/api/v1/timesheet-entries",
        params={
            "entry_date_from": "2026-07-01",
            "entry_date_to": "2026-07-31",
            "limit": 2000,
        },
        headers=client.auth_headers,
    )
    assert page.status_code == 200, page.text
    assert len(page.json()) >= 5

    first = client.get(
        "/api/v1/timesheet-entries",
        params={
            "entry_date_from": "2026-07-01",
            "entry_date_to": "2026-07-31",
            "user_id": str(designer.id),
            "skip": 0,
            "limit": 2,
        },
        headers=client.auth_headers,
    )
    second = client.get(
        "/api/v1/timesheet-entries",
        params={
            "entry_date_from": "2026-07-01",
            "entry_date_to": "2026-07-31",
            "user_id": str(designer.id),
            "skip": 2,
            "limit": 2,
        },
        headers=client.auth_headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    ids = {row["id"] for row in first.json()} | {row["id"] for row in second.json()}
    assert len(ids) == 4


def test_overview_accepts_explicit_period_range(client, session):
    response = client.get(
        "/api/v1/timesheets/overview",
        params={
            "period_start": "2026-07-01",
            "period_end": "2026-09-30",
        },
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["month_start"] == "2026-07-01"
    assert body["month_end"] == "2026-09-30"
    assert "teams" in body
    assert "users" in body


def test_timesheets_list_by_period_range(client, session):
    response = client.get(
        "/api/v1/timesheets",
        params={
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "limit": 50,
        },
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
