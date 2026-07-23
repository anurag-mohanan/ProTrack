"""Exit interview form structure and helpers (PP-HRD-FO-30)."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_HUMAN_RESOURCES
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name
from app.models.models import (
    ExitInterview,
    OrgDepartment,
    Role,
    Team,
    User,
)

FORM_CODE = "PP-HRD-FO-30"
FORM_TITLE = "Employee Exit Interview"

STATUS_LABELS = {
    "draft": "Draft",
    "in_progress": "In progress",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

# Generic exit interview — suitable for any employee / department.
EXIT_INTERVIEW_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "reason_for_leaving",
        "section": "Reason for leaving",
        "prompt": "Primary reason for leaving",
        "input": "choice",
        "required": True,
        "options": [
            "Career growth / new opportunity",
            "Compensation / benefits",
            "Work-life balance",
            "Role / responsibilities",
            "Manager / leadership",
            "Team / culture",
            "Relocation / personal",
            "Health",
            "Retirement",
            "Other",
        ],
    },
    {
        "id": "reason_details",
        "section": "Reason for leaving",
        "prompt": "Please share more detail about your reason for leaving",
        "input": "textarea",
        "required": False,
    },
    {
        "id": "overall_experience",
        "section": "Experience at the company",
        "prompt": "Overall experience working here (1 = poor, 5 = excellent)",
        "input": "rating",
        "required": True,
        "min": 1,
        "max": 5,
    },
    {
        "id": "recommend_employer",
        "section": "Experience at the company",
        "prompt": "Would you recommend this organisation as a place to work?",
        "input": "choice",
        "required": True,
        "options": ["Yes", "Maybe", "No"],
    },
    {
        "id": "enjoyed_most",
        "section": "Experience at the company",
        "prompt": "What did you enjoy most about your role or the organisation?",
        "input": "textarea",
        "required": False,
    },
    {
        "id": "improve",
        "section": "Experience at the company",
        "prompt": "What could we improve (processes, culture, tools, leadership)?",
        "input": "textarea",
        "required": False,
    },
    {
        "id": "manager_relationship",
        "section": "Manager & team",
        "prompt": "How would you rate your working relationship with your manager?",
        "input": "rating",
        "required": False,
        "min": 1,
        "max": 5,
    },
    {
        "id": "team_support",
        "section": "Manager & team",
        "prompt": "Did you feel supported by your team?",
        "input": "choice",
        "required": False,
        "options": ["Yes", "Somewhat", "No"],
    },
    {
        "id": "training_tools",
        "section": "Role enablement",
        "prompt": "Were training, tools, and resources adequate for your role?",
        "input": "choice",
        "required": False,
        "options": ["Yes", "Somewhat", "No"],
    },
    {
        "id": "compensation_fair",
        "section": "Role enablement",
        "prompt": "Did you feel compensation and benefits were fair for your role?",
        "input": "choice",
        "required": False,
        "options": ["Yes", "Somewhat", "No", "Prefer not to say"],
    },
    {
        "id": "would_have_stayed",
        "section": "Retention",
        "prompt": "Is there anything that would have made you stay?",
        "input": "textarea",
        "required": False,
    },
    {
        "id": "additional_comments",
        "section": "Closing",
        "prompt": "Any additional comments for HR or leadership?",
        "input": "textarea",
        "required": False,
    },
    {
        "id": "interviewer_notes",
        "section": "HR use only",
        "prompt": "Interviewer notes (internal)",
        "input": "textarea",
        "required": False,
        "hr_only": True,
    },
]


def can_manage_exit_process(db: Session, user: User) -> bool:
    role = get_role_name(db, user)
    if role in {"Admin", "Engineering Manager", "HR", "Human Resources"}:
        return True
    return user_has_module_action(
        user, role, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW
    )


def parse_answers(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def dump_answers(answers: dict[str, Any] | None) -> str:
    return json.dumps(answers or {}, ensure_ascii=False)


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _resolve_lookups(db: Session, row: ExitInterview) -> None:
    if row.org_department_id and not row.department_name:
        dept = db.get(OrgDepartment, row.org_department_id)
        if dept is not None:
            row.department_name = dept.name
    if row.team_id:
        team = db.get(Team, row.team_id)
        if team is not None:
            row.team_name = team.name
    if row.role_id:
        role = db.get(Role, row.role_id)
        if role is not None:
            row.role_name = role.name
    if row.employee_user_id and (not row.employee_name or row.employee_name.strip() == ""):
        emp = db.get(User, row.employee_user_id)
        name = _full_name(emp)
        if name:
            row.employee_name = name
    if row.reporting_manager_id and not row.reporting_manager_name:
        mgr = db.get(User, row.reporting_manager_id)
        row.reporting_manager_name = _full_name(mgr)
    if row.interviewer_user_id and not row.interviewer_name:
        interviewer = db.get(User, row.interviewer_user_id)
        row.interviewer_name = _full_name(interviewer)


def create_exit_interview(
    db: Session,
    *,
    current_user: User,
    employee_name: str,
    employee_user_id: UUID | None = None,
    employee_code: str | None = None,
    designation: str | None = None,
    department_name: str | None = None,
    org_department_id: UUID | None = None,
    team_id: UUID | None = None,
    role_id: UUID | None = None,
    reporting_manager_id: UUID | None = None,
    reporting_manager_name: str | None = None,
    last_working_date: date | None = None,
    resignation_date: date | None = None,
    interview_date: date | None = None,
    interviewer_user_id: UUID | None = None,
    interviewer_name: str | None = None,
    notes: str | None = None,
    answers: dict[str, Any] | None = None,
) -> ExitInterview:
    if employee_user_id:
        emp = db.get(User, employee_user_id)
        if emp is not None:
            if not employee_name.strip():
                employee_name = _full_name(emp) or employee_name
            if not designation and emp.designation:
                designation = emp.designation
            if not reporting_manager_id and emp.manager_id:
                reporting_manager_id = emp.manager_id

    row = ExitInterview(
        form_code=FORM_CODE,
        employee_user_id=employee_user_id,
        employee_name=employee_name.strip(),
        employee_code=employee_code,
        designation=designation,
        department_name=department_name,
        org_department_id=org_department_id,
        team_id=team_id,
        role_id=role_id,
        reporting_manager_id=reporting_manager_id,
        reporting_manager_name=reporting_manager_name,
        last_working_date=last_working_date,
        resignation_date=resignation_date,
        interview_date=interview_date or date.today(),
        interviewer_user_id=interviewer_user_id or current_user.id,
        interviewer_name=interviewer_name or _full_name(current_user),
        status="draft",
        answers_json=dump_answers(answers),
        notes=notes,
        created_by_id=current_user.id,
    )
    _resolve_lookups(db, row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_exit_interview(
    db: Session,
    row: ExitInterview,
    *,
    data: dict[str, Any],
) -> ExitInterview:
    for key, value in data.items():
        if key == "answers":
            existing = parse_answers(row.answers_json)
            if isinstance(value, dict):
                existing.update(value)
                row.answers_json = dump_answers(existing)
            continue
        if key == "status":
            row.status = value
            if value == "completed" and row.completed_at is None:
                row.completed_at = datetime.utcnow()
            if value != "completed":
                row.completed_at = None
            continue
        if hasattr(row, key):
            setattr(row, key, value)
    _resolve_lookups(db, row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_exit_interviews(
    db: Session, *, status: str | None = None
) -> list[ExitInterview]:
    stmt = select(ExitInterview).order_by(ExitInterview.created_at.desc())
    if status and status != "all":
        stmt = stmt.where(ExitInterview.status == status)
    return list(db.scalars(stmt).all())


def get_exit_interview(db: Session, interview_id: UUID) -> ExitInterview | None:
    return db.get(ExitInterview, interview_id)


def delete_exit_interview(db: Session, row: ExitInterview) -> None:
    db.delete(row)
    db.commit()
