from datetime import datetime

from app.models.enums import MilestoneStatus


def test_patch_status_only_leaves_other_fields_unchanged(client):
    milestone_id = client.milestone_id
    project_id = client.project_id

    before = client.get(f"/api/v1/milestones/{milestone_id}").json()
    assert before["name"] == "Feasibility"
    assert before["description"] == "Initial feasibility review"
    assert before["sort_order"] == 1
    assert before["project_id"] == project_id
    assert before["due_date"] == "2026-06-01"
    assert before["status"] == "not_started"
    assert before["completed_at"] is None

    response = client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"status": "completed"},
    )

    assert response.status_code == 200
    after = response.json()
    assert after["status"] == "completed"
    assert after["name"] == "Feasibility"
    assert after["description"] == "Initial feasibility review"
    assert after["sort_order"] == 1
    assert after["project_id"] == project_id
    assert after["due_date"] == "2026-06-01"
    assert after["completed_at"] is not None


def test_patch_status_completed_sets_completed_at(client):
    milestone_id = client.milestone_id

    response = client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"status": "completed"},
    )

    assert response.status_code == 200
    completed_at = response.json()["completed_at"]
    assert completed_at is not None
    parsed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    assert parsed.year >= 2026


def test_patch_status_away_from_completed_clears_completed_at(client):
    milestone_id = client.milestone_id

    completed = client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None

    reopened = client.patch(
        f"/api/v1/milestones/{milestone_id}",
        json={"status": "in_progress"},
    )

    assert reopened.status_code == 200
    body = reopened.json()
    assert body["status"] == "in_progress"
    assert body["completed_at"] is None


def test_milestone_update_schema_excludes_unset_fields():
    from app.schemas.project import MilestoneUpdate

    update = MilestoneUpdate(status=MilestoneStatus.completed)
    dumped = update.model_dump(exclude_unset=True)

    assert dumped == {"status": MilestoneStatus.completed}
