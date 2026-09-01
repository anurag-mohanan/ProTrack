import uuid

from tests.conftest import IDS, login


def _first_small_task_type_id(client, headers) -> str:
    response = client.get("/api/v1/lookups/project-small-task-types", headers=headers)
    assert response.status_code == 200, response.text
    items = response.json()
    assert items, "Expected seeded project small task types"
    return items[0]["id"]


def test_project_classification_report_summary(client):
    headers = login(client, "admin@prosohm.com")
    task_type_id = _first_small_task_type_id(client, headers)

    suffix = uuid.uuid4().hex[:6]
    client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"FD-RPT-{suffix}",
            "part_description": "Classification report full design",
            "customer_id": str(IDS["customer"]),
            "project_classification": "full_design",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"ST-RPT-{suffix}",
            "part_description": "Classification report small task",
            "customer_id": str(IDS["customer"]),
            "project_classification": "small_task",
            "small_task_type_id": task_type_id,
        },
        headers=headers,
    )

    response = client.get(
        "/api/v1/reports/project-classification?include_archived=true",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert "summary" in body
    assert "small_task_breakdown" in body
    assert "by_stream" in body
    assert "by_team" in body

    summary_map = {row["classification"]: row["project_count"] for row in body["summary"]}
    assert summary_map.get("full_design", 0) >= 1
    assert summary_map.get("small_task", 0) >= 1
    assert any(row["project_count"] > 0 for row in body["small_task_breakdown"])


def test_project_classification_report_requires_report_access(client):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/reports/project-classification", headers=headers)
    assert response.status_code == 403
