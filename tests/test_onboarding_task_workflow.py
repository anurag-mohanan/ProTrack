"""Onboarding task workflow: explicit statuses, request linkage, sync and audit."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.models import OnboardingChecklistItem, Role, Ticket, User
from app.services import it_provisioning_service as provisioning
from app.services import onboarding_checklist_service as onboard
from tests.conftest import DEFAULT_PASSWORD, IDS, login

BASE = "/api/v1/hr/onboarding"


def _make_user(session, role_name: str, email: str) -> User:
    role = session.scalar(select(Role).where(Role.name == role_name))
    assert role is not None
    user = User(
        id=uuid.uuid4(),
        role_id=role.id,
        email=email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        first_name="Task",
        last_name=role_name.split()[0],
        designation=role_name,
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def _create(client, headers, **extra) -> dict:
    payload = {"employee_name": "Workflow Hire", "joining_date": "2026-01-05", **extra}
    response = client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _item(body: dict, text: str) -> dict:
    return next(row for row in body["items"] if row["item_text"].startswith(text))


def _status(client, headers, checklist_id, item_id, **payload):
    return client.post(
        f"{BASE}/{checklist_id}/items/{item_id}/status", headers=headers, json=payload
    )


def test_status_model_transitions_and_reasons(client, session):
    admin = login(client, "admin@prosohm.com")
    body = _create(client, admin)
    # Ticket-required tasks start in progress (their ticket is raised); the rest wait.
    for row in body["items"]:
        expected = "in_progress" if row["execution_type"] == "TICKET_REQUIRED" else "not_started"
        assert row["status"] == expected, row["item_text"]
    assert body["resolved_items"] == 0
    assert all(row["due_date"] for row in body["items"])
    cid = body["id"]
    email = _item(body, "Email ID")

    assert _status(client, admin, cid, email["id"], status="blocked").status_code == 422
    blocked = _status(
        client, admin, cid, email["id"], status="blocked", reason="Awaiting licence approval"
    )
    assert blocked.status_code == 200, blocked.text
    row = _item(blocked.json(), "Email ID")
    assert row["status"] == "blocked"
    assert row["status_reason"] == "Awaiting licence approval"
    assert row["status_changed_by_name"]
    assert "blocked" in row["attention"]

    assert _status(client, admin, cid, email["id"], status="waived").status_code == 422
    waived = _status(client, admin, cid, email["id"], status="waived", reason="Shared mailbox")
    assert waived.status_code == 200, waived.text
    assert _item(waived.json(), "Email ID")["status"] == "waived"

    # resolved -> another resolved state must go through a reopen
    bad = _status(client, admin, cid, email["id"], status="completed")
    assert bad.status_code == 422
    reopened = _status(client, admin, cid, email["id"], status="not_started")
    assert reopened.status_code == 200
    assert _item(reopened.json(), "Email ID")["status_reason"] is None

    mouse = _item(body, "Teams")
    # A ticket-required task cannot be ticked off while its ticket is open.
    assert _status(client, admin, cid, mouse["id"], status="completed").status_code == 422
    done = _status(
        client, admin, cid, mouse["id"], status="completed", notes="Teams licence set",
        override=True, reason="Licence assigned directly in the admin centre.",
    )
    assert done.status_code == 200, done.text
    teams = _item(done.json(), "Teams")
    assert teams["completion_type"] == "manual_override"
    assert teams["completed_at"] and teams["completed_by_name"]
    na = _status(client, admin, cid, _item(body, "OneDrive")["id"], status="not_required")
    detail = na.json()
    assert detail["resolved_items"] == 2
    assert detail["completed_items"] == 1
    assert detail["completion_percent"] == round(200 / detail["total_items"])

    # Legacy values are still accepted and mapped.
    legacy = _status(client, admin, cid, _item(body, "Domain")["id"], status="not_applicable")
    assert _item(legacy.json(), "Domain")["status"] == "not_required"

    # Persistence: a fresh GET returns the same state.
    fresh = client.get(f"{BASE}/{cid}", headers=admin).json()
    assert _item(fresh, "Teams")["status"] == "completed"
    assert _item(fresh, "Teams")["notes"] == "Teams licence set"

    history = client.get(f"{BASE}/{cid}/items/{email['id']}/history", headers=admin)
    assert history.status_code == 200
    events = history.json()
    statuses = [(e["old_status"], e["new_status"]) for e in events if e["event"] == "status_changed"]
    assert ("not_started", "in_progress") in statuses  # ticket raised on create
    assert ("in_progress", "blocked") in statuses
    assert ("blocked", "waived") in statuses
    assert ("waived", "not_started") in statuses
    assert any(e["reason"] == "Shared mailbox" for e in events)
    assert events[-1]["event"] == "created"


def test_errors_and_permissions(client, session):
    admin = login(client, "admin@prosohm.com")
    body = _create(client, admin, employee_user_id=str(IDS["user_binil"]))
    cid = body["id"]
    item = _item(body, "Email ID")

    missing_item = _status(client, admin, cid, uuid.uuid4(), status="completed")
    assert missing_item.status_code == 404
    missing_checklist = _status(client, admin, uuid.uuid4(), item["id"], status="completed")
    assert missing_checklist.status_code == 404
    assert _status(client, admin, cid, item["id"], status="bogus").status_code == 422

    # The employee can view their checklist but cannot update IT tasks.
    designer = login(client, "binil@prosohm.com")
    assert client.get(f"{BASE}/{cid}", headers=designer).status_code == 200
    denied = _status(client, designer, cid, item["id"], status="completed")
    assert denied.status_code == 403
    denied_req = client.post(f"{BASE}/{cid}/items/{item['id']}/request", headers=designer, json={})
    assert denied_req.status_code == 403
    assert client.get(f"{BASE}/attention", headers=designer).status_code == 403

    # IT staff can complete IT tasks but cannot waive them.
    _make_user(session, "IT Executive", "it-exec-task@prosohm.com")
    it_user = login(client, "it-exec-task@prosohm.com")
    it_row = _item(client.get(f"{BASE}/{cid}", headers=it_user).json(), "Email ID")
    assert it_row["can_edit"] is True and it_row["can_waive"] is False
    waive = _status(client, it_user, cid, item["id"], status="waived", reason="Not needed")
    assert waive.status_code == 403
    ok = _status(
        client, it_user, cid, item["id"], status="completed",
        override=True, reason="Mailbox created before the ticket was picked up.",
    )
    assert ok.status_code == 200, ok.text


def test_workstation_completion_requires_evidence_or_override(client, session):
    admin = login(client, "admin@prosohm.com")
    body = _create(client, admin, employee_user_id=str(IDS["user_binil"]))
    cid = body["id"]
    ws = _item(body, "Workstation")
    assert ws["requires_request"] is True
    assert ws["validation_rule"] == "workstation_assigned"

    blocked = _status(client, admin, cid, ws["id"], status="completed")
    assert blocked.status_code == 422
    assert "override" in blocked.json()["detail"].lower()

    no_reason = _status(client, admin, cid, ws["id"], status="completed", override=True)
    assert no_reason.status_code == 422
    done = _status(
        client,
        admin,
        cid,
        ws["id"],
        status="completed",
        override=True,
        reason="Workstation assigned outside the IT request workflow.",
    )
    assert done.status_code == 200, done.text
    row = _item(done.json(), "Workstation")
    assert row["completion_type"] == "manual_override"
    assert row["status_reason"].startswith("Workstation assigned")


def test_request_create_then_ticket_resolution_completes_task(client, session):
    admin = login(client, "admin@prosohm.com")
    template = onboard.ensure_default_template(session)
    checklist, _ = onboard.create_checklist_from_template(
        session,
        template=template,
        employee_name="No Ticket Hire",
        created_by=session.get(User, IDS["user_admin"]),
        raise_tickets=False,
    )
    session.commit()
    cid = str(checklist.id)
    detail = client.get(f"{BASE}/{cid}", headers=admin).json()
    email = _item(detail, "Email ID")
    ws = _item(detail, "Workstation")
    assert email["help_ticket_id"] is None and email["can_create_request"] is True
    assert "request_missing" in ws["attention"]
    assert "request_missing" in email["attention"]

    tickets_before = session.scalar(select(func.count()).select_from(Ticket))
    created = client.post(
        f"{BASE}/{cid}/items/{email['id']}/request",
        headers=admin,
        json={"priority": "high", "details": "Needs M365 E3"},
    )
    assert created.status_code == 201, created.text
    row = _item(created.json(), "Email ID")
    assert row["status"] == "in_progress"
    # No IT owner is configured in the fixture: the ticket waits in the queue.
    assert row["help_ticket_number"] and row["request_status"] == "new"
    assert row["request_needs_owner"] is True
    assert row["can_create_request"] is False
    assert session.scalar(select(func.count()).select_from(Ticket)) == tickets_before + 1

    dup = client.post(f"{BASE}/{cid}/items/{email['id']}/request", headers=admin, json={})
    assert dup.status_code == 422
    assert session.scalar(select(func.count()).select_from(Ticket)) == tickets_before + 1

    ticket = session.get(Ticket, uuid.UUID(row["help_ticket_id"]))
    assert ticket.category == "it" and ticket.priority == "high"
    assert str(checklist.id) in ticket.description

    resolved = client.post(
        f"/api/v1/tickets/{ticket.id}/status",
        headers=admin,
        json={
            "status": "resolved",
            "resolution": "Mailbox created",
            "work_performed": "Created the M365 mailbox and assigned an E3 licence.",
        },
    )
    assert resolved.status_code == 200, resolved.text
    after = client.get(f"{BASE}/{cid}", headers=admin).json()
    email_after = _item(after, "Email ID")
    assert email_after["status"] == "completed"
    assert email_after["completion_type"] == "request"
    assert after["resolved_items"] == 1

    manager_item = next(r for r in after["items"] if r["responsibility"] == "manager")
    assert manager_item["can_create_request"] is False
    no_req = client.post(f"{BASE}/{cid}/items/{manager_item['id']}/request", headers=admin, json={})
    assert no_req.status_code == 422


def test_cancelled_request_blocks_task_instead_of_completing(client, session):
    admin = login(client, "admin@prosohm.com")
    body = _create(client, admin)
    cid = body["id"]
    domain = _item(body, "Domain")
    ticket_id = domain["help_ticket_id"]
    assert ticket_id

    cancelled = client.post(
        f"/api/v1/tickets/{ticket_id}/status",
        headers=admin,
        json={"status": "cancelled", "reason": "Raised against the wrong domain."},
    )
    assert cancelled.status_code == 200, cancelled.text
    after = client.get(f"{BASE}/{cid}", headers=admin).json()
    domain_row = _item(after, "Domain")
    assert domain_row["status"] == "blocked"
    assert "cancelled" in (domain_row["status_reason"] or "")
    assert domain_row["completion_type"] is None
    assert "request_cancelled" in domain_row["attention"]
    assert domain_row["can_create_request"] is True
    # Each task has its own ticket, so the other IT tasks are unaffected.
    others = [r for r in after["items"] if r["responsibility"] == "it" and r["id"] != domain["id"]]
    assert others and all(r["status"] == "in_progress" for r in others)

    replacement = client.post(f"{BASE}/{cid}/items/{domain['id']}/request", headers=admin, json={})
    assert replacement.status_code == 201, replacement.text
    row = _item(replacement.json(), "Domain")
    assert row["status"] == "in_progress"
    assert row["help_ticket_id"] != ticket_id


def test_provisioning_request_links_workstation_task_and_syncs(client, session):
    admin_user = session.get(User, IDS["user_admin"])
    employee = session.get(User, IDS["user_binil"])
    template = onboard.ensure_default_template(session)
    checklist, _ = onboard.create_checklist_from_template(
        session,
        template=template,
        employee_name="Binil",
        created_by=admin_user,
        employee_user_id=employee.id,
        raise_tickets=False,
    )
    session.commit()
    request = provisioning.create_provisioning_for_user(
        session,
        user=employee,
        created_by=admin_user,
        hardware={"computer_required": False},
        checklist_id=checklist.id,
    )
    ws = session.scalar(
        select(OnboardingChecklistItem).where(
            OnboardingChecklistItem.checklist_id == checklist.id,
            OnboardingChecklistItem.requires_request.is_(True),
        )
    )
    assert ws.help_ticket_id == request.ticket_id
    assert ws.status == "in_progress"

    provisioning.update_request_status(session, request, status="COMPLETED", actor=admin_user)
    session.refresh(ws)
    assert ws.status == "completed"
    assert ws.completion_type == "request"


def test_attention_flags_existing_orphaned_tasks(client, session):
    admin = login(client, "admin@prosohm.com")
    template = onboard.ensure_default_template(session)
    checklist, _ = onboard.create_checklist_from_template(
        session,
        template=template,
        employee_name="Legacy Hire",
        created_by=session.get(User, IDS["user_admin"]),
        raise_tickets=False,
    )
    items = {row.item_text: row for row in checklist.items}
    legacy = items["Email ID created & set up"]
    legacy.status = "pending"
    legacy.requires_request = True
    closed = Ticket(
        ticket_number="TKT-LEGACY1",
        title="Old onboarding ticket",
        category="it",
        status="closed",
        priority="medium",
        requester_id=IDS["user_admin"],
    )
    session.add(closed)
    session.flush()
    stale = items["Domain user created"]
    stale.help_ticket_id = closed.id
    session.commit()

    response = client.get(f"{BASE}/attention?responsibility=it", headers=admin)
    assert response.status_code == 200, response.text
    summary = response.json()
    by_item = {row["item_id"]: row for row in summary["items"]}
    assert "request_missing" in by_item[str(legacy.id)]["attention"]
    assert by_item[str(legacy.id)]["status"] == "not_started"
    assert "request_resolved" in by_item[str(stale.id)]["attention"]
    assert summary["counts"]["request_missing"] >= 2  # legacy email + workstation
    assert summary["counts"]["request_resolved"] >= 1

    it_dash = client.get("/api/v1/it/dashboard", headers=admin).json()
    assert it_dash["onboarding_it_attention"] >= 3

    # Reconciling the orphan by completing it directly clears the flag.
    ok = _status(
        client, admin, checklist.id, legacy.id, status="completed", notes="Done earlier",
        override=True, reason="Mailbox was created before tickets were tracked.",
    )
    assert ok.status_code == 200, ok.text
    again = client.get(f"{BASE}/attention?responsibility=it", headers=admin).json()
    assert str(legacy.id) not in {row["item_id"] for row in again["items"]}
