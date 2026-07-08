from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.models.models import TimesheetEntry, TimesheetEntryDeletionLog


from tests.conftest import login


def _create_draft_entry(client, auth_headers, user_id=None):
    owner_id = user_id or str(client.user_id)
    timesheet = client.post(
        "/api/v1/timesheets",
        json={
            "user_id": owner_id,
            "week_start": "2026-06-16",
            "status": "draft",
        },
        headers=auth_headers,
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
            "description": "Design work",
        },
        headers=auth_headers,
    )
    assert entry.status_code == 201
    return entry.json()


def test_soft_delete_creates_audit_log_and_hides_entry(client, auth_headers, test_session_factory):
    entry = _create_draft_entry(client, auth_headers)
    entry_id = entry["id"]

    deleted = client.delete(f"/api/v1/timesheet-entries/{entry_id}", headers=auth_headers)
    assert deleted.status_code == 204

    listed = client.get(
        "/api/v1/timesheet-entries",
        params={"entry_date_from": "2026-06-17", "entry_date_to": "2026-06-17"},
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert all(row["id"] != entry_id for row in listed.json())

    with test_session_factory() as db:
        stored = db.get(TimesheetEntry, UUID(entry_id))
        assert stored is not None
        assert stored.is_deleted is True
        assert stored.delete_reason == "User Deleted"
        logs = db.scalars(
            select(TimesheetEntryDeletionLog).where(
                TimesheetEntryDeletionLog.entry_id == UUID(entry_id)
            )
        ).all()
        assert len(logs) == 1
        assert logs[0].reason == "User Deleted"
        assert Decimal(str(logs[0].hours)) == Decimal("8")


def test_admin_can_restore_deleted_entry(client, auth_headers, test_session_factory):
    entry = _create_draft_entry(client, auth_headers)
    entry_id = entry["id"]

    deleted = client.delete(f"/api/v1/timesheet-entries/{entry_id}", headers=auth_headers)
    assert deleted.status_code == 204

    restored = client.post(
        f"/api/v1/timesheet-entries/{entry_id}/restore",
        headers=auth_headers,
    )
    assert restored.status_code == 200
    assert restored.json()["id"] == entry_id

    listed = client.get(
        "/api/v1/timesheet-entries",
        params={"entry_date_from": "2026-06-17", "entry_date_to": "2026-06-17"},
        headers=auth_headers,
    )
    assert any(row["id"] == entry_id for row in listed.json())

    with test_session_factory() as db:
        stored = db.get(TimesheetEntry, UUID(entry_id))
        assert stored is not None
        assert stored.is_deleted is False
        log = db.scalar(
            select(TimesheetEntryDeletionLog).where(
                TimesheetEntryDeletionLog.entry_id == UUID(entry_id)
            )
        )
        assert log is not None
        assert log.restored_at is not None


def test_can_edit_and_delete_after_submit(client, auth_headers):
    """Submitting a timesheet must NOT lock it. Status only drives workflow."""
    entry = _create_draft_entry(client, auth_headers)
    timesheet_id = entry["timesheet_id"]

    submitted = client.post(
        f"/api/v1/timesheets/{timesheet_id}/submit",
        headers=auth_headers,
    )
    assert submitted.status_code == 200

    updated = client.patch(
        f"/api/v1/timesheet-entries/{entry['id']}",
        json={"hours": 6},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert float(updated.json()["hours"]) == 6

    deleted = client.delete(f"/api/v1/timesheet-entries/{entry['id']}", headers=auth_headers)
    assert deleted.status_code == 204


def test_can_edit_after_approve(client, auth_headers):
    """Approved timesheets remain editable so users can correct entries."""
    entry = _create_draft_entry(client, auth_headers)
    timesheet_id = entry["timesheet_id"]

    submitted = client.post(
        f"/api/v1/timesheets/{timesheet_id}/submit",
        headers=auth_headers,
    )
    assert submitted.status_code == 200

    approved = client.post(
        f"/api/v1/timesheets/{timesheet_id}/approve",
        json={"comments": "Looks good"},
        headers=auth_headers,
    )
    assert approved.status_code == 200

    updated = client.patch(
        f"/api/v1/timesheet-entries/{entry['id']}",
        json={"hours": 4},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert float(updated.json()["hours"]) == 4


def test_non_owner_cannot_edit_entry(client, auth_headers):
    entry = _create_draft_entry(client, auth_headers)
    other_headers = login(client, "binil@prosohm.com")

    updated = client.patch(
        f"/api/v1/timesheet-entries/{entry['id']}",
        json={"hours": 6},
        headers=other_headers,
    )
    assert updated.status_code == 403

    deleted = client.delete(
        f"/api/v1/timesheet-entries/{entry['id']}",
        headers=other_headers,
    )
    assert deleted.status_code == 403
