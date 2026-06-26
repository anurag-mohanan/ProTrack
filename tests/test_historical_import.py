import io
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.models.models import Project
from app.schemas.historical_import import DuplicateAction
from app.services.historical_import_service import (
    analyze_upload,
    parse_workbook,
    run_import,
    save_upload,
)
from tests.conftest import IDS, login


HEADERS = [
    "Tool No.",
    "Customer",
    "Designer",
    "Surfacer",
    "Quoted Hours",
    "Actual Design Hours",
    "Design Phase",
    "Progress",
    "Eng Status",
    "Part Description",
    "Due Date",
]


def build_sample_workbook(rows: list[list]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tool Tracking"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def sample_workbook_bytes():
    return build_sample_workbook(
        [
            [
                "T-HIST-001",
                "Acme Plastics",
                "Logesh",
                "Akhil",
                120,
                80,
                "Roughing",
                40,
                "In Progress",
                "Historical cover mold",
                "2026-12-31",
            ],
            [
                "T-HIST-002",
                "Beta Manufacturing",
                "Sarath",
                "",
                90,
                90,
                "BOM Release",
                100,
                "Completed",
                "Historical lid tool",
                "2026-10-15",
            ],
            [
                "",
                "Missing Tool Customer",
                "Umesh",
                "",
                50,
                10,
                "Feasibility",
                10,
                "In Progress",
                "Invalid row",
                "2026-11-01",
            ],
        ]
    )


def test_parse_workbook(sample_workbook_bytes, tmp_path):
    path = tmp_path / "sample.xlsx"
    path.write_bytes(sample_workbook_bytes)
    rows = parse_workbook(path)
    assert len(rows) == 3
    assert rows[0].tool_number == "T-HIST-001"
    assert rows[0].quoted_hours == Decimal("120")
    assert rows[0].design_phase == "Roughing"
    assert rows[2].errors


def test_upload_and_analyze(client, sample_workbook_bytes):
    headers = login(client, "admin@prosohm.com")
    files = {
        "file": (
            "historical.xlsx",
            sample_workbook_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    response = client.post(
        "/api/v1/imports/historical-projects/upload",
        headers=headers,
        files=files,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 3
    assert body["error_rows"] >= 1
    assert body["ready_rows"] >= 1


def test_dry_run_import(client, sample_workbook_bytes):
    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-projects/upload",
        headers=headers,
        files={"file": ("historical.xlsx", sample_workbook_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    upload_id = upload.json()["upload_id"]

    run = client.post(
        "/api/v1/imports/historical-projects/run",
        headers=headers,
        json={
            "upload_id": upload_id,
            "dry_run": True,
            "duplicate_action": "skip",
        },
    )
    assert run.status_code == 200
    job_id = run.json()["job_id"]

    import time

    job = None
    for _ in range(20):
        job_response = client.get(
            f"/api/v1/imports/historical-projects/jobs/{job_id}",
            headers=headers,
        )
        job = job_response.json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)

    assert job is not None
    assert job["status"] == "completed"
    assert job["summary"]["projects_imported"] >= 1


def test_import_creates_projects_and_entities(session, sample_workbook_bytes):
    upload_id = "test-upload-001"
    save_upload(upload_id, "historical.xlsx", sample_workbook_bytes)
    analysis = analyze_upload(session, upload_id)
    assert analysis.ready_rows >= 1

    summary, errors = run_import(
        session,
        upload_id,
        dry_run=False,
        duplicate_action=DuplicateAction.skip,
    )
    assert summary.projects_imported >= 1
    assert summary.customers_created >= 1
    assert summary.milestones_created >= 7

    project = session.query(Project).filter(Project.tool_number == "T-HIST-001").one_or_none()
    assert project is not None
    assert project.actual_hours == Decimal("80")


def test_duplicate_skip_on_second_import(session, sample_workbook_bytes):
    upload_id = "test-upload-dup"
    save_upload(upload_id, "historical.xlsx", sample_workbook_bytes)
    run_import(session, upload_id, dry_run=False, duplicate_action=DuplicateAction.skip)

    summary, _ = run_import(
        session,
        upload_id,
        dry_run=False,
        duplicate_action=DuplicateAction.skip,
    )
    assert summary.projects_skipped >= 1


def test_non_admin_forbidden(client, sample_workbook_bytes):
    headers = login(client, "binil@prosohm.com")
    response = client.post(
        "/api/v1/imports/historical-projects/upload",
        headers=headers,
        files={"file": ("historical.xlsx", sample_workbook_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 403


def test_error_log_csv(client, sample_workbook_bytes):
    headers = login(client, "admin@prosohm.com")
    upload = client.post(
        "/api/v1/imports/historical-projects/upload",
        headers=headers,
        files={"file": ("historical.xlsx", sample_workbook_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    upload_id = upload.json()["upload_id"]
    run = client.post(
        "/api/v1/imports/historical-projects/run",
        headers=headers,
        json={"upload_id": upload_id, "dry_run": True, "duplicate_action": "skip"},
    )
    job_id = run.json()["job_id"]

    import time

    for _ in range(20):
        job = client.get(
            f"/api/v1/imports/historical-projects/jobs/{job_id}",
            headers=headers,
        ).json()
        if job["status"] == "completed":
            break
        time.sleep(0.1)

    csv_response = client.get(
        f"/api/v1/imports/historical-projects/jobs/{job_id}/errors.csv",
        headers=headers,
    )
    assert csv_response.status_code == 200
    assert "row_number" in csv_response.text
