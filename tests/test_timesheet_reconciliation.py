"""Tests for the central timesheet reconciliation service and admin endpoint."""

from decimal import Decimal
from types import SimpleNamespace

from app.models.enums import WorkCategory
from app.services.timesheet_reconciliation_service import categorize_entries


def _entry(**kwargs):
    defaults = dict(
        is_deleted=False,
        hours=Decimal("8"),
        is_billable=True,
        work_category=WorkCategory.productive,
        leave_count=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_categorize_splits_productive_np_and_leave():
    entries = [
        _entry(hours=Decimal("8"), work_category=WorkCategory.productive, is_billable=True),
        _entry(hours=Decimal("2"), work_category=WorkCategory.productive, is_billable=False),
        _entry(hours=Decimal("3"), work_category=WorkCategory.non_productive, leave_count=None, is_billable=False),
        _entry(hours=Decimal("0"), work_category=WorkCategory.non_productive, leave_count=1, is_billable=False),
    ]
    breakdown = categorize_entries(entries)
    assert breakdown.productive_hours == Decimal("10")
    assert breakdown.non_productive_hours == Decimal("3")
    assert breakdown.worked_hours == Decimal("13")  # leave excluded
    assert breakdown.billable_hours == Decimal("8")
    assert breakdown.leave_days == Decimal("1")
    assert breakdown.leave_entries == 1


def test_categorize_ignores_deleted_entries():
    entries = [
        _entry(hours=Decimal("8"), is_deleted=True),
        _entry(hours=Decimal("5"), is_deleted=False),
    ]
    breakdown = categorize_entries(entries)
    assert breakdown.worked_hours == Decimal("5")
    assert breakdown.entry_count == 1


def _create_entry(client, headers, user_id):
    timesheet = client.post(
        "/api/v1/timesheets",
        json={"user_id": user_id, "week_start": "2026-06-16", "status": "draft"},
        headers=headers,
    )
    assert timesheet.status_code == 201
    entry = client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet.json()["id"],
            "work_category": "productive",
            "project_id": client.project_id,
            "task_type_id": client.task_type_id,
            "entry_date": "2026-06-17",
            "hours": 8,
        },
        headers=headers,
    )
    assert entry.status_code == 201
    return entry.json()


def test_recalculate_endpoint_returns_report(client, auth_headers):
    _create_entry(client, auth_headers, str(client.user_id))

    response = client.post("/api/v1/admin/timesheets/recalculate", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    for key in (
        "users_checked",
        "months_recalculated",
        "entries_scanned",
        "projects_recalculated",
        "errors_fixed",
        "warnings",
        "execution_ms",
    ):
        assert key in body
    assert body["entries_scanned"] >= 1


def test_recalculate_endpoint_requires_admin(client):
    from tests.conftest import login

    designer_headers = login(client, "binil@prosohm.com")
    response = client.post(
        "/api/v1/admin/timesheets/recalculate", headers=designer_headers
    )
    assert response.status_code == 403
