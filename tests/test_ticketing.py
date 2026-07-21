"""Help-desk / ticketing system (phase 52).

Covers the full ticket lifecycle over the API: any employee can raise and track
their own ticket; category routing means IT / HR agents only see the queues they
own; Admin sees everything; comments support agent-only internal notes; and the
status lifecycle (assign, resolve, cancel, reopen) is permission-gated.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.security import hash_password
from app.models.models import Role, User
from tests.conftest import DEFAULT_PASSWORD, login


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


def _create_ticket(client, headers, *, category="it", title="Laptop will not boot", priority="high"):
    response = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "title": title,
            "category": category,
            "priority": priority,
            "description": "Detailed description of the issue.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Creation + self visibility
# ---------------------------------------------------------------------------
def test_employee_can_raise_and_track_own_ticket(client, session):
    headers = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, headers)

    assert ticket["ticket_number"].startswith("TKT-")
    assert ticket["status"] == "open"
    assert ticket["category"] == "it"
    assert ticket["can_manage"] is False

    listing = client.get("/api/v1/tickets?scope=mine", headers=headers)
    assert listing.status_code == 200
    numbers = {row["ticket_number"] for row in listing.json()}
    assert ticket["ticket_number"] in numbers

    detail = client.get(f"/api/v1/tickets/{ticket['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["comments"] == []


def test_ticket_numbers_are_unique(client, session):
    headers = login(client, "binil@prosohm.com")
    first = _create_ticket(client, headers, title="First")
    second = _create_ticket(client, headers, title="Second")
    assert first["ticket_number"] != second["ticket_number"]


# ---------------------------------------------------------------------------
# Category routing / queue visibility
# ---------------------------------------------------------------------------
def test_non_agent_cannot_see_another_users_ticket(client, session):
    requester = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, requester, category="it")

    # A Surfacer is not an IT agent and did not raise the ticket.
    other = login(client, "ranjith@prosohm.com")
    detail = client.get(f"/api/v1/tickets/{ticket['id']}", headers=other)
    assert detail.status_code == 403

    listing = client.get("/api/v1/tickets", headers=other)
    assert listing.status_code == 200
    assert ticket["ticket_number"] not in {r["ticket_number"] for r in listing.json()}


def test_it_agent_sees_and_manages_it_queue(client, session):
    _make_user(session, "IT Manager", "itmgr@prosohm.com")
    requester = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, requester, category="it")

    agent = login(client, "itmgr@prosohm.com")
    listing = client.get("/api/v1/tickets", headers=agent)
    assert listing.status_code == 200
    rows = {r["ticket_number"]: r for r in listing.json()}
    assert ticket["ticket_number"] in rows
    assert rows[ticket["ticket_number"]]["can_manage"] is True


def test_hr_agent_does_not_see_it_ticket(client, session):
    _make_user(session, "HR Manager", "hrmgr@prosohm.com")
    requester = login(client, "binil@prosohm.com")
    it_ticket = _create_ticket(client, requester, category="it")

    agent = login(client, "hrmgr@prosohm.com")
    listing = client.get("/api/v1/tickets", headers=agent)
    assert it_ticket["ticket_number"] not in {r["ticket_number"] for r in listing.json()}


def test_admin_sees_every_category(client, session):
    requester = login(client, "binil@prosohm.com")
    it_ticket = _create_ticket(client, requester, category="it")
    hr_ticket = _create_ticket(client, requester, category="hr", title="Payslip query")

    admin = login(client, "admin@prosohm.com")
    listing = client.get("/api/v1/tickets?status=all", headers=admin)
    numbers = {r["ticket_number"] for r in listing.json()}
    assert it_ticket["ticket_number"] in numbers
    assert hr_ticket["ticket_number"] in numbers


# ---------------------------------------------------------------------------
# Agent workflow: assign + status
# ---------------------------------------------------------------------------
def test_agent_assign_and_resolve_lifecycle(client, session):
    agent_user = _make_user(session, "IT Manager", "itmgr2@prosohm.com")
    requester = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, requester, category="it")

    agent = login(client, "itmgr2@prosohm.com")

    assigned = client.post(
        f"/api/v1/tickets/{ticket['id']}/assign",
        headers=agent,
        json={"assignee_id": str(agent_user.id)},
    )
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()
    assert body["assignee_id"] == str(agent_user.id)
    # Picking up an open ticket moves it into progress.
    assert body["status"] == "in_progress"

    resolved = client.post(
        f"/api/v1/tickets/{ticket['id']}/status",
        headers=agent,
        json={"status": "resolved", "resolution": "Replaced the RAM module."},
    )
    assert resolved.status_code == 200, resolved.text
    resolved_body = resolved.json()
    assert resolved_body["status"] == "resolved"
    assert resolved_body["resolution"] == "Replaced the RAM module."
    assert resolved_body["resolved_at"] is not None


# ---------------------------------------------------------------------------
# Permission gates on updates / status
# ---------------------------------------------------------------------------
def test_requester_cannot_change_restricted_fields(client, session):
    headers = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, headers)

    # Descriptive edit on own open ticket is allowed.
    ok = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=headers,
        json={"title": "Laptop won't boot at all"},
    )
    assert ok.status_code == 200, ok.text

    # Status change is an agent-only action.
    denied = client.patch(
        f"/api/v1/tickets/{ticket['id']}",
        headers=headers,
        json={"status": "resolved"},
    )
    assert denied.status_code == 403


def test_requester_can_cancel_own_ticket(client, session):
    headers = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, headers)
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/status",
        headers=headers,
        json={"status": "cancelled"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Comments + internal-note visibility
# ---------------------------------------------------------------------------
def test_internal_notes_hidden_from_requester(client, session):
    _make_user(session, "IT Manager", "itmgr3@prosohm.com")
    requester = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, requester, category="it")

    agent = login(client, "itmgr3@prosohm.com")
    internal = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        headers=agent,
        json={"body": "Ordered replacement part internally.", "is_internal": True},
    )
    assert internal.status_code == 201, internal.text
    assert internal.json()["is_internal"] is True

    public = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        headers=agent,
        json={"body": "We are working on it.", "is_internal": False},
    )
    assert public.status_code == 201

    # Requester sees only the public comment.
    req_detail = client.get(f"/api/v1/tickets/{ticket['id']}", headers=requester)
    bodies = {c["body"] for c in req_detail.json()["comments"]}
    assert "We are working on it." in bodies
    assert "Ordered replacement part internally." not in bodies

    # Agent sees both.
    agent_detail = client.get(f"/api/v1/tickets/{ticket['id']}", headers=agent)
    agent_bodies = {c["body"] for c in agent_detail.json()["comments"]}
    assert "Ordered replacement part internally." in agent_bodies


def test_requester_internal_flag_is_ignored(client, session):
    headers = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, headers)
    # A plain requester cannot post an internal (private) note — flag is stripped.
    response = client.post(
        f"/api/v1/tickets/{ticket['id']}/comments",
        headers=headers,
        json={"body": "Any update?", "is_internal": True},
    )
    assert response.status_code == 201, response.text
    assert response.json()["is_internal"] is False


# ---------------------------------------------------------------------------
# Module gate + stats
# ---------------------------------------------------------------------------
def test_help_desk_is_available_to_every_user(client, session):
    """Ticketing is company-wide — even the Planning Board account can use it."""
    headers = login(client, "planning-board@prosohm.com")
    response = client.get("/api/v1/tickets", headers=headers)
    assert response.status_code == 200, response.text


def test_stats_reflect_visible_tickets(client, session):
    headers = login(client, "binil@prosohm.com")
    _create_ticket(client, headers)
    response = client.get("/api/v1/tickets/stats", headers=headers)
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["raised_by_me"] >= 1
    assert stats["open"] >= 1


# ---------------------------------------------------------------------------
# Per-category routing (admin-configured contact)
# ---------------------------------------------------------------------------
def test_admin_can_list_and_set_category_routes(client, session):
    admin = login(client, "admin@prosohm.com")

    listing = client.get("/api/v1/tickets/routes", headers=admin)
    assert listing.status_code == 200, listing.text
    categories = {row["category"] for row in listing.json()}
    assert {"it", "facility", "admin", "hr", "other"} <= categories


def test_non_admin_cannot_view_routes(client, session):
    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/tickets/routes", headers=headers)
    assert response.status_code == 403


def test_configured_contact_receives_and_manages_ticket(client, session):
    # A non-IT-role user is nominated as the IT contact.
    contact = _make_user(session, "Surfacer", "itcontact@prosohm.com", first="Ivy", last="Contact")

    admin = login(client, "admin@prosohm.com")
    set_route = client.put(
        "/api/v1/tickets/routes/it",
        headers=admin,
        json={"assignee_user_id": str(contact.id)},
    )
    assert set_route.status_code == 200, set_route.text
    assert set_route.json()["assignee_user_id"] == str(contact.id)

    requester = login(client, "binil@prosohm.com")
    ticket = _create_ticket(client, requester, category="it")
    # Auto-assigned to the configured contact on creation.
    assert ticket["assignee_id"] == str(contact.id)

    # The contact can see and manage the ticket even without an IT agent role.
    contact_headers = login(client, "itcontact@prosohm.com")
    listing = client.get("/api/v1/tickets", headers=contact_headers)
    rows = {r["ticket_number"]: r for r in listing.json()}
    assert ticket["ticket_number"] in rows
    assert rows[ticket["ticket_number"]]["can_manage"] is True


def test_setting_unknown_category_is_rejected(client, session):
    admin = login(client, "admin@prosohm.com")
    response = client.put(
        "/api/v1/tickets/routes/nonsense",
        headers=admin,
        json={"assignee_user_id": None},
    )
    assert response.status_code == 404


def test_invalid_category_is_rejected(client, session):
    headers = login(client, "binil@prosohm.com")
    response = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={"title": "Bad category", "category": "nonsense"},
    )
    assert response.status_code == 422
