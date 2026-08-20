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
TEMPLATE_VERSION = 2

# Responsibility owners — company-wide buckets (common for every department).
RESPONSIBILITY_LABELS: dict[str, str] = {
    "hr": "Human Resources",
    "admin": "Administration",
    "manager": "Reporting Manager",
    "it": "IT",
    "accounts": "Accounts",
}

# Map checklist owners → Help Desk ticket categories (auto-trigger on create).
RESPONSIBILITY_TICKET_CATEGORY: dict[str, str | None] = {
    "hr": "hr",
    "admin": "admin",
    "it": "it",
    "accounts": "other",
    "manager": None,  # assigned to reporting manager — no department ticket
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

# Compact company-wide PP-HRD-FO-14 structure (same for all joining departments).
PP_HRD_FO_14_STRUCTURE: list[dict[str, Any]] = [
    {
        "section": "HUMAN RESOURCES",
        "items": [
            {"text": "Offer letter sent", "responsibility": "hr"},
            {"text": "Offer letter signed & returned", "responsibility": "hr"},
            {"text": "Employee ID generated", "responsibility": "hr"},
            {"text": "HR documents filed (attested + physical)", "responsibility": "hr"},
        ],
    },
    {
        "section": "ADMINISTRATION",
        "items": [
            {"text": "Workspace / desk assigned", "responsibility": "admin"},
            {"text": "Welcome kit issued", "responsibility": "admin"},
            {"text": "ID card issued", "responsibility": "admin"},
            {"text": "Physical offer letter provided", "responsibility": "admin"},
            {"text": "Group insurance enrolment", "responsibility": "admin"},
            {"text": "Bank account opened", "responsibility": "admin"},
        ],
    },
    {
        "section": "TEAM / MANAGER",
        "items": [
            {"text": "Company announcement email sent", "responsibility": "manager"},
            {"text": "GreytHR training (leave, payslips)", "responsibility": "manager"},
            {"text": "Induction completed", "responsibility": "manager"},
            {"text": "GreytHR registration initiated", "responsibility": "manager"},
            {"text": "Training plan / document created", "responsibility": "manager"},
            {"text": "Timesheet access & training given", "responsibility": "manager"},
        ],
    },
    {
        "section": "IT",
        "items": [
            {"text": "Workstation, 3D mouse & license ready", "responsibility": "it"},
            {"text": "Email ID created & set up", "responsibility": "it"},
            {"text": "Teams account created", "responsibility": "it"},
            {"text": "Domain user created", "responsibility": "it"},
            {"text": "OneDrive access provided", "responsibility": "it"},
        ],
    },
    {
        "section": "ACCOUNTS",
        "items": [
            {"text": "Onboarding completed in HR/payroll system", "responsibility": "accounts"},
            {"text": "Employee documents received", "responsibility": "accounts"},
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
    payload = json.dumps(PP_HRD_FO_14_STRUCTURE)
    if row is None:
        row = OnboardingChecklistTemplate(
            code=FORM_CODE,
            name=FORM_TITLE,
            version=TEMPLATE_VERSION,
            structure_json=payload,
            is_active=True,
        )
        db.add(row)
        db.flush()
        return row
    if (row.version or 1) < TEMPLATE_VERSION:
        row.version = TEMPLATE_VERSION
        row.name = FORM_TITLE
        row.structure_json = payload
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
    if item.owner_user_id == user.id:
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
    if any(item.owner_user_id == user.id for item in checklist.items):
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

    if fields.get("status") == "completed":
        from app.services.training_service import assert_required_trainings_complete

        assert_required_trainings_complete(db, checklist.employee_user_id)
        if checklist.completed_at is None:
            checklist.completed_at = _utcnow()
    if fields.get("status") == "in_progress":
        checklist.completed_at = None

    db.flush()
    return checklist


def delete_checklist(db: Session, checklist: OnboardingChecklist) -> None:
    """Hard-delete a checklist and its items (cascade)."""
    db.delete(checklist)
    db.flush()


def resolve_owner_for_responsibility(
    db: Session,
    responsibility: str,
    *,
    reporting_manager_id: UUID | None,
) -> UUID | None:
    """Pick the person who should action items for a responsibility bucket."""
    from app.services import ticketing_service as tickets

    if responsibility == "manager":
        return reporting_manager_id

    category = RESPONSIBILITY_TICKET_CATEGORY.get(responsibility)
    if category:
        contact_id = tickets.category_contact_id(db, category)
        if contact_id is not None:
            return contact_id

    role_sets = {
        "hr": _HR_ROLES,
        "admin": _ADMIN_ROLES,
        "it": _IT_ROLES,
        "accounts": _ACCOUNTS_ROLES,
    }
    wanted = role_sets.get(responsibility)
    if not wanted:
        return reporting_manager_id
    from app.models.models import Role

    return db.scalar(
        select(User.id)
        .join(Role, Role.id == User.role_id)
        .where(
            User.is_active.is_(True),
            User.is_deleted.is_(False),
            Role.name.in_(wanted),
        )
        .order_by(User.last_name, User.first_name)
        .limit(1)
    )


def raise_department_tickets(
    db: Session,
    checklist: OnboardingChecklist,
    *,
    created_by: User,
) -> list[dict[str, Any]]:
    """Create one Help Desk ticket per owning department for pending items."""
    from app.models.models import Ticket
    from app.services import ticketing_service as tickets

    by_resp: dict[str, list[OnboardingChecklistItem]] = {}
    for item in checklist.items:
        if item.status == "not_applicable":
            continue
        by_resp.setdefault(item.responsibility, []).append(item)

    raised: list[dict[str, Any]] = []
    for responsibility, items in by_resp.items():
        category = RESPONSIBILITY_TICKET_CATEGORY.get(responsibility)
        if not category:
            continue
        label = RESPONSIBILITY_LABELS.get(responsibility, responsibility)
        bullet_lines = "\n".join(f"- {row.item_text}" for row in items)
        description = (
            f"Auto-created from onboarding checklist {FORM_CODE} for "
            f"{checklist.employee_name}"
            f"{f' ({checklist.employee_code})' if checklist.employee_code else ''}.\n"
            f"Joining: {checklist.joining_date or 'TBD'} · "
            f"Dept: {checklist.department_name or '—'} · "
            f"Team: {checklist.team_name or '—'} · "
            f"Role: {checklist.role_name or checklist.designation or '—'}\n"
            f"Manager: {checklist.reporting_manager_name or '—'}\n\n"
            f"Tasks for {label}:\n{bullet_lines}\n\n"
            f"Checklist id: {checklist.id}"
        )
        assignee_id = tickets.category_contact_id(db, category) or items[0].owner_user_id
        ticket = Ticket(
            ticket_number=tickets.next_ticket_number(db),
            title=f"Onboarding · {checklist.employee_name} · {label}",
            description=description,
            category=category,
            priority="medium",
            status="open",
            requester_id=created_by.id,
            assignee_id=assignee_id,
            org_department_id=tickets.default_department_id_for_category(db, category),
            location=checklist.department_name,
        )
        db.add(ticket)
        db.flush()
        for row in items:
            row.help_ticket_id = ticket.id
            if row.owner_user_id is None and assignee_id is not None:
                row.owner_user_id = assignee_id
        raised.append(
            {
                "responsibility": responsibility,
                "responsibility_label": label,
                "ticket_id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "category": category,
                "assignee_id": str(assignee_id) if assignee_id else None,
                "item_count": len(items),
            }
        )
    db.flush()
    return raised


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
    raise_tickets: bool = True,
) -> tuple[OnboardingChecklist, list[dict[str, Any]]]:
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

    manager_id = checklist.reporting_manager_id
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
            owner_id = resolve_owner_for_responsibility(
                db, responsibility, reporting_manager_id=manager_id
            )
            db.add(
                OnboardingChecklistItem(
                    checklist_id=checklist.id,
                    section=section,
                    sort_order=order,
                    item_text=text,
                    responsibility=responsibility,
                    status="pending",
                    owner_user_id=owner_id,
                )
            )
            order += 1
    db.flush()
    checklist = load_checklist(db, checklist.id) or checklist
    triggered: list[dict[str, Any]] = []
    if raise_tickets:
        triggered = raise_department_tickets(db, checklist, created_by=created_by)
    if checklist.employee_user_id is not None:
        from app.services.training_service import assign_required_onboarding_trainings

        emp = db.get(User, checklist.employee_user_id)
        if emp is not None:
            assign_required_onboarding_trainings(
                db,
                user=emp,
                checklist=checklist,
                assigned_by=created_by,
            )
    return checklist, triggered


def refresh_checklist_status(checklist: OnboardingChecklist, db: Session | None = None) -> None:
    items = list(checklist.items)
    if not items:
        return
    actionable = [i for i in items if i.status != "not_applicable"]
    if actionable and all(i.status == "completed" for i in actionable):
        if db is not None and checklist.employee_user_id is not None:
            from app.services.training_service import assert_required_trainings_complete

            assert_required_trainings_complete(db, checklist.employee_user_id)
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
    if (
        status == "completed"
        and item.responsibility == "it"
        and item.checklist is not None
        and item.checklist.employee_user_id is not None
    ):
        _maybe_provision_it_account_metadata(db, item=item, actor=actor)
    if item.checklist is not None:
        refresh_checklist_status(item.checklist, db)
    return item


def _maybe_provision_it_account_metadata(
    db: Session,
    *,
    item: OnboardingChecklistItem,
    actor: User,
) -> None:
    """Best-effort: create IT account metadata for common provisioning checklist items.

    Never stores credentials. Skips quietly if an equivalent active account exists.
    """
    from app.services import it_account_service

    text = (item.item_text or "").lower()
    account_type: str | None = None
    if "email" in text:
        account_type = "email"
    elif "domain" in text:
        account_type = "domain"
    elif "teams" in text:
        account_type = "application"
    elif "onedrive" in text:
        account_type = "application"
    if account_type is None:
        return

    user_id = item.checklist.employee_user_id
    existing = it_account_service.list_accounts(db, user_id=user_id)
    if any(
        row.account_type == account_type
        and row.status == "active"
        and (row.notes or "").find(item.item_text[:80]) >= 0
        for row in existing
    ):
        return
    if any(row.account_type == account_type and row.status == "active" for row in existing):
        # Already have an active account of this type — don't duplicate on re-complete.
        if account_type in ("email", "domain"):
            return

    employee = db.get(User, user_id)
    display = None
    username = None
    if employee is not None:
        display = f"{employee.first_name or ''} {employee.last_name or ''}".strip() or None
        username = employee.email

    it_account_service.create_account(
        db,
        actor=actor,
        user_id=user_id,
        account_type=account_type,
        username=username if account_type == "email" else None,
        display_name=display,
        notes=f"Provisioned from onboarding: {item.item_text}",
        commit=False,
    )


def load_checklist(db: Session, checklist_id: UUID) -> OnboardingChecklist | None:
    return db.scalar(
        select(OnboardingChecklist)
        .options(
            selectinload(OnboardingChecklist.items).selectinload(
                OnboardingChecklistItem.completed_by
            ),
            selectinload(OnboardingChecklist.items).selectinload(
                OnboardingChecklistItem.owner
            ),
            selectinload(OnboardingChecklist.items).selectinload(
                OnboardingChecklistItem.help_ticket
            ),
            selectinload(OnboardingChecklist.template),
            selectinload(OnboardingChecklist.employee),
            selectinload(OnboardingChecklist.reporting_manager),
            selectinload(OnboardingChecklist.created_by),
        )
        .where(OnboardingChecklist.id == checklist_id)
    )


def triggered_tickets_from_items(checklist: OnboardingChecklist) -> list[dict[str, Any]]:
    """Summarize Help Desk tickets already linked on checklist items."""
    seen: dict[str, dict[str, Any]] = {}
    for item in checklist.items:
        if item.help_ticket_id is None or item.help_ticket is None:
            continue
        key = str(item.help_ticket_id)
        if key in seen:
            seen[key]["item_count"] = int(seen[key]["item_count"]) + 1
            continue
        ticket = item.help_ticket
        seen[key] = {
            "responsibility": item.responsibility,
            "responsibility_label": RESPONSIBILITY_LABELS.get(
                item.responsibility, item.responsibility
            ),
            "ticket_id": key,
            "ticket_number": ticket.ticket_number,
            "category": ticket.category,
            "assignee_id": str(ticket.assignee_id) if ticket.assignee_id else None,
            "item_count": 1,
        }
    return list(seen.values())


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
