from decimal import Decimal

from app.models.enums import MilestoneStatus
from app.services.milestone_workspace_service import apply_progress_rules


def test_apply_progress_rules_completes_at_100():
    result = apply_progress_rules({"progress_percent": 100})
    assert result["status"] == MilestoneStatus.completed
    assert result["progress_percent"] == 100
    assert result["completed_at"] is not None
    assert result["completed_date"] is not None


def test_apply_progress_rules_stamps_completion_on_status_transition():
    result = apply_progress_rules(
        {"status": MilestoneStatus.completed},
        previous_status=MilestoneStatus.in_progress,
    )
    assert result["progress_percent"] == 100
    assert result["completed_at"] is not None
    assert result["completed_date"] is not None


def test_apply_progress_rules_does_not_restamp_when_already_completed():
    existing_at = object()
    result = apply_progress_rules(
        {
            "status": MilestoneStatus.completed,
            "completed_at": existing_at,
            "completed_date": "2026-01-01",
        },
        previous_status=MilestoneStatus.completed,
    )
    assert result["completed_at"] is existing_at
    assert result["completed_date"] == "2026-01-01"


def test_apply_progress_rules_clears_completion_when_reopened():
    result = apply_progress_rules(
        {"status": MilestoneStatus.in_progress},
        previous_status=MilestoneStatus.completed,
    )
    assert result["completed_at"] is None
    assert result["completed_date"] is None


def test_milestone_summary_endpoint(client, auth_headers):
    project_id = client.project_id
    response = client.get(f"/api/v1/milestones/summary/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["milestone_count"] >= 1
    assert Decimal(str(body["quoted_hours"])) >= 0


def test_milestone_patch_planned_hours(client, auth_headers):
    milestone_id = client.milestone_id
    response = client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"planned_hours": 24, "name": "Surfacing"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["planned_hours"] == "24.00" or float(body["planned_hours"]) == 24
    assert body["name"] == "Surfacing"
