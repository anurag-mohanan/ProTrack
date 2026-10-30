"""Project experience as supporting evidence — never as proof of proficiency.

Sources: the project's current designer / surfacer / design-leader fields and the
employee's own timesheet entries (non-deleted, every timesheet status, split by
status — the shared engineering-metrics rule). Projects are filtered by what the
*viewer* may see. Nothing here creates or changes a skill record.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.team_access import project_visibility_clause
from app.models.foundation import UserSkill
from app.models.models import Project, Timesheet, TimesheetEntry, User
from app.models.skills import UserSkillEvidence
from app.services.skills.access import SkillAccess
from app.services.skills.errors import (
    SkillNotFoundError,
    SkillPermissionError,
    SkillValidationError,
)

EXPERIENCE_LIMITATIONS = (
    "Projects do not record which CAD software was used, so software experience cannot be read from project history.",
    "Projects do not record an engineering discipline; the stream and tool type are shown as the closest recorded context.",
    "Roles come from the project's current designer, surfacer and design-leader fields; earlier reassignments are not kept.",
    "Hours are the employee's own timesheet entries on the project, including draft, submitted and rejected timesheets (split shown).",
    "Project experience is supporting evidence only. It never verifies a skill or sets a proficiency level.",
)

_ZERO = Decimal("0.00")


def _role_map(projects: list[Project], user_id: UUID) -> dict[UUID, list[str]]:
    roles: dict[UUID, list[str]] = {}
    for p in projects:
        r = []
        if p.designer_id == user_id:
            r.append("designer")
        if p.surfacer_id == user_id:
            r.append("surfacer")
        if p.design_leader_id == user_id:
            r.append("design_leader")
        roles[p.id] = r
    return roles


def user_project_hours(db: Session, user_id: UUID, project_ids: list[UUID] | None = None) -> dict[UUID, dict]:
    stmt = (
        select(
            TimesheetEntry.project_id,
            Timesheet.status,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
            func.min(TimesheetEntry.entry_date),
            func.max(TimesheetEntry.entry_date),
        )
        .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .where(
            Timesheet.user_id == user_id,
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.project_id.is_not(None),
        )
        .group_by(TimesheetEntry.project_id, Timesheet.status)
    )
    if project_ids is not None:
        stmt = stmt.where(TimesheetEntry.project_id.in_(project_ids))
    out: dict[UUID, dict] = defaultdict(lambda: {"total": _ZERO, "by_status": {}, "first": None, "last": None})
    for project_id, status, hours, first, last in db.execute(stmt).all():
        row = out[project_id]
        value = Decimal(str(hours)).quantize(Decimal("0.01"))
        key = status.value if hasattr(status, "value") else str(status)
        row["by_status"][key] = row["by_status"].get(key, _ZERO) + value
        row["total"] += value
        row["first"] = first if row["first"] is None or (first and first < row["first"]) else row["first"]
        row["last"] = last if row["last"] is None or (last and last > row["last"]) else row["last"]
    return dict(out)


def connected_project_ids(db: Session, user_id: UUID) -> set[UUID]:
    assigned = set(
        db.scalars(
            select(Project.id).where(
                Project.is_deleted.is_(False),
                or_(Project.designer_id == user_id, Project.surfacer_id == user_id, Project.design_leader_id == user_id),
            )
        ).all()
    )
    booked = set(
        db.scalars(
            select(TimesheetEntry.project_id)
            .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
            .where(
                Timesheet.user_id == user_id,
                TimesheetEntry.is_deleted.is_(False),
                TimesheetEntry.project_id.is_not(None),
            )
            .distinct()
        ).all()
    )
    return assigned | booked


def _visible_project_ids(db: Session, viewer: User, ids: set[UUID]) -> set[UUID]:
    if not ids:
        return set()
    stmt = select(Project.id).where(Project.id.in_(ids), Project.is_deleted.is_(False))
    clause = project_visibility_clause(db, viewer)
    if clause is not None:
        stmt = stmt.where(clause)
    return set(db.scalars(stmt).all())


def project_experience(db: Session, viewer: User, subject_id: UUID) -> dict:
    connected = connected_project_ids(db, subject_id)
    visible = _visible_project_ids(db, viewer, connected)
    projects = list(
        db.scalars(
            select(Project)
            .options(selectinload(Project.customer), selectinload(Project.stream))
            .where(Project.id.in_(visible))
        ).all()
    ) if visible else []
    roles = _role_map(projects, subject_id)
    hours = user_project_hours(db, subject_id, [p.id for p in projects]) if projects else {}
    rows = []
    for p in projects:
        h = hours.get(p.id)
        rows.append(
            {
                "project_id": p.id,
                "tool_number": p.tool_number,
                "part_description": p.part_description,
                "customer_name": p.customer.name if p.customer is not None else None,
                "stream_name": p.stream.name if p.stream is not None else None,
                "tool_type": p.tool_type,
                "complexity": p.complexity.value if p.complexity is not None else None,
                "project_stage": p.project_stage.value if p.project_stage is not None else None,
                "execution_status": p.execution_status.value if p.execution_status is not None else None,
                "completed_at": p.completed_at.date() if p.completed_at else None,
                "roles": roles.get(p.id) or [],
                "timesheet_only": not roles.get(p.id),
                "hours_total": h["total"] if h else _ZERO,
                "hours_by_status": h["by_status"] if h else {},
                "first_booked": h["first"] if h else None,
                "last_booked": h["last"] if h else None,
                "cad_software": None,
            }
        )
    rows.sort(key=lambda r: (r["last_booked"] or date.min, r["tool_number"]), reverse=True)
    return {
        "subject_user_id": subject_id,
        "projects": rows,
        "hidden_project_count": len(connected) - len(visible),
        "limitations": list(EXPERIENCE_LIMITATIONS),
    }


def add_evidence(db: Session, access: SkillAccess, record: UserSkill, *, project_id: UUID, note: str | None) -> UserSkillEvidence:
    if not (record.user_id == access.user.id or access.can_review(db, record.user_id)):
        raise SkillPermissionError("Only the employee or an authorised reviewer can add evidence.")
    project = db.get(Project, project_id)
    if project is None or project.is_deleted:
        raise SkillNotFoundError("Project not found.")
    if project_id not in connected_project_ids(db, record.user_id):
        raise SkillValidationError(
            "The employee is not assigned to this project and has no timesheet hours on it, so it cannot be cited as their experience."
        )
    if project_id not in _visible_project_ids(db, access.user, {project_id}):
        raise SkillPermissionError("You cannot see this project.")
    existing = db.scalar(
        select(UserSkillEvidence).where(UserSkillEvidence.user_skill_id == record.id, UserSkillEvidence.project_id == project_id)
    )
    if existing is not None:
        return existing
    row = UserSkillEvidence(user_skill_id=record.id, project_id=project_id, note=(note or "").strip() or None, added_by_id=access.user.id)
    db.add(row)
    db.flush()
    return row


def remove_evidence(db: Session, access: SkillAccess, evidence_id: UUID) -> None:
    row = db.get(UserSkillEvidence, evidence_id)
    if row is None:
        raise SkillNotFoundError("Evidence not found.")
    record = db.get(UserSkill, row.user_skill_id)
    if record is None or not (record.user_id == access.user.id or access.can_review(db, record.user_id)):
        raise SkillPermissionError("You cannot remove this evidence.")
    db.delete(row)
    db.flush()


def evidence_for_records(db: Session, viewer: User, record_ids: list[UUID]) -> dict[UUID, list[dict]]:
    if not record_ids:
        return {}
    rows = list(db.scalars(select(UserSkillEvidence).where(UserSkillEvidence.user_skill_id.in_(record_ids))).all())
    project_ids = {r.project_id for r in rows}
    visible = _visible_project_ids(db, viewer, project_ids)
    projects = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_(project_ids))).all()} if project_ids else {}
    records = {r.id: r.user_id for r in db.scalars(select(UserSkill).where(UserSkill.id.in_(record_ids))).all()}
    hours_cache: dict[UUID, dict] = {}
    out: dict[UUID, list[dict]] = defaultdict(list)
    for row in rows:
        p = projects.get(row.project_id)
        is_visible = row.project_id in visible
        subject = records.get(row.user_skill_id)
        if subject is not None and subject not in hours_cache:
            hours_cache[subject] = user_project_hours(db, subject)
        h = hours_cache.get(subject, {}).get(row.project_id) if is_visible else None
        out[row.user_skill_id].append(
            {
                "id": row.id,
                "project_id": row.project_id if is_visible else None,
                "tool_number": p.tool_number if (p and is_visible) else None,
                "part_description": p.part_description if (p and is_visible) else None,
                "execution_status": p.execution_status.value if (p and is_visible and p.execution_status) else None,
                "hours_total": h["total"] if h else None,
                "visible": is_visible,
                "note": row.note if is_visible else None,
                "added_at": row.created_at,
            }
        )
    return dict(out)
