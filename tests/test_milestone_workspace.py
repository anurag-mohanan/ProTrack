from decimal import Decimal

from app.models.enums import MilestoneStatus
from app.services.milestone_workspace_service import apply_progress_rules


def test_apply_progress_rules_completes_at_100():
    result = apply_progress_rules({"progress_percent": 100})
    assert result["status"] == MilestoneStatus.completed
    assert result["progress_percent"] == 100
    assert result["completed_at"] is not None
    assert result["completed_date"] is not None


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
