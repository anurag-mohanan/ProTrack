"""Tests for Project Command Center (Phase 8 Module 1)."""

from uuid import UUID

import pytest


@pytest.fixture
def sample_project_id(client, auth_headers) -> str:
    response = client.get("/api/v1/projects", headers=auth_headers)
    assert response.status_code == 200
    projects = response.json()
    assert projects, "Expected at least one seeded project"
    return projects[0]["id"]


def test_command_center_endpoint(client, auth_headers, sample_project_id):
    response = client.get(
        f"/api/v1/projects/{sample_project_id}/command-center",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["header"]["tool_number"]
    assert "timeline" in payload
    assert "kpis" in payload
    assert "team" in payload
    assert "customer_summary" in payload
    assert "risks" in payload
    assert "folders" in payload


def test_project_decision_crud(client, auth_headers, sample_project_id):
    create = client.post(
        f"/api/v1/projects/{sample_project_id}/decisions",
        headers=auth_headers,
        json={"category": "design", "comment": "Approved blockout direction"},
    )
    assert create.status_code == 201
    decision = create.json()
    decision_id = decision["id"]
    assert decision["comment"] == "Approved blockout direction"

    listing = client.get(
        f"/api/v1/projects/{sample_project_id}/decisions",
        headers=auth_headers,
    )
    assert listing.status_code == 200
    assert any(row["id"] == decision_id for row in listing.json())

    updated = client.patch(
        f"/api/v1/projects/{sample_project_id}/decisions/{decision_id}",
        headers=auth_headers,
        json={"comment": "Updated decision note"},
    )
    assert updated.status_code == 200
    assert updated.json()["comment"] == "Updated decision note"

    deleted = client.delete(
        f"/api/v1/projects/{sample_project_id}/decisions/{decision_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204


def test_clone_project(client, auth_headers, sample_project_id):
    response = client.post(
        f"/api/v1/projects/{sample_project_id}/clone",
        headers=auth_headers,
    )
    assert response.status_code == 201
    cloned = response.json()
    assert cloned["id"] != sample_project_id
    assert "COPY" in cloned["code"]


def test_update_project_folders(client, auth_headers, sample_project_id):
    response = client.patch(
        f"/api/v1/projects/{sample_project_id}/folders",
        headers=auth_headers,
        json={
            "project_folder_path": r"\\server\projects\TEST-001",
            "cad_folder_path": r"\\server\projects\TEST-001\CAD",
            "released_folder_path": r"\\server\projects\TEST-001\Released",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_folder_path"] == r"\\server\projects\TEST-001"


def test_engineering_change_create(client, auth_headers, sample_project_id):
    response = client.post(
        f"/api/v1/projects/{sample_project_id}/engineering-changes",
        headers=auth_headers,
        json={"ec_number": "EC-001", "title": "Gate relocation", "hours": 4},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ec_number"] == "EC-001"
    assert payload["status"] == "open"

    cc = client.get(
        f"/api/v1/projects/{sample_project_id}/command-center",
        headers=auth_headers,
    )
    assert cc.status_code == 200
    assert cc.json()["engineering_changes"]["open_count"] >= 1
