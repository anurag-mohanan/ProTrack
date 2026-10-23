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
from app.services import onboarding_task_service as tasks

FORM_CODE = "PP-HRD-FO-14"
FORM_TITLE = "New Hire Onboarding Checklist"
TEMPLATE_VERSION = 4

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

STATUS_LABELS: dict[str, str] = dict(tasks.STATUS_LABELS)

CHECKLIST_STATUS_LABELS: dict[str, str] = {
    "in_progress": "In Progress",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

# Compact company-wide PP-HRD-FO-14 structure (same for all joining departments).
# Execution keys are defaults for new templates; admins edit them per template.
PP_HRD_FO_14_STRUCTURE: list[dict[str, Any]] = [
    {
        "section": "HUMAN RESOURCES",
        "items": [
            {"text": "Offer letter sent", "responsibility": "hr", "execution_type": "CHECKLIST_ONLY"},
            {
                "text": "Offer letter signed & returned",
                "responsibility": "hr",
                "execution_type": "EXTERNAL_DEPENDENCY",
                "evidence_required": True,
            },
            {
                "text": "Employee ID generated",
                "responsibility": "hr",
                "execution_type": "AUTOMATED",
                "validation": "employee_code_present",
            },
            {
                "text": "HR documents filed (attested + physical)",
                "responsibility": "hr",
                "execution_type": "CHECKLIST_ONLY",
                "evidence_required": True,
            },
        ],
    },
    {
        "section": "ADMINISTRATION",
        "items": [
            {"text": "Workspace / desk assigned", "responsibility": "admin", "execution_type": "CHECKLIST_ONLY"},
            {"text": "Welcome kit issued", "responsibility": "admin", "execution_type": "OPTIONAL", "mandatory": False, "blocks_completion": False},
            {"text": "ID card issued", "responsibility": "admin", "execution_type": "CHECKLIST_ONLY"},
            {"text": "Physical offer letter provided", "responsibility": "admin", "execution_type": "CHECKLIST_ONLY"},
            {"text": "Group insurance enrolment", "responsibility": "admin", "execution_type": "EXTERNAL_DEPENDENCY", "evidence_required": True},
            {"text": "Bank account opened", "responsibility": "admin", "execution_type": "EXTERNAL_DEPENDENCY", "evidence_required": True},
        ],
    },
    {
        "section": "TEAM / MANAGER",
        "items": [
            {"text": "Company announcement email sent", "responsibility": "manager", "execution_type": "CHECKLIST_ONLY"},
            {"text": "GreytHR training (leave, payslips)", "responsibility": "manager", "execution_type": "CHECKLIST_ONLY"},
            {"text": "Induction completed", "responsibility": "manager", "execution_type": "APPROVAL_REQUIRED", "confirm_by": "manager"},
            {"text": "GreytHR registration initiated", "responsibility": "manager", "execution_type": "CHECKLIST_ONLY"},
            {"text": "Training plan / document created", "responsibility": "manager", "execution_type": "CHECKLIST_ONLY"},
            {"text": "Timesheet access & training given", "responsibility": "manager", "execution_type": "CHECKLIST_ONLY"},
        ],
    },
    {
        "section": "IT",
        "items": [
            {
                "text": "Workstation, 3D mouse & license ready",
                "responsibility": "it",
                "requires_request": True,
                "validation": "workstation_assigned",
                "execution_type": "TICKET_REQUIRED",
                "ticket_category": "it",
                "ticket_subcategory": "hardware.computer",
                "priority": "high",
            },
            {
                "text": "Email ID created & set up",
                "responsibility": "it",
                "execution_type": "TICKET_REQUIRED",
                "ticket_category": "it",
                "ticket_subcategory": "access.email",
            },
            {
                "text": "Teams account created",
                "responsibility": "it",
                "execution_type": "TICKET_REQUIRED",
                "ticket_category": "it",
                "ticket_subcategory": "access.collaboration",
            },
            {
                "text": "Domain user created",
                "responsibility": "it",
                "execution_type": "TICKET_REQUIRED",
                "ticket_category": "it",
                "ticket_subcategory": "access.domain",
            },
            {
                "text": "OneDrive access provided",
                "responsibility": "it",
                "execution_type": "TICKET_REQUIRED",
                "ticket_category": "it",
                "ticket_subcategory": "access.storage",
            },
        ],
    },
    {
        "section": "ACCOUNTS",
        "items": [
            {"text": "Onboarding completed in HR/payroll system", "responsibility": "accounts", "execution_type": "CHECKLIST_ONLY"},
            {"text": "Employee documents received", "responsibility": "accounts", "execution_type": "CHECKLIST_ONLY", "evidence_required": True},
            {"text": "Payroll structure created", "responsibility": "accounts", "execution_type": "CHECKLIST_ONLY"},
        ],
    },
]

# Per-item execution configuration keys stored in the template JSON.
ITEM_CONFIG_DEFAULTS: dict[str, Any] = {
    "execution_type": None,
    "mandatory": True,
    "blocks_completion": True,
    "evidence_required": False,
    "reversible": True,
    "priority": None,
    "ticket_category": None,
    "ticket_subcategory": None,
    "completion_rule": "resolved",
    "owner_role": None,
    "confirm_by": "owner",
    "due_offset_days": None,
}


def _default_row_for(text: str) -> dict[str, Any] | None:
    for section in PP_HRD_FO_14_STRUCTURE:
        for row in section["items"]:
            if row["text"] == text:
                return row
    return None


def item_config(item_row: dict[str, Any]) -> dict[str, Any]:
    """Execution config for one template item with defaults applied."""
    config = {key: item_row.get(key, default) for key, default in ITEM_CONFIG_DEFAULTS.items()}
    kind = str(config["execution_type"] or "").upper()
    if kind not in tasks.EXECUTION_TYPE_LABELS:
        kind = tasks.TICKET_REQUIRED if item_row.get("requires_request") else tasks.CHECKLIST_ONLY
    config["execution_type"] = kind
    if kind == tasks.OPTIONAL:
        config["mandatory"] = False
        config["blocks_completion"] = False
    return config


def _merge_execution_defaults(structure: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add execution keys to template items that predate them (admin edits win)."""
    for section in structure:
        for row in section.get("items") or []:
            if "execution_type" in row:
                continue
            default = _default_row_for(str(row.get("text") or ""))
            if default is not None:
                for key, value in default.items():
                    if key in ITEM_CONFIG_DEFAULTS:
                        row.setdefault(key, value)
            else:
                row["execution_type"] = (
                    tasks.TICKET_REQUIRED if row.get("requires_request") else tasks.CHECKLIST_ONLY
                )
    return structure


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
    if (row.version or 1) < 3:
        row.version = TEMPLATE_VERSION
        row.name = FORM_TITLE
        row.structure_json = payload
        db.flush()
    elif (row.version or 1) < TEMPLATE_VERSION:
        row.version = TEMPLATE_VERSION
        row.structure_json = json.dumps(_merge_execution_defaults(parse_structure(row.structure_json)))
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


def can_approve_item(db: Session, user: User, item: OnboardingChecklistItem) -> bool:
    """Who may confirm an APPROVAL_REQUIRED task (``confirm_by`` on the template)."""
    if can_manage_onboarding(db, user):
        return True
    confirm_by = item.confirm_by or "owner"
    checklist = item.checklist
    if confirm_by == "manager":
        return checklist is not None and checklist.reporting_manager_id == user.id
    if confirm_by == "it":
        return "it" in responsibilities_for_user(db, user)
    if confirm_by == "hr":
        return False
    return item.owner_user_id == user.id or item.responsibility in responsibilities_for_user(db, user)


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
    owner_role: str | None = None,
) -> UUID | None:
    """Named owner for a task from configuration only, else None (team queue).

    Manager tasks go to the reporting manager. Otherwise the configured queue
    owner (primary, then backup) for the responsibility's ticket category, or the
    single active holder of the template's ``owner_role``. No person is guessed.
    """
    from app.models.models import Role
    from app.services import ticket_workflow_service as workflow

    if responsibility == "manager":
        return reporting_manager_id

    if owner_role:
        holders = db.scalars(
            select(User.id)
            .join(Role, Role.id == User.role_id)
            .where(
                User.is_active.is_(True),
                User.is_deleted.is_(False),
                Role.name == owner_role,
            )
            .limit(2)
        ).all()
        if len(holders) == 1:
            return holders[0]

    category = RESPONSIBILITY_TICKET_CATEGORY.get(responsibility)
    if not category:
        return None
    return workflow.resolve_routing(db, category=category).assignee_id


def raise_task_tickets(
    db: Session,
    checklist: OnboardingChecklist,
    *,
    created_by: User,
) -> list[dict[str, Any]]:
    """Raise one ticket per unresolved TICKET_REQUIRED task (idempotent)."""
    raised: list[dict[str, Any]] = []
    for item in checklist.items:
        if tasks.is_resolved(item.status) or tasks.execution_type(item) != tasks.TICKET_REQUIRED:
            continue
        if tasks.request_category(item) is None:
            continue
        ticket, _created = tasks.ensure_ticket_for_item(db, item=item, actor=created_by)
        raised.append(
            {
                "responsibility": item.responsibility,
                "responsibility_label": RESPONSIBILITY_LABELS.get(
                    item.responsibility, item.responsibility
                ),
                "ticket_id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "category": ticket.category,
                "assignee_id": str(ticket.assignee_id) if ticket.assignee_id else None,
                "item_count": 1,
            }
        )
    db.flush()
    return raised


raise_department_tickets = raise_task_tickets


def run_automations(db: Session, checklist: OnboardingChecklist) -> int:
    """Complete AUTOMATED tasks whose system check now passes."""
    done = 0
    for item in checklist.items:
        if tasks.complete_automated(
            db, item, evidence="Verified automatically by ProTrack."
        ) is not None:
            done += 1
    if done:
        refresh_checklist_status(checklist, db)
    return done


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
            config = item_config(item_row)
            owner_id = resolve_owner_for_responsibility(
                db,
                responsibility,
                reporting_manager_id=manager_id,
                owner_role=config["owner_role"],
            )
            validation = item_row.get("validation")
            due = tasks.default_due_date(responsibility, checklist.joining_date)
            if config["due_offset_days"] is not None and checklist.joining_date is not None:
                from datetime import timedelta

                due = checklist.joining_date + timedelta(days=int(config["due_offset_days"]))
            db.add(
                OnboardingChecklistItem(
                    checklist_id=checklist.id,
                    section=section,
                    sort_order=order,
                    item_text=text,
                    responsibility=responsibility,
                    status=tasks.NOT_STARTED,
                    owner_user_id=owner_id,
                    due_date=due,
                    requires_request=config["execution_type"] == tasks.TICKET_REQUIRED,
                    validation_rule=str(validation) if validation else None,
                    execution_type=config["execution_type"],
                    mandatory=bool(config["mandatory"]),
                    blocks_completion=bool(config["blocks_completion"]),
                    evidence_required=bool(config["evidence_required"]),
                    reversible=bool(config["reversible"]),
                    task_priority=config["priority"],
                    ticket_category=config["ticket_category"],
                    ticket_subcategory=config["ticket_subcategory"],
                    completion_rule=config["completion_rule"],
                    owner_role=config["owner_role"],
                    confirm_by=config["confirm_by"],
                )
            )
            order += 1
    db.flush()
    checklist = load_checklist(db, checklist.id) or checklist
    triggered: list[dict[str, Any]] = []
    if raise_tickets:
        triggered = raise_task_tickets(db, checklist, created_by=created_by)
    run_automations(db, checklist)
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
    if all(tasks.is_resolved(i.status) for i in items if tasks.blocks_completion(i)):
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
    reason: str | None = None,
    override: bool = False,
) -> OnboardingChecklistItem:
    result = tasks.transition(
        db,
        item=item,
        status=status,
        actor=actor,
        can_waive=can_manage_onboarding(db, actor),
        reason=reason,
        note=notes,
        override=override,
        completion_date=completion_date,
        can_approve=can_approve_item(db, actor, item),
    )
    status = result.new_status
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


def _checklist_load_options() -> list[Any]:
    items = selectinload(OnboardingChecklist.items)
    return [
        items.selectinload(OnboardingChecklistItem.completed_by),
        items.selectinload(OnboardingChecklistItem.owner),
        items.selectinload(OnboardingChecklistItem.help_ticket),
        items.selectinload(OnboardingChecklistItem.status_changed_by),
        selectinload(OnboardingChecklist.template),
        selectinload(OnboardingChecklist.employee),
        selectinload(OnboardingChecklist.reporting_manager),
        selectinload(OnboardingChecklist.created_by),
    ]


def load_checklist(db: Session, checklist_id: UUID) -> OnboardingChecklist | None:
    return db.scalar(
        select(OnboardingChecklist)
        .options(*_checklist_load_options())
        .where(OnboardingChecklist.id == checklist_id)
    )


def load_checklists(db: Session, *, status: str | None = None) -> list[OnboardingChecklist]:
    """All checklists with items eager-loaded in a fixed number of queries."""
    stmt = (
        select(OnboardingChecklist)
        .options(*_checklist_load_options())
        .order_by(OnboardingChecklist.created_at.desc())
    )
    if status and status != "all":
        stmt = stmt.where(OnboardingChecklist.status == status)
    return list(db.scalars(stmt).all())


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
    return tasks.completion_stats(checklist)
