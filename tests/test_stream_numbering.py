"""Stream optional project prefix and numbering."""

from tests.conftest import login


def test_create_stream_with_optional_prefix_and_numbering(client):
    headers = login(client, "admin@prosohm.com")

    created = client.post(
        "/api/v1/streams",
        headers=headers,
        json={
            "name": "Numbered Stream Test",
            "description": "Internal numbering",
            "is_active": True,
            "use_project_prefix": True,
            "use_project_numbering": True,
            "project_number_prefix": "MD",
            "project_number_format": "{prefix}-{seq}",
            "next_project_sequence": 10,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["use_project_prefix"] is True
    assert body["use_project_numbering"] is True
    assert body["project_number_prefix"] == "MD"
    assert body["project_number_format"] == "{prefix}-{seq}"
    assert body["next_project_sequence"] == 10

    plain = client.post(
        "/api/v1/streams",
        headers=headers,
        json={"name": "Customer Numbers Stream", "is_active": True},
    )
    assert plain.status_code == 201, plain.text
    plain_body = plain.json()
    assert plain_body["use_project_prefix"] is False
    assert plain_body["use_project_numbering"] is False
    assert plain_body["project_number_prefix"] in (None, "")


def test_project_create_auto_codes_from_stream_numbering(client, session):
    from tests.conftest import IDS

    headers = login(client, "admin@prosohm.com")
    stream = client.post(
        "/api/v1/streams",
        headers=headers,
        json={
            "name": "Auto Code Stream",
            "use_project_prefix": True,
            "use_project_numbering": True,
            "project_number_prefix": "FX",
            "project_number_format": "{prefix}-{seq}",
            "next_project_sequence": 5,
        },
    )
    assert stream.status_code == 201, stream.text
    stream_id = stream.json()["id"]

    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "tool_number": "CUST-TOOL-99",
            "part_description": "Auto numbered part",
            "customer_id": str(IDS["customer"]),
            "stream_id": stream_id,
            "code": None,
        },
    )
    assert project.status_code == 201, project.text
    assert project.json()["code"] == "FX-5"

    refreshed = client.get(f"/api/v1/streams/{stream_id}", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["next_project_sequence"] == 6


def test_project_keeps_customer_supplied_code_when_provided(client):
    from tests.conftest import IDS

    headers = login(client, "admin@prosohm.com")
    stream = client.post(
        "/api/v1/streams",
        headers=headers,
        json={
            "name": "Manual Code Stream",
            "use_project_prefix": True,
            "use_project_numbering": True,
            "project_number_prefix": "ZZ",
            "project_number_format": "{prefix}-{seq}",
            "next_project_sequence": 1,
        },
    )
    assert stream.status_code == 201, stream.text
    stream_id = stream.json()["id"]

    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "tool_number": "CUST-SUPPLIED-1",
            "part_description": "Customer number wins",
            "customer_id": str(IDS["customer"]),
            "stream_id": stream_id,
            "code": "CUSTOMER-PN-7788",
        },
    )
    assert project.status_code == 201, project.text
    assert project.json()["code"] == "CUSTOMER-PN-7788"

    refreshed = client.get(f"/api/v1/streams/{stream_id}", headers=headers)
    assert refreshed.json()["next_project_sequence"] == 1
