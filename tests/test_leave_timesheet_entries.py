"""Leave timesheet entries via category-driven NP code rules."""

from decimal import Decimal

from tests.conftest import IDS, login
from tests.test_timesheet_work_categories import _create_draft_timesheet, _get_np_code_id


def test_c500_entry_sets_leave_fields(client):
    timesheet_id = _create_draft_timesheet(client)
    leave_code_id = _get_np_code_id(client, "C500")

    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "non_productive_code_id": leave_code_id,
            "entry_date": "2026-06-11",
            "hours": "8",
            "is_billable": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["non_productive_code"] == "C500"
    assert body["non_productive_category"] == "leave"
    assert body["is_billable"] is False
    assert body["leave_count"] == 1
    assert body["project_id"] is None


def test_c500_rejects_billable_override_even_for_admin(client):
    timesheet_id = _create_draft_timesheet(client)
    leave_code_id = _get_np_code_id(client, "C500")
    headers = login(client, "admin@prosohm.com")

    response = client.patch(
        f"/api/v1/timesheet-entries/{_create_leave_entry(client, timesheet_id, leave_code_id)}",
        headers=headers,
        json={"is_billable": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_billable"] is False


def _create_leave_entry(client, timesheet_id: str, leave_code_id: str) -> str:
    created = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "non_productive_code_id": leave_code_id,
            "entry_date": "2026-06-12",
            "hours": "8",
        },
    )
    assert created.status_code == 201
    return created.json()["id"]


def test_leave_excluded_from_np_hours_report(client):
    timesheet_id = _create_draft_timesheet(client)
    leave_code_id = _get_np_code_id(client, "C500")
    meeting_code_id = _get_np_code_id(client, "C502")

    client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "non_productive_code_id": leave_code_id,
            "entry_date": "2026-06-13",
            "hours": "8",
        },
    )
    client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "non_productive_code_id": meeting_code_id,
            "entry_date": "2026-06-13",
            "hours": "2",
        },
    )

    np_hours = client.get(
        "/api/v1/reports/non-productive-hours",
        headers=client.auth_headers,
    )
    assert np_hours.status_code == 200
    codes = {row["non_productive_code"] for row in np_hours.json()}
    assert "C500" not in codes
    assert "C502" in codes


def test_billable_vs_np_report_includes_leave_days(client):
    timesheet_id = _create_draft_timesheet(client)
    leave_code_id = _get_np_code_id(client, "C500")
    client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet_id,
            "work_category": "non_productive",
            "non_productive_code_id": leave_code_id,
            "entry_date": "2026-06-14",
            "hours": "8",
        },
    )
    submitted = client.post(
        f"/api/v1/timesheets/{timesheet_id}/submit",
        headers=client.auth_headers,
    )
    assert submitted.status_code == 200
    approved = client.post(
        f"/api/v1/timesheets/{timesheet_id}/approve",
        json={},
        headers=login(client, "admin@prosohm.com"),
    )
    assert approved.status_code == 200

    report = client.get(
        "/api/v1/reports/billable-vs-non-billable",
        headers=client.auth_headers,
    )
    assert report.status_code == 200
    body = report.json()
    assert body["leave_days"] >= 1
    assert Decimal(str(body["np_hours"])) == Decimal("0")


def test_np_code_lookup_includes_leave_category(client):
    response = client.get(
        "/api/v1/lookups/non-productive-codes",
        headers=client.auth_headers,
    )
    assert response.status_code == 200
    leave = next(row for row in response.json() if row["code"] == "C500")
    assert leave["category"] == "leave"
    assert leave["description"] == "Leave"
