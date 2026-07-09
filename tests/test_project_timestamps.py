import uuid

from sqlalchemy import text

from app.db.schema_sync import ensure_project_timestamps
from tests.conftest import IDS, list_items, login


def test_get_projects_list_returns_timestamps(client, test_engine):
    ensure_project_timestamps(test_engine)

    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/projects", headers=headers)
    assert response.status_code == 200, response.text
    projects = list_items(response)
    assert projects
    assert all(item["created_at"] and item["updated_at"] for item in projects)


def test_create_project_sets_timestamps(client, test_session_factory):
    headers = login(client, "admin@prosohm.com")
    tool_number = f"TS-{uuid.uuid4().hex[:6]}"

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": tool_number,
            "part_description": "Timestamp coverage",
            "customer_id": str(IDS["customer"]),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_at"]
    assert body["updated_at"]

    with test_session_factory() as db:
        row = db.execute(
            text(
                "SELECT created_at, updated_at FROM projects WHERE tool_number = :tool_number"
            ),
            {"tool_number": tool_number},
        ).one()
        assert row[0] is not None
        assert row[1] is not None
