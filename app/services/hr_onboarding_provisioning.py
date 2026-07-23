"""Create User + notify team leader when onboarding starts (HR Process Control)."""

from __future__ import annotations

import secrets
import string
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.timesheet_eligibility import default_requires_timesheet_for_role
from app.core.salary_eligibility import default_requires_salary_for_role
from app.crud.team import sync_user_team_membership
from app.models.enums import EntityType, NotificationType
from app.models.models import OnboardingChecklist, Role, Team, User
from app.services.kpi_participation import apply_defaults_for_user

PROVISIONAL_ROLE_NAME = "Designer"


def _generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def split_employee_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "New", "Hire"
    if len(parts) == 1:
        return parts[0][:100], "Hire"
    return parts[0][:100], " ".join(parts[1:])[:100]


def resolve_provisional_role_id(db: Session, role_id: UUID | None) -> UUID:
    if role_id is not None:
        role = db.get(Role, role_id)
        if role is None:
            raise ValueError("Role not found.")
        return role.id
    role = db.scalar(select(Role).where(Role.name == PROVISIONAL_ROLE_NAME))
    if role is None:
        role = db.scalar(select(Role).order_by(Role.name).limit(1))
    if role is None:
        raise ValueError("No roles configured; cannot create user.")
    return role.id


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(
            func.lower(User.email) == email.strip().lower(),
            User.is_deleted.is_(False),
        )
    )


def create_user_for_onboarding(
    db: Session,
    *,
    employee_name: str,
    email: str,
    role_id: UUID | None = None,
    team_id: UUID | None = None,
    manager_id: UUID | None = None,
    joining_date: date | None = None,
    designation: str | None = None,
    department_id: UUID | None = None,
) -> tuple[User, str]:
    """Create active User with temp password. Flushes only (no commit)."""
    cleaned = email.strip().lower()
    if not cleaned or "@" not in cleaned:
        raise ValueError("A valid employee email is required to create a user account.")
    existing = find_user_by_email(db, cleaned)
    if existing is not None:
        raise ValueError(
            f"A user with email {cleaned} already exists. "
            "Link the existing user instead of creating a duplicate."
        )

    resolved_role_id = resolve_provisional_role_id(db, role_id)
    role = db.get(Role, resolved_role_id)
    role_name = role.name if role is not None else PROVISIONAL_ROLE_NAME
    first_name, last_name = split_employee_name(employee_name)
    temporary_password = _generate_temporary_password()

    # Prefer team lead as manager when not provided.
    resolved_manager_id = manager_id
    if resolved_manager_id is None and team_id is not None:
        team = db.get(Team, team_id)
        if team is not None and team.team_lead_id is not None:
            resolved_manager_id = team.team_lead_id

    user = User(
        role_id=resolved_role_id,
        email=cleaned,
        first_name=first_name,
        last_name=last_name,
        designation=designation or role_name,
        manager_id=resolved_manager_id,
        team_id=None,
        department_id=department_id,
        joining_date=joining_date,
        is_active=True,
        must_change_password=True,
        password_hash=hash_password(temporary_password),
        requires_timesheet=default_requires_timesheet_for_role(role_name),
        requires_salary=default_requires_salary_for_role(role_name),
    )
    db.add(user)
    db.flush()
    apply_defaults_for_user(db, user, reset_kpi_flags=True)
    sync_user_team_membership(db, user.id, team_id)
    db.flush()
    return user, temporary_password


def resolve_notify_recipient_id(
    db: Session,
    *,
    team_id: UUID | None,
    reporting_manager_id: UUID | None,
) -> UUID | None:
    """Prefer team lead; fallback reporting manager."""
    if team_id is not None:
        team = db.get(Team, team_id)
        if team is not None and team.team_lead_id is not None:
            lead = db.get(User, team.team_lead_id)
            if lead is not None and lead.is_active and not lead.is_deleted:
                return lead.id
    if reporting_manager_id is not None:
        mgr = db.get(User, reporting_manager_id)
        if mgr is not None and mgr.is_active and not mgr.is_deleted:
            return mgr.id
    return None


def notify_team_leader_of_new_hire(
    db: Session,
    checklist: OnboardingChecklist,
    *,
    created_by: User | None = None,
) -> dict[str, Any]:
    """In-app + email notify for team leader / reporting manager. May commit via email/notif."""
    recipient_id = resolve_notify_recipient_id(
        db,
        team_id=checklist.team_id,
        reporting_manager_id=checklist.reporting_manager_id,
    )
    if recipient_id is None:
        return {"notified": False, "reason": "no_leader"}

    joining = checklist.joining_date.isoformat() if checklist.joining_date else "TBD"
    team_label = checklist.team_name or "unassigned team"
    title = f"New hire joined: {checklist.employee_name}"
    message = (
        f"{checklist.employee_name} has started onboarding"
        f"{f' ({checklist.employee_code})' if checklist.employee_code else ''}. "
        f"Team: {team_label}. Joining date: {joining}. "
        "Please set their role and access in Users, then complete your manager "
        "onboarding checklist items."
    )
    onboarding_path = "/hr/onboarding"
    users_path = "/admin/users"

    from app.services.notification_service import create_notification

    create_notification(
        db,
        user_id=recipient_id,
        notification_type=NotificationType.new_hire_onboarding,
        title=title,
        message=message,
        entity_type=EntityType.user,
        entity_id=checklist.employee_user_id,
        email_context={
            "EmployeeName": checklist.employee_name,
            "TeamName": team_label,
            "JoiningDate": joining,
            "OnboardingUrl": onboarding_path,
            "UsersUrl": users_path,
            "Message": message,
            "Title": title,
            "ToolNumber": checklist.employee_code or checklist.employee_name,
        },
        send_email=True,
        commit=True,
    )
    return {
        "notified": True,
        "recipient_id": str(recipient_id),
        "created_by_id": str(created_by.id) if created_by else None,
    }