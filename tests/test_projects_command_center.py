"""Projects Command Center — workstreams, filters, saved views."""

from __future__ import annotations


def test_workstream_catalog_and_crud(client):
    listed = client.get("/api/v1/workstreams", headers=client.auth_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    items = body.get("items") or body
    assert isinstance(items, list)
    names = {row["name"] for row in items}
    assert "Mold Design" in names or "Concept" in names

    created = client.post(
        "/api/v1/workstreams",
        headers=client.auth_headers,
        json={
            "name": "CC Test WS",
            "code": "CCTEST",
            "display_order": 99,
            "color": "#0d9488",
            "icon": "precision",
        },
    )
    assert created.status_code == 201, created.text
    ws_id = created.json()["id"]
    assert created.json()["color"] == "#0d9488"

    patched = client.patch(
        f"/api/v1/workstreams/{ws_id}",
        headers=client.auth_headers,
        json={"description": "Command center test", "display_order": 5},
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == "Command center test"
    assert patched.json()["display_order"] == 5


def test_project_workstreams_optional_and_replace(client):
    projects = client.get("/api/v1/projects?page_size=5", headers=client.auth_headers)
    assert projects.status_code == 200
    items = projects.json().get("items") or []
    assert items, "expected seeded projects"
    project_id = items[0]["id"]

    empty = client.get(f"/api/v1/projects/{project_id}/workstreams", headers=client.auth_headers)
    assert empty.status_code == 200
    assert isinstance(empty.json(), list)

    ws_list = client.get("/api/v1/workstreams?is_active=true", headers=client.auth_headers)
    workstreams = ws_list.json().get("items") or ws_list.json()
    assert workstreams
    ws_id = workstreams[0]["id"]

    replaced = client.put(
        f"/api/v1/projects/{project_id}/workstreams",
        headers=client.auth_headers,
        json={"items": [{"workstream_id": ws_id, "estimated_hours": 10}]},
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()) == 1
    assert replaced.json()[0]["workstream_id"] == ws_id
    assert float(replaced.json()[0]["estimated_hours"]) == 10.0

    filtered = client.get(
        f"/api/v1/projects?workstream_ids={ws_id}&page_size=50",
        headers=client.auth_headers,
    )
    assert filtered.status_code == 200
    filtered_ids = {row["id"] for row in (filtered.json().get("items") or [])}
    assert project_id in filtered_ids

    cleared = client.put(
        f"/api/v1/projects/{project_id}/workstreams",
        headers=client.auth_headers,
        json={"items": []},
    )
    assert cleared.status_code == 200
    assert cleared.json() == []


def test_projects_summary_and_saved_views(client):
    summary = client.get("/api/v1/projects/summary", headers=client.auth_headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert "active_count" in data
    assert "overdue_count" in data

    views = client.get("/api/v1/projects/views", headers=client.auth_headers)
    assert views.status_code == 200
    assert any(v["is_system"] and v["name"] == "All" for v in views.json())

    created = client.post(
        "/api/v1/projects/views",
        headers=client.auth_headers,
        json={
            "name": "My CC View",
            "filter_json": {"health": "red"},
            "display_json": {"layout": "list"},
        },
    )
    assert created.status_code == 201, created.text
    view_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/projects/views/{view_id}", headers=client.auth_headers)
    assert deleted.status_code == 204


def test_preferences_cc_layout(client):
    patched = client.patch(
        "/api/v1/preferences/me",
        headers=client.auth_headers,
        json={
            "projects_cc_layout": "grouped",
            "projects_cc_show_workstreams": False,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["projects_cc_layout"] == "grouped"
    assert patched.json()["projects_cc_show_workstreams"] is False


def test_multi_workstream_assignment_appears_on_project_read(client):
    projects = client.get("/api/v1/projects?page_size=5", headers=client.auth_headers)
    project_id = (projects.json().get("items") or [])[0]["id"]
    ws_list = client.get("/api/v1/workstreams?is_active=true", headers=client.auth_headers)
    workstreams = ws_list.json().get("items") or ws_list.json()
    assert len(workstreams) >= 2
    ids = [workstreams[0]["id"], workstreams[1]["id"]]

    replaced = client.put(
        f"/api/v1/projects/{project_id}/workstreams",
        headers=client.auth_headers,
        json={
            "items": [
                {"workstream_id": ids[0], "estimated_hours": 8},
                {"workstream_id": ids[1], "estimated_hours": 4},
            ]
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()) == 2

    detail = client.get(f"/api/v1/projects/{project_id}", headers=client.auth_headers)
    assert detail.status_code == 200
    ws_ids = {row["workstream_id"] for row in detail.json().get("workstreams") or []}
    assert set(ids) <= ws_ids
