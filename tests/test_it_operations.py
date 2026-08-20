"""IT Operations MVP — permissions, asset lifecycle, IP allocation, credentials."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core.access_control import (
    ALL_SPECIAL_PERMISSIONS,
    MODULE_IT_OPERATIONS,
    SPECIAL_ALLOCATE_IT_IPS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_GENERATE_IT_CREDENTIALS,
    SPECIAL_MANAGE_IT_ASSETS,
    SPECIAL_MANAGE_IT_NETWORKS,
    SPECIAL_VIEW_IT_OPERATIONS,
)
from app.core.security import hash_password
from app.models.enums import ActivityAction
from app.models.it_operations import AssetAssignment, IPAssignmentHistory
from app.models.models import Activity, Role, User
from app.services.employee_offboard_service import confirm_and_set_leaving_date
from app.services.it_deprovision_service import OFFBOARD_TICKET_MARKER, find_open_offboard_ticket
from tests.conftest import DEFAULT_PASSWORD, IDS, login


def _grant_it_access(session, user: User, *, specials: list[str] | None = None) -> None:
    modules = [MODULE_IT_OPERATIONS]
    user.module_access = json.dumps(modules)
    if specials is not None:
        user.special_permissions = json.dumps(specials)
    session.add(user)
    session.commit()
    session.refresh(user)


def _make_user(
    session,
    role_name: str,
    email: str,
    *,
    first: str = "IT",
    last: str = "Tester",
) -> User:
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


def _first_asset_type_id(client, headers) -> str:
    response = client.get("/api/v1/it/asset-types", headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert rows, "asset types should be seeded by phase81"
    return rows[0]["id"]


def test_admin_can_access_it_dashboard(client):
    response = client.get("/api/v1/it/dashboard", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "total_assets" in body
    assert "pending_onboarding_tasks" in body


def test_employee_without_it_module_cannot_list_assets(client, session):
    employee = _make_user(session, "Designer", "it-denied@prosohm.com")
    employee.module_access = json.dumps(["dashboard", "projects", "timesheets"])
    employee.special_permissions = json.dumps([])
    session.add(employee)
    session.commit()
    headers = login(client, employee.email)
    response = client.get("/api/v1/it/assets", headers=headers)
    assert response.status_code == 403


def test_view_permission_can_read_but_not_create_asset(client, session):
    viewer = _make_user(session, "Designer", "it-viewer@prosohm.com")
    _grant_it_access(session, viewer, specials=[SPECIAL_VIEW_IT_OPERATIONS])
    headers = login(client, viewer.email)

    listing = client.get("/api/v1/it/assets", headers=headers)
    assert listing.status_code == 200, listing.text

    create = client.post(
        "/api/v1/it/assets",
        headers=headers,
        json={"asset_type_id": _first_asset_type_id(client, client.auth_headers), "make": "Dell"},
    )
    assert create.status_code == 403


def test_asset_number_unique_and_assignment_history(client, session):
    type_id = _first_asset_type_id(client, client.auth_headers)
    created = client.post(
        "/api/v1/it/assets",
        headers=client.auth_headers,
        json={
            "asset_type_id": type_id,
            "make": "Lenovo",
            "model": "T14",
            "serial_number": f"SN-{uuid.uuid4().hex[:8]}",
        },
    )
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["asset_number"]
    assert asset["status"] == "available"

    assignee_id = str(IDS["user_anurag"])
    assigned = client.post(
        f"/api/v1/it/assets/{asset['id']}/assign",
        headers=client.auth_headers,
        json={"user_id": assignee_id, "notes": "Day-1 laptop"},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["returned_date"] is None

    detail = client.get(f"/api/v1/it/assets/{asset['id']}", headers=client.auth_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "assigned"

    history = client.get(
        f"/api/v1/it/assets/{asset['id']}/assignments",
        headers=client.auth_headers,
    )
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) >= 1
    assert rows[0]["returned_date"] is None

    returned = client.post(
        f"/api/v1/it/assets/{asset['id']}/return",
        headers=client.auth_headers,
        json={"return_condition": "good", "notes": "Returned after loan"},
    )
    assert returned.status_code == 200, returned.text

    detail2 = client.get(f"/api/v1/it/assets/{asset['id']}", headers=client.auth_headers)
    assert detail2.json()["status"] == "available"

    history2 = client.get(
        f"/api/v1/it/assets/{asset['id']}/assignments",
        headers=client.auth_headers,
    )
    assert history2.json()[0]["returned_date"] is not None

    # History rows are append-only — assignment count never shrinks on return.
    assert session.scalar(
        select(AssetAssignment).where(AssetAssignment.asset_id == uuid.UUID(asset["id"]))
    ) is not None
    count = len(
        session.scalars(
            select(AssetAssignment).where(AssetAssignment.asset_id == uuid.UUID(asset["id"]))
        ).all()
    )
    assert count >= 1


def test_computer_name_generated_uniquely(client):
    type_id = _first_asset_type_id(client, client.auth_headers)
    # Prefer a computer-category type when available
    types = client.get("/api/v1/it/asset-types", headers=client.auth_headers).json()
    laptop = next((row for row in types if row["code"] == "LAPTOP"), types[0])
    type_id = laptop["id"]

    first = client.post(
        "/api/v1/it/computers",
        headers=client.auth_headers,
        json={"asset_type_id": type_id, "make": "Dell", "os": "Windows 11", "ram_gb": 16},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/v1/it/computers",
        headers=client.auth_headers,
        json={"asset_type_id": type_id, "make": "HP", "os": "Windows 11", "ram_gb": 32},
    )
    assert second.status_code == 201, second.text
    assert first.json()["computer_name"] != second.json()["computer_name"]


def test_ip_allocate_and_release_preserves_history(client, session):
    network = client.post(
        "/api/v1/it/networks",
        headers=client.auth_headers,
        json={
            "name": f"Lab LAN {uuid.uuid4().hex[:6]}",
            "cidr": "10.66.66.0/29",
            "gateway": "10.66.66.1",
        },
    )
    assert network.status_code == 201, network.text
    network_id = network.json()["id"]

    ips = client.get(f"/api/v1/it/networks/{network_id}/ips", headers=client.auth_headers)
    assert ips.status_code == 200, ips.text
    available = [row for row in ips.json() if row["status"] == "available"]
    assert available, "network should auto-generate usable IPs for /29"

    allocated = client.post(
        "/api/v1/it/ips/allocate",
        headers=client.auth_headers,
        json={
            "ip_address_id": available[0]["id"],
            "hostname": "lab-host-1",
            "assigned_to_user_id": str(IDS["user_anurag"]),
        },
    )
    assert allocated.status_code == 200, allocated.text
    assert allocated.json()["status"] == "allocated"
    ip_id = allocated.json()["id"]

    # Second allocation of same IP must fail
    conflict = client.post(
        "/api/v1/it/ips/allocate",
        headers=client.auth_headers,
        json={"ip_address_id": ip_id, "hostname": "lab-host-2"},
    )
    assert conflict.status_code in (400, 409, 422)

    released = client.post(
        f"/api/v1/it/ips/{ip_id}/release",
        headers=client.auth_headers,
        json={"notes": "Lab teardown"},
    )
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "available"

    history = session.scalars(
        select(IPAssignmentHistory).where(IPAssignmentHistory.ip_address_id == uuid.UUID(ip_id))
    ).all()
    assert len(history) >= 1
    assert history[0].released_date is not None


def test_credential_generation_does_not_store_secret(client, session):
    payload = {
        "user_id": str(IDS["user_anurag"]),
        "account_type": "domain",
        "username": f"user{uuid.uuid4().hex[:6]}",
    }
    response = client.post(
        "/api/v1/it/accounts/generate-credential",
        headers=client.auth_headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("one_time_password")
    assert "password" not in json.dumps(body).lower().replace("one_time_password", "")

    # Re-fetch account list — secret must not appear
    accounts = client.get(
        f"/api/v1/it/accounts?user_id={IDS['user_anurag']}",
        headers=client.auth_headers,
    )
    assert accounts.status_code == 200
    dumped = json.dumps(accounts.json()).lower()
    assert body["one_time_password"].lower() not in dumped

    # Audit must not contain the secret
    activities = session.scalars(
        select(Activity).where(Activity.action == ActivityAction.it_credential_generated)
    ).all()
    assert activities
    for activity in activities:
        blob = f"{activity.old_value or ''}{activity.new_value or ''}"
        assert body["one_time_password"] not in blob


def test_profile_me_available_without_it_module(client, session):
    employee = _make_user(session, "Designer", "it-profile@prosohm.com")
    employee.module_access = json.dumps(["dashboard", "projects", "timesheets"])
    employee.special_permissions = json.dumps([])
    session.add(employee)
    session.commit()
    headers = login(client, employee.email)
    response = client.get("/api/v1/it/profile/me", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == str(employee.id)


def test_offboard_creates_it_deprovision_ticket(client, session):
    type_id = _first_asset_type_id(client, client.auth_headers)
    asset_resp = client.post(
        "/api/v1/it/assets",
        headers=client.auth_headers,
        json={"asset_type_id": type_id, "make": "ExitLoan"},
    )
    assert asset_resp.status_code == 201, asset_resp.text
    asset_id = asset_resp.json()["id"]

    employee = _make_user(session, "Designer", "it-leaver@prosohm.com", first="Leaving", last="Soon")
    assign = client.post(
        f"/api/v1/it/assets/{asset_id}/assign",
        headers=client.auth_headers,
        json={"user_id": str(employee.id)},
    )
    assert assign.status_code == 200, assign.text

    admin = session.get(User, IDS["user_admin"]) if "user_admin" in IDS else None
    if admin is None:
        admin = session.scalar(select(User).where(User.email == "admin@prosohm.com"))
    assert admin is not None

    confirm_and_set_leaving_date(
        session,
        user_id=employee.id,
        leaving_date=date.today() + timedelta(days=14),
        actor=admin,
        confirm_left_organisation=True,
        commit=True,
    )

    ticket = find_open_offboard_ticket(session, employee.id)
    assert ticket is not None
    assert OFFBOARD_TICKET_MARKER in ticket.title
    assert str(employee.id) in (ticket.description or "")


def test_open_it_requests_report(client):
    # Ensure at least one IT ticket exists
    ticket = client.post(
        "/api/v1/tickets",
        headers=client.auth_headers,
        json={
            "title": "IT Ops report probe",
            "category": "it",
            "priority": "low",
            "description": "Created by IT MVP test",
        },
    )
    assert ticket.status_code == 201, ticket.text

    report = client.get("/api/v1/it/reports/open-requests", headers=client.auth_headers)
    assert report.status_code == 200, report.text
    numbers = {row.get("ticket_number") for row in report.json()}
    assert ticket.json()["ticket_number"] in numbers


def test_special_permission_constants_registered():
    for key in (
        SPECIAL_VIEW_IT_OPERATIONS,
        SPECIAL_MANAGE_IT_ASSETS,
        SPECIAL_ASSIGN_IT_ASSETS,
        SPECIAL_MANAGE_IT_NETWORKS,
        SPECIAL_ALLOCATE_IT_IPS,
        SPECIAL_GENERATE_IT_CREDENTIALS,
    ):
        assert key in ALL_SPECIAL_PERMISSIONS


def test_customer_owned_asset_return_excludes_from_current(client, session):
    from app.core.access_control import SPECIAL_RETURN_CUSTOMER_ASSETS
    from app.models.models import Customer

    customer = session.scalar(select(Customer).limit(1))
    assert customer is not None

    type_id = _first_asset_type_id(client, client.auth_headers)
    created = client.post(
        "/api/v1/it/assets",
        headers=client.auth_headers,
        json={
            "asset_type_id": type_id,
            "make": "Dell",
            "model": "CustOwned",
            "purchased_by": "customer",
            "owner_customer_id": str(customer.id),
        },
    )
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["purchased_by"] == "customer"
    assert asset["owner_customer_id"] == str(customer.id)

    current = client.get(
        "/api/v1/it/assets",
        headers=client.auth_headers,
        params={"inventory_scope": "current"},
    )
    assert current.status_code == 200
    assert any(row["id"] == asset["id"] for row in current.json()["items"])

    returned = client.post(
        f"/api/v1/it/assets/{asset['id']}/return-to-customer",
        headers=client.auth_headers,
        json={
            "condition_at_return": "good",
            "received_by_name": "Customer receiver",
            "return_reason": "Project ended",
        },
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["owner_customer_id"] == str(customer.id)

    current2 = client.get(
        "/api/v1/it/assets",
        headers=client.auth_headers,
        params={"inventory_scope": "current"},
    )
    assert current2.status_code == 200
    assert all(row["id"] != asset["id"] for row in current2.json()["items"])

    hist = client.get(
        "/api/v1/it/assets",
        headers=client.auth_headers,
        params={"inventory_scope": "returned"},
    )
    assert hist.status_code == 200
    assert any(row["id"] == asset["id"] for row in hist.json()["items"])

    events = client.get(
        "/api/v1/it/assets/customer-returns",
        headers=client.auth_headers,
    )
    assert events.status_code == 200, events.text
    assert any(row["asset_id"] == asset["id"] for row in events.json())

    report = client.get(
        "/api/v1/it/reports/customer-returns",
        headers=client.auth_headers,
    )
    assert report.status_code == 200, report.text
    assert any(row["asset_number"] == asset["asset_number"] for row in report.json())

    delete = client.delete(
        f"/api/v1/it/assets/{asset['id']}",
        headers=client.auth_headers,
    )
    assert delete.status_code == 422

    assert SPECIAL_RETURN_CUSTOMER_ASSETS in ALL_SPECIAL_PERMISSIONS
