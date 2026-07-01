"""Tests for productive and non-productive timesheet entries."""

from decimal import Decimal

from tests.conftest import IDS, login


def _create_draft_timesheet(client):
    response = client.post(
        "/api/v1/timesheets",
        headers=client.auth_headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "week_start": "2026-06-09",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _get_task_type_id(client, name: str) -> str:
    response = client.get("/api/v1/lookups/task-types", headers=client.auth_headers)
    assert response.status_code == 200
    match = next((row for row in response.json() if row["name"] == name), None)
    assert match is not None, f"Task type {name} not found"
    return match["id"]


def _get_np_code_id(client, code: str) -> str:
    response = client.get("/api/v1/lookups/non-productive-codes", headers=client.auth_headers)
    assert response.status_code == 200
    match = next((row for row in response.json() if row["code"] == code), None)
    assert match is not None
    return match["id"]


def test_productive_entry_requires_project_and_task(client):
    timesheet_id = _create_draft_timesheet(client)
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "entry_date": "2026-06-10",
            "hours": "8",
        },
    )
    assert response.status_code == 422


def test_productive_entry_auto_fills_customer_and_defaults_billable(client):
    timesheet_id = _create_draft_timesheet(client)
    task_type_id = _get_task_type_id(client, "Design")
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": client.project_id,
            "task_type_id": task_type_id,
            "entry_date": "2026-06-10",
            "hours": "7.5",
            "description": "Design work",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["customer_id"] == str(IDS["customer"])
    assert body["customer_name"] == "TI Automotive"
    assert body["is_billable"] is True
    assert body["project_tool_number"] == "T-100"


def test_non_productive_entry_requires_np_code_and_forbids_project(client):
    timesheet_id = _create_draft_timesheet(client)
    np_code_id = _get_np_code_id(client, "C502")
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "non_productive_code_id": np_code_id,
            "entry_date": "2026-06-10",
            "hours": "2",
            "description": "Team meeting",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] is None
    assert body["is_billable"] is False
    assert body["non_productive_code"] == "C502"


def test_non_productive_rejects_project(client):
    timesheet_id = _create_draft_timesheet(client)
    np_code_id = _get_np_code_id(client, "C500")
    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "project_id": client.project_id,
            "non_productive_code_id": np_code_id,
            "entry_date": "2026-06-10",
            "hours": "1",
        },
    )
    assert response.status_code == 422


def test_reports_separate_productive_and_np_hours(client):
    timesheet_id = _create_draft_timesheet(client)
    task_type_id = _get_task_type_id(client, "Design")
    np_code_id = _get_np_code_id(client, "C504")
    client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "productive",
            "project_id": client.project_id,
            "task_type_id": task_type_id,
            "entry_date": "2026-06-10",
            "hours": "4",
        },
    )
    client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "non_productive_code_id": np_code_id,
            "entry_date": "2026-06-10",
            "hours": "2",
        },
    )
    productive = client.get(
        "/api/v1/reports/productive-hours",
        headers=client.auth_headers,
    )
    np_hours = client.get(
        "/api/v1/reports/non-productive-hours",
        headers=client.auth_headers,
    )
    assert productive.status_code == 200
    assert np_hours.status_code == 200
    assert sum(Decimal(str(row["total_hours"])) for row in productive.json()) >= Decimal("4")
    assert any(row["non_productive_code"] == "C504" for row in np_hours.json())


def test_dashboard_includes_billable_and_np_kpis(client):
    response = client.get("/api/v1/dashboard/summary", headers=client.auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "billable_hours" in body
    assert "np_hours" in body
    assert "productive_percent" in body
