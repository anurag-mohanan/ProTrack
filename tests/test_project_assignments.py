from tests.conftest import IDS, login


def _project_payload(project_type_mold_id: str, **overrides):
    payload = {
        "tool_number": "T-200",
        "part_description": "Assignment test part",
        "customer_id": str(IDS["customer"]),
        "customer_contact_id": str(IDS["contact"]),
        "design_leader_id": str(IDS["user_anurag"]),
        "designer_id": str(IDS["user_binil"]),
        "surfacer_id": None,
        "stream_id": str(IDS["stream"]),
        "project_type_id": project_type_mold_id,
        "code": "TEST-ASSIGN-001",
        "quoted_hours": 40,
        "due_date": "2026-08-01",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def test_designer_tier_can_fill_designer_or_surfacer_slot(client, project_type_mold_id):
    headers = login(client, "admin@prosohm.com")

    as_designer = client.post(
        "/api/v1/projects",
        json=_project_payload(
            project_type_mold_id,
            tool_number="T-200-A",
            code="TEST-JR-DESIGNER",
            designer_id=str(IDS["user_junior_designer"]),
            surfacer_id=str(IDS["user_senior_designer"]),
        ),
        headers=headers,
    )
    assert as_designer.status_code == 201

    as_surfacer = client.post(
        "/api/v1/projects",
        json=_project_payload(
            project_type_mold_id,
            tool_number="T-200-B",
            code="TEST-SR-SURFACER",
            designer_id=str(IDS["user_binil"]),
            surfacer_id=str(IDS["user_junior_designer"]),
        ),
        headers=headers,
    )
    assert as_surfacer.status_code == 201


def test_junior_assigned_as_surfacer_can_read_project(client, project_type_mold_id):
    headers = login(client, "admin@prosohm.com")
    create = client.post(
        "/api/v1/projects",
        json=_project_payload(
            project_type_mold_id,
            tool_number="T-200-C",
            code="TEST-JR-ACCESS",
            designer_id=str(IDS["user_binil"]),
            surfacer_id=str(IDS["user_junior_designer"]),
        ),
        headers=headers,
    )
    assert create.status_code == 201
    project_id = create.json()["id"]

    junior_headers = login(client, "akhil@prosohm.com")
    response = client.get(f"/api/v1/projects/{project_id}", headers=junior_headers)
    assert response.status_code == 200
