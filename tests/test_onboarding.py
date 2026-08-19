"""Onboarding checklists (PP-HRD-FO-14) — phase 54."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.data.india_leave_defaults import INDIA_LEAVE_TYPE_DEFAULTS
from app.models.models import OnboardingChecklistTemplate, Role, Ticket, User
from app.services.onboarding_checklist_service import (
    FORM_CODE,
    PP_HRD_FO_14_STRUCTURE,
    TEMPLATE_VERSION,
)
from tests.conftest import DEFAULT_PASSWORD, login


def _expected_item_count() -> int:
    return sum(len(section["items"]) for section in PP_HRD_FO_14_STRUCTURE)


def _make_user(session, role_name: str, email: str, first: str = "Test", last: str = "User") -> User:
    role = session.scalar(select(Role).where(Role.name == role_name))
    assert role is not None, f"role {role_name!r} should be seeded"
    user = User(
        id=uuid.uuid4(),
        role_id=role.id,
        email=email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        first_name=first,
        last_name=last,
        designation=role_name,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_india_leave_defaults_are_ready_for_future_module():
    codes = {row["code"] for row in INDIA_LEAVE_TYPE_DEFAULTS}
    assert {"el", "cl", "sl", "maternity", "paternity", "unpaid"} <= codes
    el = next(row for row in INDIA_LEAVE_TYPE_DEFAULTS if row["code"] == "el")
    assert el["default_annual_days"] == 18.0


def test_default_template_seeded(client, session):
    admin = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/hr/onboarding/templates", headers=admin)
    assert response.status_code == 200, response.text
    codes = {row["code"] for row in response.json()}
    assert FORM_CODE in codes

    row = session.scalar(
        select(OnboardingChecklistTemplate).where(OnboardingChecklistTemplate.code == FORM_CODE)
    )
    assert row is not None
    assert row.version >= TEMPLATE_VERSION
    assert _expected_item_count() == 24


def test_hr_can_create_and_complete_checklist(client, session):
    _make_user(session, "HR Manager", "hrmgr-onboard@prosohm.com", first="Hari", last="HR")
    hr = login(client, "hrmgr-onboard@prosohm.com")

    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={
            "employee_name": "Abhay CK",
            "employee_code": "PP099",
            "joining_date": "2026-03-09",
            "designation": "Senior Design Engineer",
            "department_name": "Prosohm",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["employee_name"] == "Abhay CK"
    assert body["template_code"] == FORM_CODE
    assert body["total_items"] == 24
    assert body["pending_items"] == 24
    assert body["status"] == "in_progress"
    assert {item["section"] for item in body["items"]} >= {
        "HUMAN RESOURCES",
        "ADMINISTRATION",
        "TEAM / MANAGER",
        "IT",
        "ACCOUNTS",
    }
    assert len(body["triggered_tickets"]) == 4  # hr, admin, it, accounts (not manager)

    first_item = body["items"][0]
    updated = client.post(
        f"/api/v1/hr/onboarding/{body['id']}/items/{first_item['id']}/status",
        headers=hr,
        json={"status": "completed"},
    )
    assert updated.status_code == 200, updated.text
    updated_body = updated.json()
    assert updated_body["completed_items"] == 1
    assert updated_body["items"][0]["status"] == "completed"
    assert updated_body["items"][0]["completion_date"] is not None


def test_create_assigns_manager_owner_and_raises_tickets(client, session):
    admin = login(client, "admin@prosohm.com")
    manager = _make_user(
        session, "Engineering Manager", "mgr-onboard@prosohm.com", first="Maya", last="Mgr"
    )
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=admin,
        json={
            "employee_name": "Routed Hire",
            "reporting_manager_id": str(manager.id),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    manager_items = [item for item in body["items"] if item["responsibility"] == "manager"]
    assert manager_items
    assert all(item["owner_user_id"] == str(manager.id) for item in manager_items)
    assert all(item["help_ticket_id"] is None for item in manager_items)

    ticketed = [item for item in body["items"] if item["responsibility"] != "manager"]
    assert ticketed
    assert all(item["help_ticket_id"] is not None for item in ticketed)
    assert all(item["help_ticket_number"] for item in ticketed)

    ticket_ids = {uuid.UUID(item["help_ticket_id"]) for item in ticketed}
    assert len(ticket_ids) == 4
    tickets = session.scalars(select(Ticket).where(Ticket.id.in_(ticket_ids))).all()
    assert len(tickets) == 4
    assert {t.category for t in tickets} == {"hr", "admin", "it", "other"}


def test_designer_cannot_create_onboarding(client, session):
    headers = login(client, "binil@prosohm.com")
    response = client.post(
        "/api/v1/hr/onboarding",
        headers=headers,
        json={"employee_name": "Should Fail"},
    )
    assert response.status_code == 403


def test_hr_can_edit_and_delete_checklist(client, session):
    admin = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=admin,
        json={"employee_name": "Editable Hire", "employee_code": "PP100"},
    )
    assert created.status_code == 201, created.text
    checklist_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/hr/onboarding/{checklist_id}",
        headers=admin,
        json={"employee_name": "Editable Hire Updated", "employee_code": "PP100"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["employee_name"] == "Editable Hire Updated"
    assert updated.json()["employee_code"] == "PP100"

    blocked = client.patch(
        f"/api/v1/hr/onboarding/{checklist_id}",
        headers=admin,
        json={"employee_code": "PP101"},
    )
    assert blocked.status_code == 422, blocked.text
    assert client.get(
        f"/api/v1/hr/onboarding/{checklist_id}", headers=admin
    ).json()["employee_code"] == "PP100"

    deleted = client.delete(f"/api/v1/hr/onboarding/{checklist_id}", headers=admin)
    assert deleted.status_code == 204, deleted.text

    missing = client.get(f"/api/v1/hr/onboarding/{checklist_id}", headers=admin)
    assert missing.status_code == 404


def test_designer_cannot_delete_onboarding(client, session):
    admin = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=admin,
        json={"employee_name": "Protected Hire"},
    )
    assert created.status_code == 201
    checklist_id = created.json()["id"]

    designer = login(client, "binil@prosohm.com")
    denied = client.delete(f"/api/v1/hr/onboarding/{checklist_id}", headers=designer)
    assert denied.status_code == 403


def test_create_with_department_team_and_role(client, session):
    from app.models.models import OrgDepartment, Role, Team

    admin = login(client, "admin@prosohm.com")
    dept = session.scalar(select(OrgDepartment).where(OrgDepartment.is_active.is_(True)))
    team = session.scalar(select(Team).where(Team.is_active.is_(True)))
    role = session.scalar(select(Role).where(Role.name == "Design Engineer"))
    assert dept is not None and team is not None

    payload = {
        "employee_name": "Placement Hire",
        "org_department_id": str(dept.id),
        "team_id": str(team.id),
    }
    if role is not None:
        payload["role_id"] = str(role.id)

    created = client.post("/api/v1/hr/onboarding", headers=admin, json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["org_department_id"] == str(dept.id)
    assert body["department_name"] == dept.name
    assert body["team_id"] == str(team.id)
    assert body["team_name"] == team.name
    if role is not None:
        assert body["role_id"] == str(role.id)
        assert body["role_name"] == role.name


def test_completing_all_items_marks_checklist_complete(client, session):
    admin = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=admin,
        json={"employee_name": "Full Complete"},
    )
    assert created.status_code == 201, created.text
    checklist = created.json()
    for item in checklist["items"]:
        response = client.post(
            f"/api/v1/hr/onboarding/{checklist['id']}/items/{item['id']}/status",
            headers=admin,
            json={"status": "completed"},
        )
        assert response.status_code == 200, response.text
    final = client.get(f"/api/v1/hr/onboarding/{checklist['id']}", headers=admin)
    assert final.status_code == 200
    body = final.json()
    assert body["status"] == "completed"
    assert body["completion_percent"] == 100
    assert body["completed_at"] is not None


def test_published_onboarding_checklist_cannot_be_deleted(client, session):
    admin = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=admin,
        json={"employee_name": "Publish Lock Hire", "employee_code": "PP200"},
    )
    assert created.status_code == 201, created.text
    checklist_id = created.json()["id"]
    assert created.json()["is_published"] is False

    published = client.post(f"/api/v1/hr/onboarding/{checklist_id}/publish", headers=admin)
    assert published.status_code == 200, published.text
    assert published.json()["is_published"] is True
    assert published.json()["published_at"] is not None

    again = client.post(f"/api/v1/hr/onboarding/{checklist_id}/publish", headers=admin)
    assert again.status_code == 400

    blocked = client.delete(f"/api/v1/hr/onboarding/{checklist_id}", headers=admin)
    assert blocked.status_code == 400
    assert "cannot be deleted" in blocked.json()["detail"].lower()

    still_there = client.get(f"/api/v1/hr/onboarding/{checklist_id}", headers=admin)
    assert still_there.status_code == 200
    assert still_there.json()["is_published"] is True
