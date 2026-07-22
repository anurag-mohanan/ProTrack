"""Onboarding checklist service — PP-HRD-FO-14 New Hire Onboarding Checklist."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import EXECUTIVE_ROLES
from app.core.permissions import get_role_name, is_admin
from app.models.models import (
    OnboardingChecklist,
    OnboardingChecklistItem,
    OnboardingChecklistTemplate,
    User,
)

FORM_CODE = "PP-HRD-FO-14"
FORM_TITLE = "New Hire Onboarding Checklist"

# Responsibility owners — mapped from the Excel RESPONSIBILITY column
# (DINESH → hr/it by context, ADMIN, MANAGER, ACCOUNTS).
RESPONSIBILITY_LABELS: dict[str, str] = {
    "hr": "Human Resources",
    "admin": "Administration",
    "manager": "Reporting Manager",
    "it": "IT",
    "accounts": "Accounts",
    "engineering": "Engineering",
}

STATUS_LABELS: dict[str, str] = {
    "pending": "Pending",
    "completed": "Completed",
    "not_applicable": "N/A",
}

CHECKLIST_STATUS_LABELS: dict[str, str] = {
    "in_progress": "In Progress",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

# Structure mirrors PP-HRD-FO-14_ONBOARDING_CHECKLIST Excel
# (sections + items with default responsibility).
PP_HRD_FO_14_STRUCTURE: list[dict[str, Any]] = [
    {
        "section": "HUMAN RESOURCES",
        "items": [
            {"text": "Offer letter sent to candidate", "responsibility": "hr"},
            {"text": "Offer letter signed and submitted by candidate", "responsibility": "hr"},
            {"text": "Secure / designate space", "responsibility": "admin"},
            {"text": "Generate employee ID number", "responsibility": "hr"},
            {
                "text": "Welcome kit provided (Diary, water bottle, mug, pens, T-shirt)",
                "responsibility": "admin",
            },
            {"text": "ID card provided", "responsibility": "admin"},
            {
                "text": "Training provided to use GreytHR (leaves, payslips etc)",
                "responsibility": "manager",
            },
            {
                "text": "Send out a company wide email announcing new hire, with their name & position",
                "responsibility": "manager",
            },
            {"text": "Physical copy of offer letter given", "responsibility": "admin"},
            {"text": "Employee added to group insurance", "responsibility": "admin"},
            {"text": "Onboarding kit available", "responsibility": "admin"},
            {
                "text": "File all HR related documents (attested and physical copy)",
                "responsibility": "admin",
            },
        ],
    },
    {
        "section": "ENGINEERING",
        "items": [
            {
                "text": "Are IT setup completed? (Workstation, 3D mouse, license)",
                "responsibility": "manager",
            },
            {"text": "Induction program completed", "responsibility": "manager"},
            {
                "text": "Initiate new hire registration in HR system (GreytHR)",
                "responsibility": "manager",
            },
            {"text": "Individual training document created", "responsibility": "manager"},
            {
                "text": "Individual timesheets provided and training given on using them",
                "responsibility": "manager",
            },
        ],
    },
    {
        "section": "IT",
        "items": [
            {"text": "Email ID created & setup on workstation", "responsibility": "it"},
            {"text": "Teams account created", "responsibility": "it"},
            {"text": "Domain user created", "responsibility": "it"},
            {"text": "OneDrive access provided", "responsibility": "it"},
        ],
    },
    {
        "section": "ACCOUNTS",
        "items": [
            {"text": "Onboarding process through HR system", "responsibility": "accounts"},
            {
                "text": "All onboarding documents submitted by employee",
                "responsibility": "accounts",
            },
            {"text": "Bank account opened (HDFC Bank)", "responsibility": "admin"},
            {"text": "Payroll structure created", "responsibility": "accounts"},
        ],
    },
]

_HR_ROLES = frozenset(
    {"Director of HR", "HR Manager", "HR Executive", "HR", "HR Assistant"}
)
_ADMIN_ROLES = frozenset({"Admin", "Office Administrator", "System Administrator"})
_IT_ROLES = frozenset(
    {
        "Director of IT",
        "IT Manager",
        "System Administrator",
        "IT Executive",
        "IT Support Engineer",
    }
)
_ACCOUNTS_ROLES = frozenset(
    {
        "Director of Accounts",
        "Accounts Manager",
        "Accounts Executive",
        "Accountant",
        "Finance Manager",
    }
)
_MANAGER_ROLES = frozenset(
    {
        "Engineering Manager",
        "Design Leader",
        "Team Leader",
        "Director of Engineering",
        "Managing Director",
    }
)


def _utcnow() -> datetime:
    return datetime.utcnow()


def parse_structure(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return list(PP_HRD_FO_14_STRUCTURE)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return list(PP_HRD_FO_14_STRUCTURE)
    if isinstance(data, list):
        return data
    return list(PP_HRD_FO_14_STRUCTURE)


def ensure_default_template(db: Session) -> OnboardingChecklistTemplate:
    row = db.scalar(
        select(OnboardingChecklistTemplate).where(
            OnboardingChecklistTemplate.code == FORM_CODE
        )
    )
    if row is not None:
        return row
    row = OnboardingChecklistTemplate(
        code=FORM_CODE,
        name=FORM_TITLE,
        version=1,
        structure_json=json.dumps(PP_HRD_FO_14_STRUCTURE),
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def can_manage_onboarding(db: Session, user: User) -> bool:
    if is_admin(db, user):
        return True
    role = get_role_name(db, user)
    if role in EXECUTIVE_ROLES:
        return True
    return role in (_HR_ROLES | _ADMIN_ROLES)


def responsibilities_for_user(db: Session, user: User) -> set[str]:
    """Which responsibility buckets this user may mark complete."""
    if is_admin(db, user) or get_role_name(db, user) in EXECUTIVE_ROLES:
        return set(RESPONSIBILITY_LABELS.keys())
    role = get_role_name(db, user)
    owned: set[str] = set()
    if role in _HR_ROLES:
        owned.add("hr")
    if role in _ADMIN_ROLES:
        owned.add("admin")
    if role in _IT_ROLES:
        owned.add("it")
    if role in _ACCOUNTS_ROLES:
        owned.add("accounts")
    if role in _MANAGER_ROLES or role in _HR_ROLES or role in _ADMIN_ROLES:
        owned.add("manager")
        owned.add("engineering")
    # HR managers can update any item on checklists they oversee.
    if role in _HR_ROLES:
        owned.update(RESPONSIBILITY_LABELS.keys())
    return owned


def can_edit_item(db: Session, user: User, item: OnboardingChecklistItem) -> bool:
    if can_manage_onboarding(db, user):
        return True
    return item.responsibility in responsibilities_for_user(db, user)


def can_view_checklist(db: Session, user: User, checklist: OnboardingChecklist) -> bool:
    if can_manage_onboarding(db, user):
        return True
    if checklist.employee_user_id == user.id:
        return True
    if checklist.reporting_manager_id == user.id:
        return True
    if checklist.created_by_id == user.id:
        return True
    # Anyone who owns at least one responsibility bucket can open checklists
    # to complete their section items.
    return bool(responsibilities_for_user(db, user))


def resolve_placement_fields(
    db: Session,
    *,
    org_department_id: UUID | None = None,
    team_id: UUID | None = None,
    role_id: UUID | None = None,
    reporting_manager_id: UUID | None = None,
    reporting_manager_name: str | None = None,
    department_name: str | None = None,
    designation: str | None = None,
    fill_manager_from_team: bool = True,
) -> dict[str, object | None]:
    """Resolve denormalized names for department / team / role / manager."""
    from app.models.models import OrgDepartment, Role, Team

    team_name: str | None = None
    role_name: str | None = None
    resolved_manager_id = reporting_manager_id
    resolved_manager_name = reporting_manager_name
    resolved_department_name = department_name
    resolved_designation = designation

    if team_id is not None:
        team = db.get(Team, team_id)
        if team is None:
            raise ValueError("Team not found.")
        team_name = team.name
        if fill_manager_from_team and resolved_manager_id is None and team.team_lead_id is not None:
            resolved_manager_id = team.team_lead_id

    if role_id is not None:
        role = db.get(Role, role_id)
        if role is None:
            raise ValueError("Role not found.")
        role_name = role.name
        if not resolved_designation:
            resolved_designation = role.name

    if org_department_id is not None:
        dept = db.get(OrgDepartment, org_department_id)
        if dept is None:
            raise ValueError("Department not found.")
        if not resolved_department_name:
            resolved_department_name = dept.name

    if resolved_manager_id and not resolved_manager_name:
        mgr = db.get(User, resolved_manager_id)
        if mgr is not None:
            resolved_manager_name = f"{mgr.first_name} {mgr.last_name}".strip()

    return {
        "org_department_id": org_department_id,
        "department_name": resolved_department_name,
        "team_id": team_id,
        "team_name": team_name if team_id is not None else None,
        "role_id": role_id,
        "role_name": role_name if role_id is not None else None,
        "reporting_manager_id": resolved_manager_id,
        "reporting_manager_name": resolved_manager_name if resolved_manager_id else None,
        "designation": resolved_designation,
    }


def apply_checklist_header(
    db: Session,
    checklist: OnboardingChecklist,
    fields: dict[str, object | None],
) -> OnboardingChecklist:
    """Apply header/placement updates and keep denormalized names consistent."""
    simple_fields = {
        "employee_name",
        "employee_user_id",
        "employee_code",
        "joining_date",
        "notes",
        "status",
    }
    for key in simple_fields:
        if key in fields:
            value = fields[key]
            if key == "employee_name" and isinstance(value, str):
                value = value.strip()
            setattr(checklist, key, value)

    placement_keys = {
        "org_department_id",
        "team_id",
        "role_id",
        "reporting_manager_id",
        "reporting_manager_name",
        "department_name",
        "designation",
    }
    if any(key in fields for key in placement_keys):
        placement = resolve_placement_fields(
            db,
            org_department_id=(
                fields["org_department_id"]  # type: ignore[arg-type]
                if "org_department_id" in fields
                else checklist.org_department_id
            ),
            team_id=(
                fields["team_id"]  # type: ignore[arg-type]
                if "team_id" in fields
                else checklist.team_id
            ),
            role_id=(
                fields["role_id"]  # type: ignore[arg-type]
                if "role_id" in fields
                else checklist.role_id
            ),
            reporting_manager_id=(
                fields["reporting_manager_id"]  # type: ignore[arg-type]
                if "reporting_manager_id" in fields
                else checklist.reporting_manager_id
            ),
            reporting_manager_name=(
                fields["reporting_manager_name"]  # type: ignore[arg-type]
                if "reporting_manager_name" in fields
                else checklist.reporting_manager_name
            ),
            department_name=(
                fields["department_name"]  # type: ignore[arg-type]
                if "department_name" in fields
                else checklist.department_name
            ),
            designation=(
                fields["designation"]  # type: ignore[arg-type]
                if "designation" in fields
                else checklist.designation
            ),
            fill_manager_from_team="reporting_manager_id" not in fields,
        )
        for key, value in placement.items():
            setattr(checklist, key, value)

    if fields.get("status") == "completed" and checklist.completed_at is None:
        checklist.completed_at = _utcnow()
    if fields.get("status") == "in_progress":
        checklist.completed_at = None

    db.flush()
    return checklist


def delete_checklist(db: Session, checklist: OnboardingChecklist) -> None:
    """Hard-delete a checklist and its items (cascade)."""
    db.delete(checklist)
    db.flush()


def create_checklist_from_template(
    db: Session,
    *,
    template: OnboardingChecklistTemplate,
    employee_name: str,
    created_by: User,
    employee_user_id: UUID | None = None,
    employee_code: str | None = None,
    joining_date: date | None = None,
    designation: str | None = None,
    department_name: str | None = None,
    org_department_id: UUID | None = None,
    team_id: UUID | None = None,
    role_id: UUID | None = None,
    reporting_manager_id: UUID | None = None,
    reporting_manager_name: str | None = None,
    notes: str | None = None,
) -> OnboardingChecklist:
    if employee_user_id and (not designation or not employee_code):
        emp = db.get(User, employee_user_id)
        if emp is not None:
            designation = designation or emp.designation

    placement = resolve_placement_fields(
        db,
        org_department_id=org_department_id,
        team_id=team_id,
        role_id=role_id,
        reporting_manager_id=reporting_manager_id,
        reporting_manager_name=reporting_manager_name,
        department_name=department_name,
        designation=designation,
        fill_manager_from_team=reporting_manager_id is None,
    )

    checklist = OnboardingChecklist(
        template_id=template.id,
        employee_user_id=employee_user_id,
        employee_name=employee_name.strip(),
        employee_code=(employee_code or None),
        joining_date=joining_date,
        notes=notes,
        created_by_id=created_by.id,
        status="in_progress",
        **placement,  # type: ignore[arg-type]
    )
    db.add(checklist)
    db.flush()

    structure = parse_structure(template.structure_json)
    order = 0
    for section_row in structure:
        section = str(section_row.get("section") or "GENERAL")
        for item_row in section_row.get("items") or []:
            text = str(item_row.get("text") or "").strip()
            if not text:
                continue
            responsibility = str(item_row.get("responsibility") or "hr").strip().lower()
            if responsibility not in RESPONSIBILITY_LABELS:
                responsibility = "hr"
            db.add(
                OnboardingChecklistItem(
                    checklist_id=checklist.id,
                    section=section,
                    sort_order=order,
                    item_text=text,
                    responsibility=responsibility,
                    status="pending",
                )
            )
            order += 1
    db.flush()
    return checklist


def refresh_checklist_status(checklist: OnboardingChecklist) -> None:
    items = list(checklist.items)
    if not items:
        return
    actionable = [i for i in items if i.status != "not_applicable"]
    if actionable and all(i.status == "completed" for i in actionable):
        checklist.status = "completed"
        checklist.completed_at = checklist.completed_at or _utcnow()
    elif checklist.status == "completed":
        checklist.status = "in_progress"
        checklist.completed_at = None


def set_item_status(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    status: str,
    actor: User,
    completion_date: date | None = None,
    notes: str | None = None,
) -> OnboardingChecklistItem:
    if status not in STATUS_LABELS:
        raise ValueError(f"Invalid item status: {status}")
    item.status = status
    if notes is not None:
        item.notes = notes
    if status == "completed":
        item.completed_by_id = actor.id
        item.completion_date = completion_date or date.today()
    elif status == "pending":
        item.completed_by_id = None
        item.completion_date = None
    else:
        # N/A
        item.completed_by_id = actor.id
        item.completion_date = completion_date or date.today()
    db.flush()
    if item.checklist is not None:
        refresh_checklist_status(item.checklist)
    return item


def load_checklist(db: Session, checklist_id: UUID) -> OnboardingChecklist | None:
    return db.scalar(
        select(OnboardingChecklist)
        .options(
            selectinload(OnboardingChecklist.items).selectinload(
                OnboardingChecklistItem.completed_by
            ),
            selectinload(OnboardingChecklist.template),
            selectinload(OnboardingChecklist.employee),
            selectinload(OnboardingChecklist.reporting_manager),
            selectinload(OnboardingChecklist.created_by),
        )
        .where(OnboardingChecklist.id == checklist_id)
    )


def completion_stats(checklist: OnboardingChecklist) -> dict[str, int]:
    items = list(checklist.items)
    total = len(items)
    completed = sum(1 for i in items if i.status == "completed")
    pending = sum(1 for i in items if i.status == "pending")
    na = sum(1 for i in items if i.status == "not_applicable")
    actionable = total - na
    percent = int(round((completed / actionable) * 100)) if actionable else 100
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "not_applicable": na,
        "percent": percent,
    }
