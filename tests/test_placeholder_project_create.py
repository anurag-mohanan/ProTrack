import uuid

from tests.conftest import IDS, login


def test_create_placeholder_project_with_minimal_fields(client):
    headers = login(client, "admin@prosohm.com")
    tool_number = f"PH-{uuid.uuid4().hex[:6]}"

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": tool_number,
            "part_description": "RFQ placeholder part",
            "customer_id": str(IDS["customer"]),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tool_number"] == tool_number
    assert body["part_description"] == "RFQ placeholder part"
    assert body["customer_id"] == str(IDS["customer"])
    assert body["customer_contact_id"] is None
    assert body["design_leader_id"] is None
    assert body["designer_id"] is None
    assert body["surfacer_id"] is None
    assert body["stream_id"] is None
    assert body["project_type_id"] is None
    assert body["project_template_id"] is None
    assert body["team_id"] is None
    assert body["due_date"] is None
    assert body["execution_status"] == "planning"
    assert body["priority"] == "medium"
    assert body["health"] == "green"
    assert body["code"] is None
    assert float(body["quoted_hours"]) == 0.0


def test_create_allows_any_active_user_as_design_leader(client):
    headers = login(client, "admin@prosohm.com")

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"T-{uuid.uuid4().hex[:6]}",
            "part_description": "Leader assignment test",
            "customer_id": str(IDS["customer"]),
            "design_leader_id": str(IDS["user_binil"]),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["design_leader_id"] == str(IDS["user_binil"])


def test_create_rejects_missing_required_fields(client):
    headers = login(client, "admin@prosohm.com")

    response = client.post(
        "/api/v1/projects",
        json={"customer_id": str(IDS["customer"])},
        headers=headers,
    )
    assert response.status_code == 422, response.text


def test_create_rejects_duplicate_tool_number(client):
    headers = login(client, "admin@prosohm.com")
    tool_number = f"DUP-{uuid.uuid4().hex[:6]}"

    first = client.post(
        "/api/v1/projects",
        json={
            "tool_number": tool_number,
            "part_description": "First project",
            "customer_id": str(IDS["customer"]),
        },
        headers=headers,
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/projects",
        json={
            "tool_number": tool_number,
            "part_description": "Duplicate tool number",
            "customer_id": str(IDS["customer"]),
        },
        headers=headers,
    )
    assert second.status_code == 422, second.text
    assert "tool number" in second.json()["detail"].lower()


def test_create_with_explicit_code(client):
    headers = login(client, "admin@prosohm.com")
    code = f"CODE-{uuid.uuid4().hex[:6]}"

    response = client.post(
        "/api/v1/projects",
        json={
            "tool_number": f"T-{uuid.uuid4().hex[:6]}",
            "part_description": "Coded project",
            "customer_id": str(IDS["customer"]),
            "code": code,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["code"] == code
