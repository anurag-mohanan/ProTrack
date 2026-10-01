"""Ticket workflow: lifecycle, routing, idempotency, task sync, SLA and queue."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.it_operations import StockAlert
from app.models.models import (
    OnboardingChecklistItem,
    Role,
    Ticket,
    TicketAssignmentHistory,
    TicketCategoryRoute,
    TicketNotificationLog,
    User,
)
from app.services import it_provisioning_service as provisioning
from app.services import it_stock_service as stock
from app.services import onboarding_checklist_service as onboard
from app.services import ticket_workflow_service as workflow
from tests.conftest import DEFAULT_PASSWORD, IDS, login

BASE = "/api/v1/tickets"


def _make_user(session, role_name: str, email: str, *, active: bool = True) -> User:
    role = session.scalar(select(Role).where(Role.name == role_name))
    assert role is not None
    user = User(
        id=uuid.uuid4(),
        role_id=role.id,
        email=email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        first_name="Flow",
        last_name=role_name.split()[0],
        designation=role_name,
        is_active=active,
    )
    session.add(user)
    session.commit()
    return user


def _route_it(session, primary: User | None, backup: User | None = None) -> None:
    route = session.scalar(select(TicketCategoryRoute).where(TicketCategoryRoute.category == "it"))
    if route is None:
        route = TicketCategoryRoute(category="it")
        session.add(route)
    route.assignee_user_id = primary.id if primary else None
    route.backup_user_id = backup.id if backup else None
    route.is_active = True
    session.commit()


def _raise(client, headers, **extra) -> dict:
    payload = {"title": "Monitor flickers", "category": "it", "priority": "normal", **extra}
    response = client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _status(client, headers, ticket_id, **payload):
    return client.post(f"{BASE}/{ticket_id}/status", headers=headers, json=payload)


# --- Lifecycle -----------------------------------------------------------------


def test_lifecycle_rules_are_enforced_on_the_backend(client, session):
    agent_user = _make_user(session, "IT Manager", "flow-agent@prosohm.com")
    requester = login(client, "binil@prosohm.com")
    agent = login(client, "flow-agent@prosohm.com")
    ticket = _raise(client, requester)
    assert ticket["status"] == "new"
    assert ticket["allowed_transitions"] == ["cancelled"]

    # Requesters cannot work the ticket.
    assert _status(client, requester, ticket["id"], status="in_progress").status_code == 403

    taken = client.post(f"{BASE}/{ticket['id']}/take", headers=agent)
    assert taken.status_code == 200, taken.text
    body = taken.json()
    assert body["assignee_id"] == str(agent_user.id)
    assert body["status"] == "in_progress"
    assert body["started_at"] and body["assigned_at"]
    assert "resolved" in body["allowed_transitions"]
    assert "closed" not in body["allowed_transitions"]

    # Pending needs a reason; resolving needs a summary and the work performed.
    assert _status(client, agent, ticket["id"], status="pending_vendor").status_code == 422
    waiting = _status(client, agent, ticket["id"], status="pending_vendor", reason="RMA with Dell")
    assert waiting.json()["pending_reason"] == "RMA with Dell"
    assert _status(client, agent, ticket["id"], status="resolved", resolution="Fixed").status_code == 422
    assert _status(client, agent, ticket["id"], status="closed").status_code == 422  # not from pending
    resolved = _status(
        client, agent, ticket["id"], status="resolved", resolution="Replaced panel",
        work_performed="Swapped the LCD panel under warranty.", resolution_category="fixed",
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolved_at"]

    # Requester may close (confirm) or reopen a resolved ticket.
    assert set(resolved.json()["allowed_transitions"]) >= {"closed", "open"}
    req_view = client.get(f"{BASE}/{ticket['id']}", headers=requester).json()
    assert set(req_view["allowed_transitions"]) == {"closed", "open"}
    assert _status(client, requester, ticket["id"], status="open").status_code == 422  # no reason
    reopened = _status(client, requester, ticket["id"], status="open", reason="Flicker is back")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["resolution"] is None and reopened.json()["resolved_at"] is None

    _status(
        client, agent, ticket["id"], status="resolved", resolution="Replaced cable",
        work_performed="Replaced the DisplayPort cable.",
    )
    closed = _status(client, requester, ticket["id"], status="closed")
    assert closed.status_code == 200, closed.text
    assert closed.json()["closure_reason"] == "confirmed_by_requester"
    assert closed.json()["allowed_transitions"] == []

    detail = client.get(f"{BASE}/{ticket['id']}", headers=agent).json()
    kinds = [event["kind"] for event in detail["timeline"]]
    assert "ticket_created" in kinds and "ticket_reopened" in kinds and "ticket_closed" in kinds
    assert [row["change_type"] for row in detail["assignment_history"]] == ["auto:queue", "take"]


def test_cancel_requires_reason_and_cannot_be_resolved_after(client, session):
    requester = login(client, "binil@prosohm.com")
    ticket = _raise(client, requester)
    assert _status(client, requester, ticket["id"], status="cancelled").status_code == 422
    done = _status(client, requester, ticket["id"], status="cancelled", reason="Duplicate request")
    assert done.status_code == 200
    assert done.json()["cancellation_reason"] == "Duplicate request"
    admin = login(client, "admin@prosohm.com")
    bad = _status(
        client, admin, ticket["id"], status="resolved", resolution="x", work_performed="y"
    )
    assert bad.status_code == 422


def test_category_change_must_use_transfer_with_reason(client, session):
    _make_user(session, "IT Manager", "flow-transfer@prosohm.com")
    requester = login(client, "binil@prosohm.com")
    agent = login(client, "flow-transfer@prosohm.com")
    ticket = _raise(client, requester)
    patched = client.patch(f"{BASE}/{ticket['id']}", headers=agent, json={"category": "facility"})
    assert patched.status_code == 422
    no_reason = client.post(f"{BASE}/{ticket['id']}/transfer", headers=agent, json={"category": "facility"})
    assert no_reason.status_code == 422
    moved = client.post(
        f"{BASE}/{ticket['id']}/transfer",
        headers=agent,
        json={"category": "facility", "reason": "Monitor arm is a facilities fixture"},
    )
    assert moved.status_code == 200, moved.text
    row = session.get(Ticket, uuid.UUID(ticket["id"]))
    session.refresh(row)
    assert row.category == "facility"
    history = session.scalars(
        select(TicketAssignmentHistory).where(TicketAssignmentHistory.ticket_id == row.id)
    ).all()
    assert any(h.change_type == "transfer" and h.new_group == "facility" for h in history)


# --- Routing -------------------------------------------------------------------


def test_routing_uses_primary_then_backup_then_queue(client, session):
    primary = _make_user(session, "IT Executive", "flow-primary@prosohm.com")
    backup = _make_user(session, "IT Executive", "flow-backup@prosohm.com")
    _route_it(session, primary, backup)
    requester = login(client, "binil@prosohm.com")

    first = _raise(client, requester)
    assert first["assignee_id"] == str(primary.id)
    assert first["status"] == "open" and first["needs_owner"] is False

    primary.is_active = False
    session.commit()
    second = _raise(client, requester, title="Keyboard missing keys")
    assert second["assignee_id"] == str(backup.id)

    backup.is_active = False
    session.commit()
    third = _raise(client, requester, title="Headset broken")
    assert third["assignee_id"] is None
    assert third["needs_owner"] is True and third["status"] == "new"
    # Admins are told an ownerless ticket is waiting.
    sent = session.scalars(
        select(TicketNotificationLog).where(TicketNotificationLog.ticket_id == uuid.UUID(third["id"]))
    ).all()
    assert any(row.event_key.startswith("needs_owner") for row in sent)
    assert any(row.user_id == IDS["user_admin"] for row in sent)


def test_subcategory_rule_beats_category_route(client, session):
    general = _make_user(session, "IT Executive", "flow-general@prosohm.com")
    licensing = _make_user(session, "IT Executive", "flow-licence@prosohm.com")
    _route_it(session, general)
    admin = login(client, "admin@prosohm.com")
    rule = client.post(
        f"{BASE}/routing-rules",
        headers=admin,
        json={"category": "it", "subcategory": "software.license", "primary_user_id": str(licensing.id)},
    )
    assert rule.status_code == 201, rule.text
    requester = login(client, "binil@prosohm.com")
    lic = _raise(client, requester, title="Need Visio", subcategory="software.license")
    other = _raise(client, requester, title="Printer jam", subcategory="hardware.peripheral")
    assert lic["assignee_id"] == str(licensing.id)
    assert other["assignee_id"] == str(general.id)

    designer = login(client, "binil@prosohm.com")
    assert client.get(f"{BASE}/routing-rules", headers=designer).status_code == 403


# --- Idempotency ---------------------------------------------------------------


def test_create_is_idempotent_on_key(session):
    admin = session.get(User, IDS["user_admin"])
    first, created = workflow.create_ticket(
        session, title="Restock", category="it", requester=admin, idempotency_key="test:key:1"
    )
    again, created_again = workflow.create_ticket(
        session, title="Restock again", category="it", requester=admin, idempotency_key="test:key:1"
    )
    session.commit()
    assert created is True and created_again is False
    assert first.id == again.id
    assert session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.idempotency_key == "test:key:1")
    ) == 1


def test_onboarding_refresh_does_not_duplicate_task_tickets(client, session):
    admin_user = session.get(User, IDS["user_admin"])
    template = onboard.ensure_default_template(session)
    checklist, _ = onboard.create_checklist_from_template(
        session, template=template, employee_name="Idem Hire", created_by=admin_user
    )
    session.commit()
    before = session.scalar(select(func.count()).select_from(Ticket))
    onboard.raise_task_tickets(session, checklist, created_by=admin_user)
    onboard.raise_task_tickets(session, checklist, created_by=admin_user)
    session.commit()
    assert session.scalar(select(func.count()).select_from(Ticket)) == before
    keys = session.scalars(
        select(Ticket.idempotency_key).where(Ticket.idempotency_key.like("onboarding_task:%"))
    ).all()
    assert len(keys) == len(set(keys))


def test_provisioning_reuses_workstation_ticket(client, session):
    admin_user = session.get(User, IDS["user_admin"])
    employee = session.get(User, IDS["user_binil"])
    template = onboard.ensure_default_template(session)
    checklist, _ = onboard.create_checklist_from_template(
        session, template=template, employee_name="Binil", created_by=admin_user,
        employee_user_id=employee.id,
    )
    session.commit()
    ws = session.scalar(
        select(OnboardingChecklistItem).where(
            OnboardingChecklistItem.checklist_id == checklist.id,
            OnboardingChecklistItem.validation_rule == "workstation_assigned",
        )
    )
    assert ws.help_ticket_id is not None
    before = session.scalar(select(func.count()).select_from(Ticket))
    request = provisioning.create_provisioning_for_user(
        session, user=employee, created_by=admin_user,
        hardware={"computer_required": False}, checklist_id=checklist.id,
    )
    session.commit()
    assert request.ticket_id == ws.help_ticket_id
    assert session.scalar(select(func.count()).select_from(Ticket)) == before

    provisioning.update_request_status(session, request, status="COMPLETED", actor=admin_user)
    session.commit()
    ticket = session.get(Ticket, request.ticket_id)
    session.refresh(ticket)
    session.refresh(ws)
    assert ticket.status == "resolved" and ticket.work_performed
    assert ws.status == "completed" and ws.completion_type == "request"


# --- Ticket -> task sync ---------------------------------------------------------


def test_ticket_status_drives_task_status(client, session):
    admin = login(client, "admin@prosohm.com")
    created = client.post("/api/v1/hr/onboarding", headers=admin, json={"employee_name": "Sync Hire"})
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    email = next(i for i in created.json()["items"] if i["item_text"].startswith("Email ID"))
    tid = email["help_ticket_id"]

    def task_status() -> dict:
        body = client.get(f"/api/v1/hr/onboarding/{cid}", headers=admin).json()
        return next(i for i in body["items"] if i["id"] == email["id"])

    assert task_status()["status"] == "in_progress"
    _status(client, admin, tid, status="pending_requester", reason="Need preferred alias")
    row = task_status()
    assert row["status"] == "waiting" and "Need preferred alias" in row["status_reason"]
    _status(client, admin, tid, status="in_progress")
    assert task_status()["status"] == "in_progress"
    _status(client, admin, tid, status="resolved", resolution="Mailbox live", work_performed="Created mailbox")
    row = task_status()
    assert row["status"] == "completed" and row["completion_type"] == "request"
    _status(client, admin, tid, status="open", reason="Wrong display name")
    assert task_status()["status"] == "in_progress"
    _status(client, admin, tid, status="cancelled", reason="Raised in error")
    row = task_status()
    # A cancelled ticket never completes a mandatory task.
    assert row["status"] == "blocked" and row["completion_type"] is None


def test_closed_rule_waits_for_closure(client, session):
    admin_user = session.get(User, IDS["user_admin"])
    template = onboard.ensure_default_template(session)
    checklist, _ = onboard.create_checklist_from_template(
        session, template=template, employee_name="Close Rule", created_by=admin_user
    )
    session.commit()
    item = next(i for i in checklist.items if i.item_text.startswith("Domain"))
    item.completion_rule = "closed"
    session.commit()
    ticket = item.help_ticket
    workflow.transition(session, ticket, to_status="resolved", actor=admin_user,
                        resolution="Account created", work_performed="Created AD account")
    session.commit()
    session.refresh(item)
    assert item.status == "in_progress"
    workflow.transition(session, ticket, to_status="closed", actor=admin_user)
    session.commit()
    session.refresh(item)
    assert item.status == "completed"


def test_repair_link_raises_missing_ticket(client, session):
    admin_user = session.get(User, IDS["user_admin"])
    template = onboard.ensure_default_template(session)
    checklist, _ = onboard.create_checklist_from_template(
        session, template=template, employee_name="Repair Hire", created_by=admin_user,
        raise_tickets=False,
    )
    session.commit()
    item = next(i for i in checklist.items if i.item_text.startswith("Domain"))
    admin = login(client, "admin@prosohm.com")
    row = next(
        i for i in client.get(f"/api/v1/hr/onboarding/{checklist.id}", headers=admin).json()["items"]
        if i["id"] == str(item.id)
    )
    assert row["can_repair_link"] is True and "request_missing" in row["attention"]
    repaired = client.post(f"/api/v1/hr/onboarding/{checklist.id}/items/{item.id}/repair-link", headers=admin)
    assert repaired.status_code == 200, repaired.text
    fixed = next(i for i in repaired.json()["checklist"]["items"] if i["id"] == str(item.id))
    assert fixed["help_ticket_id"] and fixed["status"] == "in_progress"
    assert repaired.json()["actions"]


# --- Low stock -----------------------------------------------------------------


def test_low_stock_ticket_is_deduplicated_and_auto_resolved(client, session):
    admin = session.get(User, IDS["user_admin"])
    employee = session.get(User, IDS["user_binil"])
    item = stock.create_item(
        session, actor=admin,
        data={"name": f"Flow Mouse {uuid4().hex[:4]}", "item_kind": "mouse", "min_stock": 2, "target_stock": 10},
        opening_qty=3,
    )
    session.commit()
    stock.issue(session, item, actor=admin, quantity=2, employee_user_id=employee.id)
    session.commit()
    alert = session.scalar(select(StockAlert).where(StockAlert.item_id == item.id))
    key = f"it_stock_alert:{alert.id}"
    assert session.scalar(select(func.count()).select_from(Ticket).where(Ticket.idempotency_key == key)) == 1

    # Re-evaluating (e.g. a dashboard refresh path) never adds tickets.
    stock.evaluate_alert(session, item, actor=admin)
    stock.evaluate_alert(session, item, actor=None)
    session.commit()
    assert session.scalar(select(func.count()).select_from(Ticket).where(Ticket.idempotency_key == key)) == 1

    stock.issue(session, item, actor=admin, quantity=1, employee_user_id=employee.id)
    session.commit()
    ticket = session.scalar(select(Ticket).where(Ticket.idempotency_key == key))
    assert ticket.priority == "urgent"

    stock.receive(session, item, actor=admin, quantity=10, purchase_order="PO-FLOW")
    session.commit()
    session.refresh(ticket)
    assert ticket.status == "resolved" and ticket.work_performed


# --- SLA -----------------------------------------------------------------------


def test_sla_sweep_alerts_once(session):
    admin = session.get(User, IDS["user_admin"])
    agent = _make_user(session, "IT Executive", "flow-sla@prosohm.com")
    ticket, _ = workflow.create_ticket(
        session, title="Slow VPN", category="it", requester=admin, assignee_id=agent.id, priority="high"
    )
    session.commit()
    assert ticket.sla_due_at is not None
    later = ticket.sla_due_at + timedelta(hours=10)
    first = workflow.run_sla_sweep(session, now=later)
    session.commit()
    second = workflow.run_sla_sweep(session, now=later + timedelta(minutes=5))
    session.commit()
    assert first["overdue"] >= 1
    assert second["overdue"] == 0
    session.refresh(ticket)
    assert ticket.escalation_level == 1


# --- Queue / permissions ----------------------------------------------------------


def test_queue_views_filters_and_summary(client, session):
    agent_user = _make_user(session, "IT Manager", "flow-queue@prosohm.com")
    requester = login(client, "binil@prosohm.com")
    agent = login(client, "flow-queue@prosohm.com")
    hw = _raise(client, requester, title="Dock not charging", subcategory="hardware.peripheral", priority="urgent")
    sw = _raise(client, requester, title="Need Revit licence", subcategory="software.license")
    client.post(f"{BASE}/{hw['id']}/take", headers=agent)

    summary = client.get(f"{BASE}/queue/summary?category=it", headers=agent).json()["counts"]
    assert summary["hardware"] >= 1 and summary["software"] >= 1
    assert summary["high"] >= 1 and summary["mine"] >= 1 and summary["unassigned"] >= 1

    def numbers(query: str) -> set[str]:
        response = client.get(f"{BASE}/queue?{query}", headers=agent)
        assert response.status_code == 200, response.text
        return {row["ticket_number"] for row in response.json()["items"]}

    assert hw["ticket_number"] in numbers("view=mine")
    assert sw["ticket_number"] not in numbers("view=mine")
    assert sw["ticket_number"] in numbers("view=unassigned")
    assert hw["ticket_number"] in numbers("view=hardware") and sw["ticket_number"] not in numbers("view=hardware")
    assert sw["ticket_number"] in numbers("view=software")
    assert hw["ticket_number"] in numbers("priority=urgent")
    assert hw["ticket_number"] in numbers(f"q={hw['ticket_number']}")
    assert sw["ticket_number"] in numbers("q=Revit")
    assert hw["ticket_number"] in numbers(f"assignee={agent_user.id}")
    page = client.get(f"{BASE}/queue?page=1&page_size=1", headers=agent).json()
    assert len(page["items"]) == 1 and page["total"] >= 2

    csv_response = client.get(f"{BASE}/export.csv?category=it", headers=agent)
    assert csv_response.status_code == 200 and hw["ticket_number"] in csv_response.text
    assert client.get(f"{BASE}/export.csv", headers=requester).status_code == 403


def test_permissions_are_enforced_server_side(client, session):
    requester = login(client, "binil@prosohm.com")
    other = login(client, "ranjith@prosohm.com")
    ticket = _raise(client, requester)
    assert client.post(f"{BASE}/{ticket['id']}/take", headers=other).status_code == 403
    assert client.post(f"{BASE}/{ticket['id']}/take", headers=requester).status_code == 403
    assert client.post(
        f"{BASE}/{ticket['id']}/assign", headers=requester, json={"assignee_id": str(IDS["user_binil"])}
    ).status_code == 403
    assert client.post(
        f"{BASE}/{ticket['id']}/comments", headers=other, json={"body": "hi"}
    ).status_code == 403
    assert client.get(f"{BASE}/reports/summary", headers=requester).status_code == 403
    assert client.get(f"{BASE}/reconciliation", headers=requester).status_code == 403
    assert client.put(f"{BASE}/routes/it", headers=requester, json={}).status_code == 403
    me = client.get(f"{BASE}/me", headers=requester).json()
    assert me["is_agent"] is False and me["can_configure"] is False


def test_employee_tickets_hide_internal_detail_from_hr(client, session):
    _make_user(session, "HR Manager", "flow-hr@prosohm.com")
    admin = login(client, "admin@prosohm.com")
    created = _raise(client, admin, affected_user_id=str(IDS["user_binil"]), title="Laptop for Binil")
    client.post(
        f"{BASE}/{created['id']}/comments", headers=admin,
        json={"body": "Serial ABC internal", "is_internal": True},
    )
    hr = login(client, "flow-hr@prosohm.com")
    rows = client.get(f"{BASE}/employee/{IDS['user_binil']}", headers=hr)
    assert rows.status_code == 200, rows.text
    row = next(r for r in rows.json() if r["id"] == created["id"])
    assert row["can_open"] is False
    assert client.get(f"{BASE}/{created['id']}", headers=hr).status_code == 403
    outsider = login(client, "ranjith@prosohm.com")
    assert client.get(f"{BASE}/employee/{IDS['user_binil']}", headers=outsider).status_code == 403


def test_template_config_is_admin_editable_and_validated(client, session):
    admin = login(client, "admin@prosohm.com")
    templates = client.get("/api/v1/hr/onboarding/templates", headers=admin).json()
    tid = templates[0]["id"]
    config = client.get(f"/api/v1/hr/onboarding/templates/{tid}/config", headers=admin)
    assert config.status_code == 200, config.text
    assert config.json()["responsibilities"]["it"] == "IT"
    caps = client.get("/api/v1/hr/onboarding/capabilities", headers=admin)
    assert caps.status_code == 200 and caps.json() == {"can_configure_templates": True}
    rows = config.json()["items"]
    welcome = next(r for r in rows if r["execution_type"] == "OPTIONAL")
    payload = {k: welcome[k] for k in (
        "execution_type", "responsibility", "owner_role", "priority", "due_offset_days",
        "evidence_required", "confirm_by", "reversible", "mandatory", "blocks_completion",
        "ticket_category", "ticket_subcategory", "completion_rule",
    )}
    url = f"/api/v1/hr/onboarding/templates/{tid}/items/{welcome['section_index']}/{welcome['item_index']}"
    bad = client.put(url, headers=admin, json={**payload, "execution_type": "AUTOMATED"})
    assert bad.status_code == 422
    ok = client.put(url, headers=admin, json={**payload, "execution_type": "CHECKLIST_ONLY", "evidence_required": True})
    assert ok.status_code == 200, ok.text
    updated = next(
        r for r in ok.json()["items"]
        if (r["section_index"], r["item_index"]) == (welcome["section_index"], welcome["item_index"])
    )
    assert updated["execution_type"] == "CHECKLIST_ONLY" and updated["evidence_required"] is True
    designer = login(client, "binil@prosohm.com")
    assert client.put(url, headers=designer, json=payload).status_code == 403


def test_due_dates_use_server_clock(session):
    admin = session.get(User, IDS["user_admin"])
    ticket, _ = workflow.create_ticket(session, title="Clock", category="it", requester=admin, priority="urgent")
    session.commit()
    assert ticket.sla_due_at is not None
    assert ticket.sla_due_at - datetime.utcnow() <= timedelta(hours=8, minutes=1)
