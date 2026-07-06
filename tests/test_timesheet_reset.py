from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from app.models.models import (
    Project,
    Timesheet,
    TimesheetEntry,
    TimesheetEntryDeletionLog,
    TimesheetImportHistory,
)
from tests.conftest import login


def _seed_timesheet_entry(client, auth_headers):
    timesheet = client.post(
        "/api/v1/timesheets",
        json={
            "user_id": str(client.user_id),
            "week_start": "2026-06-16",
            "status": "draft",
        },
        headers=auth_headers,
    ).json()
    entry = client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet["id"],
            "work_category": "productive",
            "project_id": client.project_id,
            "task_type_id": client.task_type_id,
            "entry_date": "2026-06-17",
            "hours": 4,
        },
        headers=auth_headers,
    ).json()
    return timesheet, entry


def test_reset_requires_delete_confirmation(client, auth_headers):
    response = client.post(
        "/api/v1/imports/historical-timesheets/reset",
        json={"confirmation": "delete"},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_reset_deletes_timesheets_and_recalculates_projects(
    client, auth_headers, test_session_factory
):
    _seed_timesheet_entry(client, auth_headers)
    project_before = client.get(
        f"/api/v1/projects/{client.project_id}",
        headers=auth_headers,
    ).json()
    assert Decimal(str(project_before["actual_hours"])) == Decimal("4")

    response = client.post(
        "/api/v1/imports/historical-timesheets/reset",
        json={"confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["timesheets_deleted"] >= 1
    assert body["entries_deleted"] >= 1
    assert "Before_Historical_Reimport_" in body["backup_path"]

    listed = client.get(
        "/api/v1/timesheet-entries",
        params={"entry_date_from": "2026-06-17", "entry_date_to": "2026-06-17"},
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert listed.json() == []

    project_after = client.get(
        f"/api/v1/projects/{client.project_id}",
        headers=auth_headers,
    ).json()
    assert Decimal(str(project_after["actual_hours"])) == Decimal("0")

    with test_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(TimesheetEntry)) == 0
        assert db.scalar(select(func.count()).select_from(Timesheet)) == 0
        assert db.scalar(select(func.count()).select_from(TimesheetImportHistory)) == 0
        assert db.scalar(select(func.count()).select_from(TimesheetEntryDeletionLog)) == 0


def test_non_admin_cannot_reset(client, test_session_factory):
    headers = login(client, "binil@prosohm.com")
    response = client.post(
        "/api/v1/imports/historical-timesheets/reset",
        json={"confirmation": "DELETE"},
        headers=headers,
    )
    assert response.status_code == 403
