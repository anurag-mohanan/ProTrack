"""Onboarding-provisioned users must log in with the org soft-launch password."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.auth_constants import SOFT_LAUNCH_PASSWORD
from app.core.security import hash_password, verify_password
from app.models.models import Role, Team, User
from app.services.hr_onboarding_provisioning import create_user_for_onboarding
from tests.conftest import IDS, login


def _make_hr_user(session, email: str) -> User:
    role = session.scalar(select(Role).where(Role.name == "HR Manager"))
    assert role is not None
    user = User(
        id=uuid.uuid4(),
        role_id=role.id,
        email=email,
        password_hash=hash_password("Password@123"),
        first_name="Hari",
        last_name="HR",
        designation="HR Manager",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_create_user_for_onboarding_uses_soft_launch_password(session):
    user, temp_pw = create_user_for_onboarding(
        session,
        employee_name="Login Test Hire",
        email="onboard.login.test@prosohm.com",
    )
    session.commit()
    session.refresh(user)

    assert temp_pw == SOFT_LAUNCH_PASSWORD
    assert verify_password(SOFT_LAUNCH_PASSWORD, user.password_hash)
    assert user.is_active is True
    assert user.must_change_password is True


def test_onboarding_api_returns_provisioned_password_and_user_can_login(client, session):
    _make_hr_user(session, "hr-onboard-login@prosohm.com")
    hr = login(client, "hr-onboard-login@prosohm.com")

    email = "newhire.login@prosohm.com"
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={
            "employee_name": "New Hire Login",
            "employee_email": email,
            "employee_code": "PPLOGIN1",
            "joining_date": "2026-08-01",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["employee_user_id"] is not None
    assert body["provisioned_temporary_password"] == SOFT_LAUNCH_PASSWORD

    user = session.scalar(select(User).where(User.email == email))
    assert user is not None
    assert verify_password(SOFT_LAUNCH_PASSWORD, user.password_hash)

    login_ok = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
    )
    assert login_ok.status_code == 200, login_ok.text
    token = login_ok.json()["access_token"]
    assert token

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email


def test_onboarding_user_wrong_password_rejected(client, session):
    _make_hr_user(session, "hr-onboard-wrongpw@prosohm.com")
    hr = login(client, "hr-onboard-wrongpw@prosohm.com")

    email = "wrongpw.hire@prosohm.com"
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={"employee_name": "Wrong PW Hire", "employee_email": email},
    )
    assert created.status_code == 201, created.text

    denied = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "NotTheRightPassword!"},
    )
    assert denied.status_code == 401


def test_onboarding_link_existing_user_does_not_return_password(client, session):
    existing = session.get(User, IDS["user_binil"])
    assert existing is not None

    _make_hr_user(session, "hr-onboard-link@prosohm.com")
    hr = login(client, "hr-onboard-link@prosohm.com")

    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={
            "employee_name": existing.first_name + " " + existing.last_name,
            "employee_user_id": str(existing.id),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body.get("provisioned_temporary_password") is None


def test_onboarding_login_email_case_insensitive(client, session):
    _make_hr_user(session, "hr-onboard-case@prosohm.com")
    hr = login(client, "hr-onboard-case@prosohm.com")

    email = "Mixed.Case@Prosohm.com"
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={"employee_name": "Case Test", "employee_email": email},
    )
    assert created.status_code == 201, created.text

    login_ok = client.post(
        "/api/v1/auth/login",
        json={"email": "mixed.case@prosohm.com", "password": SOFT_LAUNCH_PASSWORD},
    )
    assert login_ok.status_code == 200, login_ok.text


def test_onboarding_user_can_login_while_checklist_in_progress(client, session):
    """Updating checklist items must not alter login credentials."""
    _make_hr_user(session, "hr-onboard-progress@prosohm.com")
    hr = login(client, "hr-onboard-progress@prosohm.com")

    email = "progress.flow@prosohm.com"
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={"employee_name": "Progress Flow", "employee_email": email},
    )
    assert created.status_code == 201, created.text
    checklist = created.json()

    first_item = checklist["items"][0]
    updated = client.post(
        f"/api/v1/hr/onboarding/{checklist['id']}/items/{first_item['id']}/status",
        headers=hr,
        json={"status": "completed"},
    )
    assert updated.status_code == 200, updated.text

    login_ok = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
    )
    assert login_ok.status_code == 200, login_ok.text


def test_onboarding_with_team_assigns_membership_and_login_works(client, session):
    lead = User(
        id=uuid.uuid4(),
        role_id=session.scalar(select(Role).where(Role.name == "Design Leader")).id,
        email="lead-onboard-team@prosohm.com",
        password_hash=hash_password("Password@123"),
        first_name="Lead",
        last_name="Onboard",
        designation="Design Leader",
        is_active=True,
    )
    team = Team(id=uuid.uuid4(), name="Onboard Login Team", team_lead_id=lead.id, is_active=True)
    session.add_all([lead, team])
    session.commit()

    _make_hr_user(session, "hr-onboard-team@prosohm.com")
    hr = login(client, "hr-onboard-team@prosohm.com")

    email = "team.hire@prosohm.com"
    created = client.post(
        "/api/v1/hr/onboarding",
        headers=hr,
        json={
            "employee_name": "Team Hire",
            "employee_email": email,
            "team_id": str(team.id),
        },
    )
    assert created.status_code == 201, created.text

    user = session.scalar(select(User).where(User.email == email))
    assert user is not None

    login_ok = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": SOFT_LAUNCH_PASSWORD},
    )
    assert login_ok.status_code == 200, login_ok.text
