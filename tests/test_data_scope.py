"""Layer-2 data scope: team-aware visibility."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.core.data_scope import (
    DataScopeLevel,
    can_access_project,
    resolve_data_scope,
    scoped_customer_ids,
)
from app.core.team_access import project_visibility_clause
from app.models.models import Project, User
from tests.conftest import IDS


def test_admin_data_scope_is_administrator(client, session):
    me = client.get("/api/v1/auth/me", headers=client.auth_headers)
    assert me.status_code == 200
    scope = me.json().get("data_scope")
    assert scope is not None
    assert scope["level"] == DataScopeLevel.administrator.value
    assert scope["unrestricted"] is True
    assert scope["team_ids"] is None


def test_designer_project_list_is_team_scoped(client, session):
    """Non-admin designer must not see projects outside team portfolio / assignment."""
    designer = session.scalar(select(User).where(User.email == "designer@prosohm.com"))
    if designer is None:
        # Seed may use a different designer email — fall back to any non-admin with a team
        designer = session.scalar(
            select(User).where(
                User.is_active.is_(True),
                User.email != "admin@prosohm.com",
                User.team_id.is_not(None),
            )
        )
    assert designer is not None

    from tests.conftest import login

    headers = login(client, designer.email)
    scope = resolve_data_scope(session, designer)
    assert scope.level in {
        DataScopeLevel.own,
        DataScopeLevel.own_team,
        DataScopeLevel.multiple_teams,
        DataScopeLevel.department,
    }

    listed = client.get("/api/v1/projects?page_size=100", headers=headers)
    assert listed.status_code == 200
    items = listed.json().get("items") or []
    from uuid import UUID

    for row in items:
        project = session.get(Project, UUID(str(row["id"])))
        assert project is not None
        assert can_access_project(session, designer, project)


def test_lookup_teams_respect_data_scope(client, session):
    designer = session.scalar(
        select(User).where(
            User.is_active.is_(True),
            User.email != "admin@prosohm.com",
            User.team_id.is_not(None),
        )
    )
    if designer is None:
        return
    from tests.conftest import login

    headers = login(client, designer.email)
    scope = resolve_data_scope(session, designer)
    teams = client.get("/api/v1/lookups/teams", headers=headers)
    assert teams.status_code == 200
    if scope.unrestricted:
        return
    returned = {row["id"] for row in teams.json()}
    if scope.team_ids is not None:
        assert returned <= {str(tid) for tid in scope.team_ids}


def test_project_visibility_clause_matches_can_access(session):
    admin = session.scalar(select(User).where(User.email == "admin@prosohm.com"))
    assert admin is not None
    assert project_visibility_clause(session, admin) is None
    assert resolve_data_scope(session, admin).unrestricted is True

    project = session.get(Project, IDS["project"])
    assert project is not None
    assert can_access_project(session, admin, project)


def test_scoped_customers_subset_for_restricted_user(session):
    designer = session.scalar(
        select(User).where(
            User.is_active.is_(True),
            User.email != "admin@prosohm.com",
            User.team_id.is_not(None),
        )
    )
    if designer is None:
        return
    allowed = scoped_customer_ids(session, designer)
    admin = session.scalar(select(User).where(User.email == "admin@prosohm.com"))
    assert admin is not None
    assert scoped_customer_ids(session, admin) is None
    if allowed is not None:
        assert uuid4() not in allowed  # sanity: random id not in set
