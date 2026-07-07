import io
import time
import uuid
from decimal import Decimal

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.models.models import Project, TimesheetEntry, TimesheetImportHistory
from app.services.historical_timesheet_import_service import (
    ImportContext,
    parse_csv,
    run_timesheet_import,
    save_upload,
)
from app.schemas.historical_timesheet_import import (
    DesignerResolution,
    DesignerResolutionAction,
    DuplicateWeekAction,
)
from tests.conftest import IDS, login


TIMESHEET_HEADERS = ["Date", "Tool No.", "Customer", "Task", "Hours", "Designer"]


def build_timesheet_csv(rows: list[list]) -> bytes:
    lines = [",".join(TIMESHEET_HEADERS)]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    return "\n".join(lines).encode("utf-8")


def build_timesheet_workbook(rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Timesheet"
    sheet.append(TIMESHEET_HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def productive_row():
    return ["2026-06-23", "T-100", "Acme Plastics", "Design", 8, "Binil"]


@pytest.fixture
def sample_csv_bytes(productive_row):
    return build_timesheet_csv([productive_row])


def test_parse_csv(sample_csv_bytes, tmp_path):
    path = tmp_path / "timesheet.csv"
    path.write_bytes(sample_csv_bytes)
    rows = parse_csv(path)
    assert len(rows) == 1
    assert rows[0].tool_number == "T-100"
    assert rows[0].hours == Decimal("8")
    assert rows[0].designer == "Binil"


def test_upload_and_analyze(client, sample_csv_bytes):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("timesheet.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 1
    assert body["ready_rows"] == 1
    assert body["designer"]["detected_name"] == "Binil"
    assert body["designer"]["matched_user_id"] is not None


def test_engineering_manager_forbidden_from_timesheet_import(client, sample_csv_bytes):
    headers = login(client, "pm@prosohm.com")
    response = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("timesheet.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 403


def test_validate_upload(client, sample_csv_bytes):
    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("timesheet.csv", sample_csv_bytes, "text/csv")},
    )
    upload_id = upload.json()["upload_id"]
    response = client.post(
        f"/api/v1/imports/historical-timesheets/upload/{upload_id}/validate",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def _poll_job(client, headers, job_id: str):
    for _ in range(30):
        job_response = client.get(
            f"/api/v1/imports/historical-timesheets/jobs/{job_id}",
            headers=headers,
        )
        job = job_response.json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.1)
    raise AssertionError("Job did not complete")


def test_import_updates_project_hours(client, sample_csv_bytes, test_session_factory):
    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("timesheet.csv", sample_csv_bytes, "text/csv")},
    )
    upload_id = upload.json()["upload_id"]
    matched_user_id = upload.json()["designer"]["matched_user_id"]

    client.post(
        f"/api/v1/imports/historical-timesheets/upload/{upload_id}/resolve",
        headers=headers,
        json={
            "upload_id": upload_id,
            "duplicate_week_action": "merge",
            "designer": {
                "action": "match_existing",
                "user_id": matched_user_id,
            },
        },
    )

    run = client.post(
        "/api/v1/imports/historical-timesheets/run",
        headers=headers,
        json={
            "upload_id": upload_id,
            "dry_run": False,
            "duplicate_week_action": "merge",
            "designer": {
                "action": "match_existing",
                "user_id": matched_user_id,
            },
        },
    )
    assert run.status_code == 200
    job = _poll_job(client, headers, run.json()["job_id"])
    assert job["status"] == "completed"
    assert job["summary"]["rows_imported"] == 1

    session = test_session_factory()
    try:
        project = session.get(Project, IDS["project"])
        assert project is not None
        assert project.actual_hours == Decimal("8.00")
    finally:
        session.close()


def test_duplicate_week_skip(client, sample_csv_bytes, test_session_factory):
    headers = login(client, "admin@prosohm.com")
    session = test_session_factory()
    try:
        matched_user_id = str(IDS["user_binil"])
    finally:
        session.close()

    def run_import(duplicate_action: str):
        upload = client.post(
            "/api/v1/imports/historical-timesheets/upload",
            headers=headers,
            files={"file": ("timesheet.csv", sample_csv_bytes, "text/csv")},
        )
        upload_id = upload.json()["upload_id"]
        run = client.post(
            "/api/v1/imports/historical-timesheets/run",
            headers=headers,
            json={
                "upload_id": upload_id,
                "dry_run": False,
                "duplicate_week_action": duplicate_action,
                "designer": {
                    "action": "match_existing",
                    "user_id": matched_user_id,
                },
            },
        )
        return _poll_job(client, headers, run.json()["job_id"])

    first = run_import("merge")
    assert first["summary"]["rows_imported"] == 1

    second = run_import("skip")
    assert second["summary"]["rows_skipped"] == 1
    assert second["summary"]["rows_imported"] == 0


def test_np_code_import(client, test_session_factory):
    csv_bytes = build_timesheet_csv([["2026-06-24", "C500", "", "", 2, "Binil"]])
    # Fix header alignment for NP row - use dedicated NP headers
    csv_bytes = (
        "Date,NP Code,Hours,Designer\n2026-06-24,C500,2,Binil\n"
    ).encode("utf-8")

    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("np.csv", csv_bytes, "text/csv")},
    )
    assert upload.status_code == 200
    upload_id = upload.json()["upload_id"]
    matched_user_id = upload.json()["designer"]["matched_user_id"]

    run = client.post(
        "/api/v1/imports/historical-timesheets/run",
        headers=headers,
        json={
            "upload_id": upload_id,
            "dry_run": False,
            "duplicate_week_action": "merge",
            "designer": {
                "action": "match_existing",
                "user_id": matched_user_id,
            },
        },
    )
    job = _poll_job(client, headers, run.json()["job_id"])
    assert job["status"] == "completed"
    assert job["summary"]["np_entries"] == 1

    session = test_session_factory()
    try:
        entries = session.scalars(select(TimesheetEntry)).all()
        np_entries = [e for e in entries if e.non_productive_code_id is not None]
        assert len(np_entries) >= 1
    finally:
        session.close()


def test_special_code_c500_zero_hours_imports_successfully(client):
    csv_bytes = build_timesheet_csv([["2026-06-24", "C500", "", "", 0, "Binil"]])

    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("leave.csv", csv_bytes, "text/csv")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["error_rows"] == 0
    assert body["ready_rows"] == 1
    assert not any("Invalid Hours" in " ".join(row.get("messages", [])) for row in body["preview"])


def test_special_code_c501_zero_hours_imports_successfully(client):
    csv_bytes = build_timesheet_csv([["2026-06-24", "C501", "", "", 0, "Binil"]])

    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("lack-of-work.csv", csv_bytes, "text/csv")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["error_rows"] == 0
    assert body["ready_rows"] == 1
    assert not any("Invalid Hours" in " ".join(row.get("messages", [])) for row in body["preview"])


def test_special_code_c500_blank_hours_defaults_to_zero(client):
    csv_bytes = build_timesheet_csv([["2026-06-24", "C500", "", "", "", "Binil"]])

    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("leave-blank-hours.csv", csv_bytes, "text/csv")},
    )
    assert upload.status_code == 200
    body = upload.json()
    assert body["error_rows"] == 0
    assert body["ready_rows"] == 1
    preview = body["preview"][0]
    assert str(preview.get("hours")) in {"0", "0.0", "0.00"}


def test_import_history_recorded(client, sample_csv_bytes):
    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("timesheet.csv", sample_csv_bytes, "text/csv")},
    )
    upload_id = upload.json()["upload_id"]
    matched_user_id = upload.json()["designer"]["matched_user_id"]
    run = client.post(
        "/api/v1/imports/historical-timesheets/run",
        headers=headers,
        json={
            "upload_id": upload_id,
            "dry_run": False,
            "duplicate_week_action": "merge",
            "designer": {
                "action": "match_existing",
                "user_id": matched_user_id,
            },
        },
    )
    _poll_job(client, headers, run.json()["job_id"])

    history = client.get(
        "/api/v1/imports/historical-timesheets/history",
        headers=headers,
    )
    assert history.status_code == 200
    assert len(history.json()) >= 1


def test_dry_run_does_not_persist(client, sample_csv_bytes, test_session_factory):
    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-timesheets/upload",
        headers=headers,
        files={"file": ("timesheet.csv", sample_csv_bytes, "text/csv")},
    )
    upload_id = upload.json()["upload_id"]
    matched_user_id = upload.json()["designer"]["matched_user_id"]
    run = client.post(
        "/api/v1/imports/historical-timesheets/run",
        headers=headers,
        json={
            "upload_id": upload_id,
            "dry_run": True,
            "duplicate_week_action": "merge",
            "designer": {
                "action": "match_existing",
                "user_id": matched_user_id,
            },
        },
    )
    job = _poll_job(client, headers, run.json()["job_id"])
    assert job["status"] == "completed"

    session = test_session_factory()
    try:
        count = len(session.scalars(select(TimesheetEntry)).all())
        assert count == 0
    finally:
        session.close()



def test_service_rollback_on_failure(test_session_factory, sample_csv_bytes):
    upload_id = "rollback-test"
    save_upload(upload_id, "timesheet.csv", sample_csv_bytes)
    session = test_session_factory()
    try:
        context = ImportContext(
            designer_resolution=DesignerResolution(
                action=DesignerResolutionAction.match_existing,
                user_id=uuid.uuid4(),
            ),
            duplicate_week_action=DuplicateWeekAction.merge,
        )
        summary, error_log, history_id = run_timesheet_import(
            session,
            upload_id,
            dry_run=False,
            context=context,
            imported_by_id=IDS["user_admin"],
        )
        assert history_id is None
        assert summary.rows_failed == summary.rows_read
        assert session.scalar(select(TimesheetEntry)) is None
    finally:
        session.close()
