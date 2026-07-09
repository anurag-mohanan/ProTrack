"""Task type master data API tests."""

from sqlalchemy import select

from app.models.models import Stream, TaskType
from tests.conftest import list_items


def _first_stream_id(client) -> str:
    response = client.get("/api/v1/streams", headers=client.auth_headers)
    assert response.status_code == 200
    streams = list_items(response)
    assert streams, "Expected at least one stream"
    return streams[0]["id"]


def test_create_task_type_success(client):
    stream_id = _first_stream_id(client)

    response = client.post(
        "/api/v1/task-types",
        headers=client.auth_headers,
        json={
            "name": "Plaques",
            "stream_id": stream_id,
            "description": None,
            "is_billable": True,
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Plaques"
    assert body["stream_id"] == stream_id
    assert body["description"] is None
    assert body["is_billable"] is True
    assert body["is_active"] is True
    assert "id" in body


def test_create_task_type_duplicate_returns_409(client):
    stream_id = _first_stream_id(client)
    payload = {
        "name": "DuplicateTask",
        "stream_id": stream_id,
        "description": None,
        "is_billable": False,
        "is_active": True,
    }
    first = client.post("/api/v1/task-types", headers=client.auth_headers, json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/task-types", headers=client.auth_headers, json=payload)
    assert second.status_code == 409, second.text
    assert "already exists" in second.json()["detail"].lower()


def test_create_task_type_invalid_stream_returns_404(client):
    import uuid

    response = client.post(
        "/api/v1/task-types",
        headers=client.auth_headers,
        json={
            "name": "Orphan Task",
            "stream_id": str(uuid.uuid4()),
            "description": None,
            "is_billable": True,
            "is_active": True,
        },
    )
    assert response.status_code == 404, response.text
    assert "stream" in response.json()["detail"].lower()


def test_create_task_type_inactive_stream_returns_422(client, session):
    inactive = Stream(name="Inactive Stream", description=None, is_active=False)
    session.add(inactive)
    session.commit()
    session.refresh(inactive)

    response = client.post(
        "/api/v1/task-types",
        headers=client.auth_headers,
        json={
            "name": "Inactive Stream Task",
            "stream_id": str(inactive.id),
            "description": None,
            "is_billable": True,
            "is_active": True,
        },
    )
    assert response.status_code == 422, response.text
    assert "inactive" in response.json()["detail"].lower()


def test_create_task_type_empty_description(client):
    stream_id = _first_stream_id(client)
    response = client.post(
        "/api/v1/task-types",
        headers=client.auth_headers,
        json={
            "name": "No Description Task",
            "stream_id": stream_id,
            "description": "",
            "is_billable": True,
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["description"] is None


def test_create_task_type_with_description(client):
    stream_id = _first_stream_id(client)
    response = client.post(
        "/api/v1/task-types",
        headers=client.auth_headers,
        json={
            "name": "Described Task",
            "stream_id": stream_id,
            "description": "Detailed work",
            "is_billable": False,
            "is_active": False,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["description"] == "Detailed work"
    assert body["is_billable"] is False
    assert body["is_active"] is False


def test_update_task_type(client, session):
    stream_id = _first_stream_id(client)
    created = client.post(
        "/api/v1/task-types",
        headers=client.auth_headers,
        json={
            "name": "Editable Task",
            "stream_id": stream_id,
            "description": None,
            "is_billable": True,
            "is_active": True,
        },
    )
    assert created.status_code == 201
    task_type_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/task-types/{task_type_id}",
        headers=client.auth_headers,
        json={"description": "Updated", "is_billable": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] == "Updated"
    assert updated.json()["is_billable"] is False


def test_existing_seeded_task_types_unaffected(client, session):
    seeded = session.scalar(select(TaskType).where(TaskType.name == "Design"))
    assert seeded is not None
    stream = session.get(Stream, seeded.stream_id)
    assert stream is not None
