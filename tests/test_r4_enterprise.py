"""R4 enterprise — QA gate, documents, learning plans, legal entities."""

from __future__ import annotations

import io
import uuid

from sqlalchemy import select

from app.models.enums import MilestoneStatus
from app.models.models import Milestone, Project
from app.services.legal_entity_service import ensure_default_legal_entity, list_legal_entities
from app.services.milestone_qa_gate_service import assert_milestone_qa_gate
from app.core.exceptions import ProTrackValidationError


def test_qa_gate_blocks_complete_without_ack(session, client):
    project = session.get(Project, uuid.UUID(str(client.project_id)))
    assert project is not None
    project.qa_gate_enabled = True
    session.commit()

    milestone = session.scalars(
        select(Milestone).where(Milestone.project_id == project.id)
    ).first()
    assert milestone is not None
    milestone.status = MilestoneStatus.not_started
    milestone.qa_acknowledged = False
    session.commit()

    try:
        assert_milestone_qa_gate(
            session,
            milestone,
            next_status=MilestoneStatus.completed,
            qa_acknowledged=False,
        )
        raised = False
    except ProTrackValidationError:
        raised = True
    assert raised


def test_qa_gate_allows_complete_with_ack(session, client):
    project = session.get(Project, uuid.UUID(str(client.project_id)))
    assert project is not None
    project.qa_gate_enabled = True
    session.commit()

    milestone = session.scalars(
        select(Milestone).where(Milestone.project_id == project.id)
    ).first()
    assert milestone is not None

    assert_milestone_qa_gate(
        session,
        milestone,
        next_status=MilestoneStatus.completed,
        qa_acknowledged=True,
    )


def test_qa_gate_api_requires_ack(client, auth_headers, session):
    project_id = client.project_id
    patch = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"qa_gate_enabled": True},
        headers=auth_headers,
    )
    assert patch.status_code == 200
    assert patch.json()["qa_gate_enabled"] is True

    milestone = session.scalars(
        select(Milestone).where(Milestone.project_id == uuid.UUID(str(project_id)))
    ).first()
    assert milestone is not None
    milestone.status = MilestoneStatus.not_started
    milestone.qa_acknowledged = False
    session.commit()

    blocked = client.patch(
        f"/api/v1/milestones/{milestone.id}",
        json={"status": "completed", "progress_percent": 100},
        headers=auth_headers,
    )
    assert blocked.status_code == 422
    assert "qa" in blocked.json()["detail"].lower()

    ok = client.patch(
        f"/api/v1/milestones/{milestone.id}",
        json={
            "status": "completed",
            "progress_percent": 100,
            "qa_acknowledged": True,
        },
        headers=auth_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "completed"
    assert ok.json()["qa_acknowledged"] is True
    assert ok.json()["qa_gate_required"] is True


def test_document_upload_list_download(client, auth_headers):
    project_id = client.project_id
    files = {
        "file": ("spec.txt", io.BytesIO(b"r4 document body"), "text/plain"),
    }
    data = {
        "entity_type": "project",
        "entity_id": str(project_id),
        "title": "Spec note",
    }
    uploaded = client.post(
        "/api/v1/documents",
        data=data,
        files=files,
        headers=auth_headers,
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["filename"] == "spec.txt"
    assert body["entity_type"] == "project"

    listed = client.get(
        f"/api/v1/documents?entity_type=project&entity_id={project_id}",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert any(row["id"] == body["id"] for row in listed.json())

    downloaded = client.get(
        f"/api/v1/documents/{body['id']}/download",
        headers=auth_headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"r4 document body"


def test_legal_entities_endpoint(client, auth_headers, session):
    ensure_default_legal_entity(session)
    response = client.get("/api/v1/settings/legal-entities", headers=auth_headers)
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert any(row["is_default"] for row in rows)
    assert list_legal_entities(session)


def test_learning_plans_from_gaps_endpoint(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = me.json()["id"]

    created = client.post(
        "/api/v1/hr/performance/learning-plans/from-gaps",
        json={"user_id": user_id},
        headers=auth_headers,
    )
    assert created.status_code == 200
    plan = created.json()
    assert plan["user_id"] == user_id
    assert "items" in plan

    listed = client.get(
        f"/api/v1/hr/performance/learning-plans?user_id={user_id}",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert any(row["id"] == plan["id"] for row in listed.json())
