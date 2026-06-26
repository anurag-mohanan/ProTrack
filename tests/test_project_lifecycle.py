"""Tests for project archive, restore, soft delete, and permanent delete."""

from tests.conftest import IDS, login


def test_list_projects_defaults_to_active(client):
    response = client.get("/api/v1/projects", headers=client.auth_headers)
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 1
    assert projects[0]["tool_number"] == "T-100"


def test_archive_and_restore_project(client):
    project_id = client.project_id

    archive = client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers=client.auth_headers,
    )
    assert archive.status_code == 200
    archived = archive.json()
    assert archived["is_archived"] is True
    assert archived["archived_at"] is not None

    active = client.get(
        "/api/v1/projects?lifecycle=active",
        headers=client.auth_headers,
    )
    assert active.status_code == 200
    assert active.json() == []

    archived_list = client.get(
        "/api/v1/projects/archived",
        headers=client.auth_headers,
    )
    assert archived_list.status_code == 200
    assert len(archived_list.json()) == 1

    restore = client.post(
        f"/api/v1/projects/{project_id}/restore",
        headers=client.auth_headers,
    )
    assert restore.status_code == 200
    assert restore.json()["is_archived"] is False

    active_after = client.get(
        "/api/v1/projects?lifecycle=active",
        headers=client.auth_headers,
    )
    assert len(active_after.json()) == 1


def test_soft_delete_restore_and_permanent_delete_blocked(client, session):
    from app.models.models import Project

    project_id = client.project_id

    client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers=client.auth_headers,
    )
    soft_delete = client.post(
        f"/api/v1/projects/{project_id}/soft-delete",
        headers=client.auth_headers,
    )
    assert soft_delete.status_code == 200
    assert soft_delete.json()["is_deleted"] is True

    deleted_list = client.get(
        "/api/v1/projects/deleted",
        headers=client.auth_headers,
    )
    assert deleted_list.status_code == 200
    assert len(deleted_list.json()) == 1

    check = client.get(
        f"/api/v1/projects/{project_id}/delete-check",
        headers=client.auth_headers,
    )
    assert check.status_code == 200
    assert check.json()["can_permanently_delete"] is False
    assert check.json()["blockers"]

    permanent = client.delete(
        f"/api/v1/projects/{project_id}/permanent",
        headers=client.auth_headers,
    )
    assert permanent.status_code == 422

    restore = client.post(
        f"/api/v1/projects/{project_id}/restore-deleted",
        headers=client.auth_headers,
    )
    assert restore.status_code == 200
    assert restore.json()["is_deleted"] is False

    project = session.get(Project, IDS["project"])
    assert project is not None


def test_archived_projects_included_in_reports_by_default(client):
    project_id = client.project_id
    client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers=client.auth_headers,
    )

    with_archived = client.get(
        "/api/v1/reports/project-hours?include_archived=true",
        headers=client.auth_headers,
    )
    assert with_archived.status_code == 200
    assert len(with_archived.json()) == 1

    without_archived = client.get(
        "/api/v1/reports/project-hours?include_archived=false",
        headers=client.auth_headers,
    )
    assert without_archived.status_code == 200
    assert without_archived.json() == []


def test_dashboard_lifecycle_counts(client):
    project_id = client.project_id
    summary_before = client.get(
        "/api/v1/dashboard/summary",
        headers=client.auth_headers,
    ).json()
    assert summary_before["active_projects"] >= 1

    client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers=client.auth_headers,
    )
    summary_after = client.get(
        "/api/v1/dashboard/summary",
        headers=client.auth_headers,
    ).json()
    assert summary_after["archived_projects"] == 1
    assert summary_after["active_projects"] == summary_before["active_projects"] - 1


def test_non_admin_cannot_list_deleted_projects(client):
    headers = login(client, "anurag@prosohm.com")
    response = client.get("/api/v1/projects/deleted", headers=headers)
    assert response.status_code == 403
