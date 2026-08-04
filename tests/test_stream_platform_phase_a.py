"""Phase A stream platform: backfill, create validation, scope defaults."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db.phase76_stream_platform_schema_sync import (
    CAD_STREAM_NAME,
    MOLD_STREAM_NAME,
    backfill_null_project_streams,
    ensure_cad_development_stream,
)
from app.models.models import Project, Stream, TaskType, User
from app.services.stream_scope_service import (
    can_view_all_streams,
    get_user_relevant_stream_ids,
    resolve_default_project_stream_id,
)
from tests.conftest import IDS


def test_phase76_seeds_cad_stream_and_task_types(session):
    stream = ensure_cad_development_stream(session)
    session.commit()
    assert stream.name == CAD_STREAM_NAME
    names = {
        row.name
        for row in session.scalars(select(TaskType).where(TaskType.stream_id == stream.id)).all()
    }
    assert "Concept Design" in names
    assert "3D Modelling" in names


def test_backfill_null_project_streams_assigns_mold(session):
    mold = session.scalar(select(Stream).where(Stream.name == MOLD_STREAM_NAME))
    assert mold is not None
    project = session.get(Project, IDS["project"])
    assert project is not None
    project.stream_id = None
    session.flush()

    updated = backfill_null_project_streams(session)
    session.commit()
    session.refresh(project)
    assert updated >= 1
    assert project.stream_id == mold.id


def test_create_project_defaults_stream_to_mold_when_omitted(client, session):
    mold_id = resolve_default_project_stream_id(session)
    assert mold_id is not None
    payload = {
        "tool_number": f"T-{uuid4().hex[:6]}",
        "part_description": "Stream default create",
        "customer_id": str(IDS["customer"]),
        "customer_contact_id": str(IDS["contact"]),
        "design_leader_id": str(IDS["user_anurag"]),
        "designer_id": str(IDS["user_binil"]),
        "quoted_hours": "40.00",
    }
    response = client.post("/api/v1/projects", json=payload, headers=client.auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["stream_id"] == str(mold_id)


def test_create_project_rejects_unknown_stream(client):
    payload = {
        "tool_number": f"T-{uuid4().hex[:6]}",
        "part_description": "Bad stream",
        "customer_id": str(IDS["customer"]),
        "stream_id": str(uuid4()),
        "quoted_hours": "10.00",
    }
    response = client.post("/api/v1/projects", json=payload, headers=client.auth_headers)
    assert response.status_code in (400, 422)
    assert "stream" in response.text.lower()


def test_current_user_exposes_stream_scope_fields(client, session):
    # client.auth_headers logs in as admin@prosohm.com
    admin = session.scalar(select(User).where(User.email == "admin@prosohm.com"))
    assert admin is not None
    mold = session.scalar(select(Stream).where(Stream.name == MOLD_STREAM_NAME))
    assert mold is not None
    admin.stream_id = mold.id
    session.commit()

    response = client.get("/api/v1/auth/me", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stream_id"] == str(mold.id)
    assert body["stream_name"] == MOLD_STREAM_NAME
    assert "relevant_stream_ids" in body
    assert body["can_view_all_streams"] is True


def test_designer_relevant_streams_exclude_unrelated(session):
    mold = session.scalar(select(Stream).where(Stream.name == MOLD_STREAM_NAME))
    cad = ensure_cad_development_stream(session)
    session.flush()
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.stream_id = mold.id
    session.flush()

    relevant = get_user_relevant_stream_ids(session, designer)
    assert mold.id in relevant
    assert cad.id not in relevant


def test_admin_can_view_all_streams(session):
    admin = session.scalar(select(User).where(User.email == "admin@prosohm.com"))
    assert admin is not None
    assert can_view_all_streams(session, admin) is True


def test_preferences_persist_projects_portfolio_scope(client):
    patch = client.patch(
        "/api/v1/preferences/me",
        json={"projects_portfolio_scope": "my_teams"},
        headers=client.auth_headers,
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["projects_portfolio_scope"] == "my_teams"

    read = client.get("/api/v1/preferences/me", headers=client.auth_headers)
    assert read.status_code == 200
    assert read.json()["projects_portfolio_scope"] == "my_teams"
