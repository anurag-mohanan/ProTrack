"""Org department standardization, CRUD API, reassignment, and MD-at-top."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.enums import ActivityAction
from app.models.models import Activity, OrgDepartment, Role, User
from tests.conftest import IDS

BASE = "/api/v1/org-departments"


def test_phase51_standardizes_department_names(session):
    hr = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "hr_admin"))
    accounts = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "accounts"))
    assert hr is not None and hr.name == "Human Resource"
    assert accounts is not None and accounts.name == "Accounts"


def test_list_org_departments_returns_standard_set(client):
    response = client.get(BASE, headers=client.auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    codes = {row["code"] for row in payload}
    assert {"management", "engineering", "sales", "accounts", "hr_admin", "it"} <= codes
    names = {row["name"] for row in payload}
    assert "Human Resource" in names
    assert "Accounts" in names


def test_create_update_delete_org_department(client):
    create = client.post(
        BASE,
        headers=client.auth_headers,
        json={
            "code": "quality",
            "name": "Quality Assurance",
            "description": "QA and audits",
            "colour": "#8e24aa",
            "sort_order": 60,
        },
    )
    assert create.status_code == 201, create.text
    dept_id = create.json()["id"]

    update = client.patch(
        f"{BASE}/{dept_id}",
        headers=client.auth_headers,
        json={"description": "Quality & compliance"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["description"] == "Quality & compliance"

    delete = client.delete(f"{BASE}/{dept_id}", headers=client.auth_headers)
    assert delete.status_code == 204, delete.text


def test_create_duplicate_code_rejected(client):
    response = client.post(
        BASE,
        headers=client.auth_headers,
        json={"code": "engineering", "name": "Engineering Duplicate"},
    )
    assert response.status_code == 422, response.text


def test_delete_blocked_when_department_has_people(client, session):
    eng = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "engineering"))
    user = session.get(User, IDS["user_binil"])
    user.org_department_id = eng.id
    session.commit()

    check = client.get(f"{BASE}/{eng.id}/delete-check", headers=client.auth_headers)
    assert check.status_code == 200, check.text
    assert check.json()["can_delete"] is False

    delete = client.delete(f"{BASE}/{eng.id}", headers=client.auth_headers)
    assert delete.status_code == 422, delete.text


def test_assign_user_to_department_reassigns_and_audits(client, session):
    hr = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "hr_admin"))
    user = session.get(User, IDS["user_binil"])
    user.org_department_id = None
    session.commit()

    response = client.post(
        f"{BASE}/{hr.id}/assign-user",
        headers=client.auth_headers,
        json={"user_id": str(IDS["user_binil"])},
    )
    assert response.status_code == 200, response.text

    session.expire_all()
    refreshed = session.get(User, IDS["user_binil"])
    assert refreshed.org_department_id == hr.id

    activity = session.scalar(
        select(Activity).where(
            Activity.action == ActivityAction.user_department_changed,
            Activity.entity_id == IDS["user_binil"],
        )
    )
    assert activity is not None


def test_assign_user_unknown_user_404(client, session):
    hr = session.scalar(select(OrgDepartment).where(OrgDepartment.code == "hr_admin"))
    response = client.post(
        f"{BASE}/{hr.id}/assign-user",
        headers=client.auth_headers,
        json={"user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404, response.text


def test_managing_director_is_company_root(client, session):
    md_role = session.scalar(select(Role).where(Role.name == "Managing Director"))
    assert md_role is not None, "phase49 should seed the Managing Director role"

    md_user = User(
        id=uuid.uuid4(),
        role_id=md_role.id,
        email="md.orgchart@prosohm.com",
        password_hash="x",
        first_name="Meera",
        last_name="Director",
        designation="Managing Director",
        is_active=True,
    )
    session.add(md_user)
    session.commit()

    response = client.get("/api/v1/teams/organization-chart", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    root = response.json().get("company_root")
    assert root is not None
    assert root["user_id"] == str(md_user.id)
