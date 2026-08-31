"""HR Process Control — user create on start, leader notify, process audit."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.security import hash_password, verify_password
from app.models.enums import NotificationType
from app.models.models import ExitInterview, Notification, Role, Team, User
from app.services.hr_process_audit_service import build_process_audit
from tests.conftest import DEFAULT_PASSWORD, login


def _make_user(
    session,
    role_name: str,
    email: str,
    first: str = "Test",
    last: str = "User",
    *,
    team_id=None,
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
        team_id=team_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_onboarding_creates_user_and_notifies_team_lead(client, session):
    lead = _make_user(session, "Design Leader", "lead-hrpc@prosohm.com", first="Lara", last="Lead")
    team = Team(id=uuid.uuid4(), name="HRPC Team", team_lead_id=lead.id, is_active=True)
    session.add(team)
    session.commit()

    _make_user(session, "HR Manager", "hrmgr-hrpc@prosohm.com", first="Hari", last="HR")
    hr = login(client, "hrmgr-hrpc@prosohm.com")

    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={
            "employee_name": "New Hire One",
            "employee_email": "newhire.one@prosohm.com",
            "employee_code": "PP200",
            "joining_date": "2026-07-01",
            "team_id": str(team.id),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["employee_user_id"] is not None
    assert body["team_id"] == str(team.id)

    user = session.get(User, uuid.UUID(body["employee_user_id"]))
    assert user is not None
    assert user.email == "newhire.one@prosohm.com"
    assert user.must_change_password is True
    assert verify_password(SOFT_LAUNCH_PASSWORD, user.password_hash)
    role = session.get(Role, user.role_id)
    assert role is not None
    assert role.name == "Designer"

    notes = session.scalars(
        select(Notification).where(
            Notification.user_id == lead.id,
            Notification.notification_type == NotificationType.new_hire_onboarding,
        )
    ).all()
    assert len(notes) >= 1


def test_onboarding_duplicate_email_blocked(client, session):
    _make_user(session, "Designer", "dup.hire@prosohm.com", first="Dup", last="Hire")
    _make_user(session, "HR Manager", "hrmgr-dup@prosohm.com", first="Hari", last="HR")
    hr = login(client, "hrmgr-dup@prosohm.com")

    response = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={
            "employee_name": "Dup Hire",
            "employee_email": "dup.hire@prosohm.com",
        },
    )
    assert response.status_code == 422
    assert "already exists" in response.json()["detail"].lower()


def test_process_audit_flags(client, session):
    _make_user(session, "HR Manager", "hrmgr-audit@prosohm.com", first="Hari", last="HR")
    hr = login(client, "hrmgr-audit@prosohm.com")

    # Incomplete onboarding past SLA + orphan placement
    old = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={
            "employee_name": "Late Orphan",
            "employee_email": "late.orphan@prosohm.com",
            "joining_date": (date.today() - timedelta(days=30)).isoformat(),
        },
    )
    assert old.status_code == 201, old.text

    # Missing exit: inactive user without completed exit
    leaver = _make_user(session, "Designer", "leaver@prosohm.com", first="Lee", last="Ver")
    leaver.is_active = False
    leaver.leaving_date = date.today() - timedelta(days=2)
    session.add(leaver)
    session.commit()

    # Exit done still active
    stayer = _make_user(session, "Designer", "stayer@prosohm.com", first="Stay", last="Er")
    exit_row = ExitInterview(
        id=uuid.uuid4(),
        employee_user_id=stayer.id,
        employee_name="Stay Er",
        status="completed",
        completed_at=datetime.utcnow(),
        answers_json="{}",
    )
    session.add(exit_row)
    session.commit()

    audit = client.get("/api/v1/hr/process-audit", headers=hr)
    assert audit.status_code == 200, audit.text
    body = audit.json()
    flags = {item["flag"] for item in body["items"]}
    assert "incomplete_onboarding" in flags
    assert "orphan_placement" in flags
    assert "missing_exit" in flags
    assert "exit_done_still_active" in flags

    # Service-level sanity
    built = build_process_audit(session, sla_days=14)
    assert built["total"] >= 4


def test_process_audit_forbidden_for_designer(client, session):
    _make_user(session, "Designer", "des-audit@prosohm.com", first="Dee", last="Sign")
    designer = login(client, "des-audit@prosohm.com")
    response = client.get("/api/v1/hr/process-audit", headers=designer)
    assert response.status_code == 403
