"""Rework / quality issue hours are non-billable and analysable on the project."""

from decimal import Decimal

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ContributionReason
from app.models.models import User
from app.services.timesheet_entry_service import (
    apply_productive_billable_rules,
    is_rework_quality_reason,
)
from tests.conftest import IDS


def test_rework_quality_reason_forces_non_billable(session):
    data = {
        "contribution_reason": ContributionReason.rework_quality,
        "is_billable": True,
    }
    apply_productive_billable_rules(data, db=session, actor=None)
    assert data["is_billable"] is False
    assert is_rework_quality_reason(data["contribution_reason"])


def test_designer_cannot_unbill_without_rework_reason(session):
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    data = {
        "contribution_reason": None,
        "is_billable": False,
    }
    try:
        apply_productive_billable_rules(data, db=session, actor=designer)
        raise AssertionError("expected validation error")
    except ProTrackValidationError as exc:
        assert "Rework" in str(exc)


def test_productive_entry_rework_quality_is_non_billable(client):
    task_types = client.get("/api/v1/lookups/task-types", headers=client.auth_headers).json()
    project = client.get(f"/api/v1/projects/{client.project_id}", headers=client.auth_headers).json()
    stream_id = project.get("stream_id")
    design = next(
        row
        for row in task_types
        if row["name"] == "Design" and row["stream_id"] == stream_id
    )

    timesheet = client.post(
        "/api/v1/timesheets",
        headers=client.auth_headers,
        json={
            "user_id": str(IDS["user_anurag"]),
            "week_start": "2026-06-09",
        },
    )
    assert timesheet.status_code == 201

    response = client.post(
        "/api/v1/timesheet-entries",
        headers=client.auth_headers,
        json={
            "timesheet_id": timesheet.json()["id"],
            "work_category": "productive",
            "project_id": client.project_id,
            "task_type_id": design["id"],
            "entry_date": "2026-06-10",
            "hours": "4",
            "description": "Fix quality issue on block out",
            "contribution_reason": "rework_quality",
            "is_billable": True,  # client may still send true; server forces false
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["contribution_reason"] == "rework_quality"
    assert body["is_billable"] is False
    assert Decimal(str(body["hours"])) == Decimal("4")
