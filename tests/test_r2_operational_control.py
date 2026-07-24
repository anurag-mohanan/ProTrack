"""Unit tests for R2 soft project stage gates and handoff readiness."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.enums import MilestoneStatus
from app.models.models import Milestone
from app.services.project_calculation_service import recalculate_project


def _leave_milestones_incomplete(session, project_id):
    project_uuid = (
        project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))
    )
    milestones = session.scalars(
        select(Milestone).where(Milestone.project_id == project_uuid)
    ).all()
    assert milestones, "expected seeded milestones"
    for milestone in milestones:
        milestone.status = MilestoneStatus.not_started
    session.commit()


def _complete_all_milestones(session, project_id):
    project_uuid = (
        project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))
    )
    milestones = session.scalars(
        select(Milestone).where(Milestone.project_id == project_uuid)
    ).all()
    for milestone in milestones:
        milestone.status = MilestoneStatus.completed
    session.commit()


def test_cannot_complete_with_open_required_milestones(client, auth_headers, session):
    project_id = client.project_id
    _leave_milestones_incomplete(session, project_id)

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"execution_status": "completed"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "required milestones" in response.json()["detail"].lower()


def test_cannot_set_final_with_open_required_milestones(client, auth_headers, session):
    project_id = client.project_id
    _leave_milestones_incomplete(session, project_id)

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"project_stage": "final"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "required milestones" in response.json()["detail"].lower()


def test_can_complete_when_required_milestones_done(client, auth_headers, session):
    project_id = client.project_id
    _complete_all_milestones(session, project_id)
    recalculate_project(session, project_id)

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"execution_status": "completed"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["execution_status"] == "completed"


def test_project_read_includes_setup_gaps(client, auth_headers):
    project = client.get(
        f"/api/v1/projects/{client.project_id}", headers=auth_headers
    ).json()
    assert "needs_setup" in project
    assert "setup_gaps" in project
    assert isinstance(project["setup_gaps"], list)


def test_timesheet_policy_endpoint(client, auth_headers):
    response = client.get("/api/v1/settings/timesheet-policy", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["editable_months_back"] >= 0
    assert "soft_lock_enabled" in body
    assert body["hard_lock_message"]
