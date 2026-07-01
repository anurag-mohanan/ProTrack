"""Tests for Module 2 resource planning grid."""

from datetime import date


def test_resource_planning_grid_week(client, auth_headers):
    response = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
        params={"granularity": "week"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["granularity"] == "week"
    assert len(payload["periods"]) == 8
    assert "designers" in payload
    assert "team_summary" in payload


def test_resource_planning_grid_daily(client, auth_headers):
    response = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
        params={"granularity": "day", "start": date.today().isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["granularity"] == "day"
    assert len(payload["periods"]) == 14


def test_resource_planning_grid_monthly(client, auth_headers):
    response = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
        params={"granularity": "month"},
    )
    assert response.status_code == 200
    assert len(response.json()["periods"]) == 6


def test_resource_planning_assign_designer(client, auth_headers, test_session_factory):
    from app.models.models import Project, User
    from sqlalchemy import select

    with test_session_factory() as db:
        project = db.scalar(select(Project).limit(1))
        designer = db.scalar(
            select(User).where(User.email == "binil@prosohm.com").limit(1)
        )
        assert project is not None
        assert designer is not None
        project_id = str(project.id)
        designer_id = str(designer.id)

    assign = client.post(
        "/api/v1/dashboard/resource-planning/assign",
        headers=auth_headers,
        json={"project_id": project_id, "designer_id": designer_id},
    )
    assert assign.status_code == 204

    grid = client.get(
        "/api/v1/dashboard/resource-planning/grid",
        headers=auth_headers,
        params={"granularity": "week"},
    )
    assert grid.status_code == 200
    designers = grid.json()["designers"]
    assigned_row = next(
        (row for row in designers if row["user_id"] == designer_id),
        None,
    )
    assert assigned_row is not None
    assert any(
        block["project_id"] == project_id
        for cell in assigned_row["cells"]
        for block in cell["blocks"]
    )
