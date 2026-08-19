"""Create / Edit project specials plus team data scope."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.access_control import (
    SPECIAL_APPROVE_PROJECTS,
    SPECIAL_CREATE_PROJECTS,
    SPECIAL_DELETE_PROJECTS,
    SPECIAL_EDIT_PROJECTS,
)
from app.models.enums import ActivityAction, EntityType, ExecutionStatus, TeamRelationshipType
from app.models.models import Activity, Project, Team, TeamMember, User
from tests.conftest import IDS, list_items, login


def _set_specials(session, user: User, perms: list[str]) -> None:
    user.special_permissions = json.dumps(perms)
    session.add(user)
    session.commit()


def _seed_two_teams(session) -> tuple[Team, Team, Project, Project]:
    team_a = Team(id=uuid.uuid4(), name="Write Scope A", colour="#111111", is_active=True)
    team_b = Team(id=uuid.uuid4(), name="Write Scope B", colour="#222222", is_active=True)
    session.add_all([team_a, team_b])
    session.flush()

    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.team_id = team_a.id
    session.add(
        TeamMember(
            team_id=team_a.id,
            user_id=designer.id,
            relationship_type=TeamRelationshipType.member,
            is_primary=True,
        )
    )
    due = date.today() + timedelta(days=30)
    own = Project(
        id=uuid.uuid4(),
        tool_number=f"WA-{uuid.uuid4().hex[:6]}",
        part_description="Team A job",
        customer_id=IDS["customer"],
        team_id=team_a.id,
        designer_id=designer.id,
        quoted_hours=Decimal("8"),
        actual_hours=Decimal("0"),
        due_date=due,
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    other = Project(
        id=uuid.uuid4(),
        tool_number=f"WB-{uuid.uuid4().hex[:6]}",
        part_description="Team B confidential",
        customer_id=IDS["customer"],
        team_id=team_b.id,
        quoted_hours=Decimal("8"),
        actual_hours=Decimal("0"),
        due_date=due,
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    session.add_all([own, other])
    session.commit()
    return team_a, team_b, own, other


def _create_payload(tool: str, team_id: str | None) -> dict:
    body: dict = {
        "tool_number": tool,
        "part_description": "Permission create",
        "customer_id": str(IDS["customer"]),
    }
    if team_id is not None:
        body["team_id"] = team_id
    return body


def test_admin_retains_create_without_team(client):
    headers = login(client, "admin@prosohm.com")
    response = client.post(
        "/api/v1/projects",
        json=_create_payload(f"ADM-{uuid.uuid4().hex[:6]}", None),
        headers=headers,
    )
    assert response.status_code == 201, response.text


def test_view_only_designer_cannot_create_or_edit(client, session):
    team_a, _team_b, own, _other = _seed_two_teams(session)
    designer = session.get(User, IDS["user_binil"])
    _set_specials(session, designer, [])
    headers = login(client, "binil@prosohm.com")

    listed = client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    ids = {row["id"] for row in list_items(listed)}
    assert str(own.id) in ids

    created = client.post(
        "/api/v1/projects",
        json=_create_payload(f"VO-{uuid.uuid4().hex[:6]}", str(team_a.id)),
        headers=headers,
    )
    assert created.status_code == 403

    edited = client.patch(
        f"/api/v1/projects/{own.id}",
        json={"part_description": "Should not save"},
        headers=headers,
    )
    assert edited.status_code == 403


def test_create_only_user_can_create_in_scope_not_edit(client, session):
    team_a, team_b, own, _other = _seed_two_teams(session)
    designer = session.get(User, IDS["user_binil"])
    _set_specials(session, designer, [SPECIAL_CREATE_PROJECTS])
    headers = login(client, "binil@prosohm.com")

    created = client.post(
        "/api/v1/projects",
        json=_create_payload(f"CO-{uuid.uuid4().hex[:6]}", str(team_a.id)),
        headers=headers,
    )
    assert created.status_code == 201, created.text

    cross = client.post(
        "/api/v1/projects",
        json=_create_payload(f"CX-{uuid.uuid4().hex[:6]}", str(team_b.id)),
        headers=headers,
    )
    assert cross.status_code == 403

    unteamed = client.post(
        "/api/v1/projects",
        json=_create_payload(f"CN-{uuid.uuid4().hex[:6]}", None),
        headers=headers,
    )
    assert unteamed.status_code == 403

    edited = client.patch(
        f"/api/v1/projects/{own.id}",
        json={"part_description": "Create-only cannot edit"},
        headers=headers,
    )
    assert edited.status_code == 403


def test_edit_only_user_can_edit_in_scope_not_create(client, session):
    _team_a, _team_b, own, other = _seed_two_teams(session)
    designer = session.get(User, IDS["user_binil"])
    _set_specials(session, designer, [SPECIAL_EDIT_PROJECTS])
    headers = login(client, "binil@prosohm.com")

    created = client.post(
        "/api/v1/projects",
        json=_create_payload(f"EO-{uuid.uuid4().hex[:6]}", str(_team_a.id)),
        headers=headers,
    )
    assert created.status_code == 403

    edited = client.patch(
        f"/api/v1/projects/{own.id}",
        json={"part_description": "Edited in scope"},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["part_description"] == "Edited in scope"

    cross = client.patch(
        f"/api/v1/projects/{other.id}",
        json={"part_description": "Cross team"},
        headers=headers,
    )
    assert cross.status_code == 403


def test_create_and_edit_user(client, session):
    team_a, _team_b, own, _other = _seed_two_teams(session)
    designer = session.get(User, IDS["user_binil"])
    _set_specials(session, designer, [SPECIAL_CREATE_PROJECTS, SPECIAL_EDIT_PROJECTS])
    headers = login(client, "binil@prosohm.com")

    created = client.post(
        "/api/v1/projects",
        json=_create_payload(f"CE-{uuid.uuid4().hex[:6]}", str(team_a.id)),
        headers=headers,
    )
    assert created.status_code == 201, created.text

    edited = client.patch(
        f"/api/v1/projects/{own.id}",
        json={"notes": "Both permissions"},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text


def test_design_leader_defaults_still_edit_assigned_project(client):
    headers = login(client, "anurag@prosohm.com")
    response = client.patch(
        f"/api/v1/projects/{IDS['project']}",
        json={"notes": "DL default edit"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_create_and_edit_are_audited(client, session):
    headers = login(client, "admin@prosohm.com")
    tool = f"AUD-{uuid.uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/projects",
        json=_create_payload(tool, None),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"part_description": "Audited change"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text

    session.expire_all()
    created_row = session.scalar(
        select(Activity).where(
            Activity.entity_id == uuid.UUID(project_id),
            Activity.entity_type == EntityType.project,
            Activity.action == ActivityAction.project_created,
        )
    )
    updated_row = session.scalar(
        select(Activity).where(
            Activity.entity_id == uuid.UUID(project_id),
            Activity.action == ActivityAction.project_updated,
        )
    )
    assert created_row is not None
    assert created_row.user_id == IDS["user_admin"]
    assert created_row.module == "projects"
    assert tool in (created_row.new_value or "")
    assert updated_row is not None
    assert updated_row.user_id == IDS["user_admin"]
    assert "Audited change" in (updated_row.new_value or "")


def test_soft_delete_requires_delete_permission(client, session):
    _team_a, _team_b, own, _other = _seed_two_teams(session)
    designer = session.get(User, IDS["user_binil"])
    _set_specials(session, designer, [SPECIAL_EDIT_PROJECTS])
    headers = login(client, "binil@prosohm.com")
    denied = client.post(f"/api/v1/projects/{own.id}/soft-delete", headers=headers)
    assert denied.status_code == 403

    admin = login(client, "admin@prosohm.com")
    allowed = client.post(f"/api/v1/projects/{own.id}/soft-delete", headers=admin)
    assert allowed.status_code == 200, allowed.text


def test_create_only_user_cannot_delete(client, session):
    team_a, _team_b, own, _other = _seed_two_teams(session)
    designer = session.get(User, IDS["user_binil"])
    _set_specials(session, designer, [SPECIAL_CREATE_PROJECTS])
    headers = login(client, "binil@prosohm.com")
    denied = client.post(f"/api/v1/projects/{own.id}/soft-delete", headers=headers)
    assert denied.status_code == 403
    created = client.post(
        "/api/v1/projects",
        json=_create_payload(f"CR-{uuid.uuid4().hex[:6]}", str(team_a.id)),
        headers=headers,
    )
    assert created.status_code == 201, created.text


def test_admin_empty_stored_specials_can_still_delete(client, session):
    admin_user = session.get(User, IDS["user_admin"])
    assert admin_user is not None
    _set_specials(session, admin_user, [])
    team_a, _team_b, own, _other = _seed_two_teams(session)
    headers = login(client, "admin@prosohm.com")
    response = client.post(f"/api/v1/projects/{own.id}/soft-delete", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["is_deleted"] is True
    listed = client.get("/api/v1/projects", headers=headers)
    ids = {row["id"] for row in list_items(listed)}
    assert str(own.id) not in ids


def test_admin_user_save_allows_delete_and_approve_specials(client, session):
    admin = login(client, "admin@prosohm.com")
    admin_user = session.get(User, IDS["user_admin"])
    assert admin_user is not None
    response = client.patch(
        f"/api/v1/users/{admin_user.id}",
        headers=admin,
        json={
            "special_permissions": [
                SPECIAL_DELETE_PROJECTS,
                SPECIAL_APPROVE_PROJECTS,
                SPECIAL_CREATE_PROJECTS,
                SPECIAL_EDIT_PROJECTS,
            ]
        },
    )
    assert response.status_code == 200, response.text
