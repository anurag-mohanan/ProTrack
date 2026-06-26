import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.project_template_seed import ensure_project_types_and_templates
from app.models.models import Customer, Milestone, ProjectTemplate, ProjectType
from tests.conftest import IDS


@pytest.fixture
def template_db(session):
    ensure_project_types_and_templates(session)
    return session


def _get_project_type(session, name: str) -> ProjectType:
    project_type = session.scalar(select(ProjectType).where(ProjectType.name == name))
    assert project_type is not None
    return project_type


def _get_template(session, name: str) -> ProjectTemplate:
    template = session.scalar(select(ProjectTemplate).where(ProjectTemplate.name == name))
    assert template is not None
    return template


def _create_project_payload(
    session,
    *,
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    project_type_id: uuid.UUID,
    template_id: uuid.UUID | None = None,
) -> dict:
    return {
        "tool_number": f"T-{uuid.uuid4().hex[:6]}",
        "part_description": "Template test part",
        "customer_id": str(customer_id),
        "customer_contact_id": str(contact_id),
        "design_leader_id": str(IDS["user_anurag"]),
        "designer_id": str(IDS["user_binil"]),
        "stream_id": str(IDS["stream"]),
        "project_type_id": str(project_type_id),
        "project_template_id": str(template_id) if template_id else None,
        "code": f"TMP-{uuid.uuid4().hex[:6]}",
        "quoted_hours": "80.00",
        "due_date": (date.today() + timedelta(days=45)).isoformat(),
        "notes": "Template test project",
    }


def test_create_project_with_general_template(client, template_db):
    mold_type = _get_project_type(template_db, "Mold Design")
    general = _get_template(template_db, "General Mold Design")
    payload = _create_project_payload(
        template_db,
        customer_id=IDS["customer"],
        contact_id=IDS["contact"],
        project_type_id=mold_type.id,
        template_id=general.id,
    )
    response = client.post("/api/v1/projects", json=payload, headers=client.auth_headers)
    assert response.status_code == 201, response.text
    project_id = response.json()["id"]

    milestones = template_db.scalars(
        select(Milestone)
        .where(Milestone.project_id == uuid.UUID(project_id))
        .order_by(Milestone.sort_order)
    ).all()
    assert [milestone.name for milestone in milestones] == [
        "Feasibility",
        "Blockout",
        "Roughing",
        "Intermediate Review",
        "Final Review",
        "File Release",
        "BOM Release",
    ]


def test_create_project_with_sybridge_template(client, template_db):
    sybridge = template_db.scalar(select(Customer).where(Customer.name == "Sybridge"))
    assert sybridge is not None
    if not sybridge.contacts:
        from app.models.models import Contact

        contact = Contact(
            customer_id=sybridge.id,
            first_name="Sy",
            last_name="Bridge",
            is_primary=True,
            is_active=True,
        )
        template_db.add(contact)
        template_db.commit()
    contact = sybridge.contacts[0]

    mold_type = _get_project_type(template_db, "Mold Design")
    payload = _create_project_payload(
        template_db,
        customer_id=sybridge.id,
        contact_id=contact.id,
        project_type_id=mold_type.id,
    )
    response = client.post("/api/v1/projects", json=payload, headers=client.auth_headers)
    assert response.status_code == 201, response.text
    project_id = response.json()["id"]

    milestones = template_db.scalars(
        select(Milestone)
        .where(Milestone.project_id == uuid.UUID(project_id))
        .order_by(Milestone.sort_order)
    ).all()
    assert [milestone.name for milestone in milestones] == [
        "Feasibility",
        "Blockout",
        "Customer Intermediate Review",
        "Final Review",
        "File Release",
        "BOM Release",
    ]


def test_template_update_affects_new_projects_only(client, template_db):
    mold_type = _get_project_type(template_db, "Mold Design")
    general = _get_template(template_db, "General Mold Design")

    response = client.patch(
        f"/api/v1/project-templates/{general.id}",
        json={
            "milestones": [
                {"milestone_name": "Kickoff", "sort_order": 1, "is_required": True},
                {"milestone_name": "Delivery", "sort_order": 2, "is_required": True},
            ]
        },
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text

    existing_milestones = template_db.scalars(
        select(Milestone).where(Milestone.project_id == IDS["project"])
    ).all()
    assert len(existing_milestones) == 7

    payload = _create_project_payload(
        template_db,
        customer_id=IDS["customer"],
        contact_id=IDS["contact"],
        project_type_id=mold_type.id,
        template_id=general.id,
    )
    create_response = client.post(
        "/api/v1/projects", json=payload, headers=client.auth_headers
    )
    assert create_response.status_code == 201, create_response.text
    new_milestones = template_db.scalars(
        select(Milestone)
        .where(Milestone.project_id == uuid.UUID(create_response.json()["id"]))
        .order_by(Milestone.sort_order)
    ).all()
    assert [milestone.name for milestone in new_milestones] == ["Kickoff", "Delivery"]


def test_duplicate_template(client, template_db):
    source = _get_template(template_db, "General Mold Design")
    response = client.post(
        f"/api/v1/project-templates/{source.id}/duplicate",
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "General Mold Design (Copy)"
    assert body["milestone_count"] == 7
    assert body["is_default"] is False


def test_delete_template_in_use_is_blocked(client, template_db):
    mold_type = _get_project_type(template_db, "Mold Design")
    ti_template = _get_template(template_db, "TI Automotive Mold Design")
    payload = _create_project_payload(
        template_db,
        customer_id=IDS["customer"],
        contact_id=IDS["contact"],
        project_type_id=mold_type.id,
        template_id=ti_template.id,
    )
    create_response = client.post(
        "/api/v1/projects", json=payload, headers=client.auth_headers
    )
    assert create_response.status_code == 201

    delete_response = client.delete(
        f"/api/v1/project-templates/{ti_template.id}",
        headers=client.auth_headers,
    )
    assert delete_response.status_code == 422


def test_match_templates_prefers_customer_override(client, template_db):
    mold_type = _get_project_type(template_db, "Mold Design")
    sybridge = template_db.scalar(select(Customer).where(Customer.name == "Sybridge"))
    assert sybridge is not None

    response = client.get(
        "/api/v1/project-templates/match",
        params={
            "project_type_id": str(mold_type.id),
            "customer_id": str(sybridge.id),
        },
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    names = [item["name"] for item in response.json()]
    assert "Sybridge Mold Design" in names
    assert "General Mold Design" in names


def test_project_types_admin_crud(client, template_db):
    create_response = client.post(
        "/api/v1/project-types",
        json={"name": "Prototype Tooling", "description": "Prototype work"},
        headers=client.auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    project_type_id = create_response.json()["id"]

    list_response = client.get("/api/v1/project-types", headers=client.auth_headers)
    assert list_response.status_code == 200
    assert any(row["id"] == project_type_id for row in list_response.json())
