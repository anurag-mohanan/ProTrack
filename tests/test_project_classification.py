import uuid

from tests.conftest import IDS, login


def _first_small_task_type_id(client, headers) -> str:
    response = client.get("/api/v1/lookups/project-small-task-types", headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()
    assert items, "Expected seeded project small task types"
    return items[0]["id"]


def test_create_small_task_requires_task_type(client):
    headers = login(client, "admin@prosohm.com")

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"ST-{uuid.uuid4().hex[:6]}",
            "part_description": "Small task without type",
            "customer_id": str(IDS["customer"]),
            "project_classification": "small_task",
        },
        headers=headers,
    )
    assert response.status_code == 422, response.text


def test_create_small_task_with_task_type(client):
    headers = login(client, "admin@prosohm.com")
    task_type_id = _first_small_task_type_id(client, headers)

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"ST-{uuid.uuid4().hex[:6]}",
            "part_description": "Feasibility review",
            "customer_id": str(IDS["customer"]),
            "project_classification": "small_task",
            "small_task_type_id": task_type_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_classification"] == "small_task"
    assert body["small_task_type_id"] == task_type_id


def test_create_full_design_clears_task_type(client):
    headers = login(client, "admin@prosohm.com")
    task_type_id = _first_small_task_type_id(client, headers)

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"FD-{uuid.uuid4().hex[:6]}",
            "part_description": "Complete mold design",
            "customer_id": str(IDS["customer"]),
            "project_classification": "full_design",
            "small_task_type_id": task_type_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_classification"] == "full_design"
    assert body["small_task_type_id"] is None


def test_list_projects_filter_by_classification(client):
    headers = login(client, "admin@prosohm.com")

    created = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"FD-{uuid.uuid4().hex[:6]}",
            "part_description": "Filter test project",
            "customer_id": str(IDS["customer"]),
            "project_classification": "full_design",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/projects",
        params={"project_classification": "full_design", "limit": 50},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert any(item["id"] == created.json()["id"] for item in items)
    assert all(item["project_classification"] == "full_design" for item in items)


def test_lookup_project_small_task_types(client):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/lookups/project-small-task-types", headers=headers)
    assert response.status_code == 200, response.text
    names = {row["name"] for row in response.json()}
    assert "Blockout Only" in names
    assert "Feasibility" in names


def test_create_requires_project_classification(client):
    headers = login(client, "admin@prosohm.com")

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"NC-{uuid.uuid4().hex[:6]}",
            "part_description": "Missing classification",
            "customer_id": str(IDS["customer"]),
        },
        headers=headers,
    )
    assert response.status_code == 422, response.text


def test_create_full_design_persists_on_reload(client):
    headers = login(client, "admin@prosohm.com")

    created = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"FD-{uuid.uuid4().hex[:6]}",
            "part_description": "Full design persist",
            "customer_id": str(IDS["customer"]),
            "project_classification": "full_design",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    assert created.json()["project_classification"] == "full_design"

    reloaded = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["project_classification"] == "full_design"


def test_edit_classification_full_design_to_small_task_persists(client):
    headers = login(client, "admin@prosohm.com")
    task_type_id = _first_small_task_type_id(client, headers)

    created = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"ED-{uuid.uuid4().hex[:6]}",
            "part_description": "Edit classification",
            "customer_id": str(IDS["customer"]),
            "project_classification": "full_design",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "project_classification": "small_task",
            "small_task_type_id": task_type_id,
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["project_classification"] == "small_task"
    assert updated.json()["small_task_type_id"] == task_type_id

    reloaded = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["project_classification"] == "small_task"
    assert reloaded.json()["small_task_type_id"] == task_type_id


def test_edit_classification_small_task_to_full_design_persists(client):
    headers = login(client, "admin@prosohm.com")
    task_type_id = _first_small_task_type_id(client, headers)

    created = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"ED-{uuid.uuid4().hex[:6]}",
            "part_description": "Edit to full design",
            "customer_id": str(IDS["customer"]),
            "project_classification": "small_task",
            "small_task_type_id": task_type_id,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"project_classification": "full_design"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["project_classification"] == "full_design"
    assert updated.json()["small_task_type_id"] is None

    reloaded = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["project_classification"] == "full_design"
    assert reloaded.json()["small_task_type_id"] is None
