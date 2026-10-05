"""Employee directory for shift and resource assignment.

Every list of "people you can put on a shift or give a resource" is built here,
from the User master plus effective-dated shift assignments. Nobody is dropped
because they lack a shift or a resource; employees without a shift come back
with ``shift_state = NOT_ASSIGNED``.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.foundation import Department
from app.models.models import OnboardingChecklist, OrgDepartment, Role, User
from app.models.resource_shifts import ResourceShiftAssignment
from app.services import resource_shift_service as shifts

STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
STATUS_ALL = "all"
STATUSES = frozenset({STATUS_ACTIVE, STATUS_INACTIVE, STATUS_ALL})

SHIFT_ASSIGNED = "ASSIGNED"
SHIFT_NOT_ASSIGNED = "NOT_ASSIGNED"
SHIFT_INACTIVE = "INACTIVE"


def is_active_employee(user: User | None) -> bool:
    return bool(user and user.is_active and not user.is_archived and not user.is_deleted)


def display_name(user: User) -> str:
    return shifts.display_name(user)


def employee_roster(
    db: Session,
    *,
    on_date: date | None = None,
    status: str = STATUS_ACTIVE,
    shift: str | None = None,
    department_id: UUID | None = None,
    q: str | None = None,
    visible_ids: set[UUID] | None = None,
) -> dict[str, Any]:
    """All employees from the User master with their shift on ``on_date``.

    ``shift`` filters by shift id, shift code, or ``none`` (no shift on that date).
    """
    when = on_date or date.today()
    status = (status or STATUS_ACTIVE).lower()
    if status not in STATUSES:
        raise ProTrackValidationError("status must be active, inactive or all.")

    stmt = select(User).where(User.is_deleted.is_(False))
    if status == STATUS_ACTIVE:
        stmt = stmt.where(User.is_active.is_(True), User.is_archived.is_(False))
    elif status == STATUS_INACTIVE:
        stmt = stmt.where(or_(User.is_active.is_(False), User.is_archived.is_(True)))
    if department_id is not None:
        stmt = stmt.where(or_(User.org_department_id == department_id, User.department_id == department_id))
    if visible_ids is not None:
        if not visible_ids:
            return _empty(when)
        stmt = stmt.where(User.id.in_(visible_ids))
    users = list(db.scalars(stmt).all())

    org_departments = {d.id: d.name for d in db.scalars(select(OrgDepartment)).all()}
    departments = {d.id: d.name for d in db.scalars(select(Department)).all()}
    roles = {r.id: r.name for r in db.scalars(select(Role)).all()}
    managers = {u.id: display_name(u) for u in db.scalars(
        select(User).where(User.id.in_({u.manager_id for u in users if u.manager_id}))
    ).all()} if any(u.manager_id for u in users) else {}
    codes: dict[UUID, str] = {}
    for checklist in db.scalars(
        select(OnboardingChecklist)
        .where(OnboardingChecklist.employee_user_id.in_([u.id for u in users]),
               OnboardingChecklist.employee_code.is_not(None))
        .order_by(OnboardingChecklist.created_at)
    ).all():
        codes[checklist.employee_user_id] = checklist.employee_code

    ids = [u.id for u in users]
    resolved = shifts.resolve_shifts_for_range(db, ids, when, when)
    current_rows: dict[UUID, ResourceShiftAssignment] = {}
    for row in shifts._assignments_for_users(db, ids, start=when, end=when):
        if not shifts._applies_on(row, when):
            continue
        best = current_rows.get(row.user_id)
        if best is None or shifts._precedence(row) > shifts._precedence(best):
            current_rows[row.user_id] = row
    history_counts: dict[UUID, int] = {}
    for user_id in db.scalars(
        select(ResourceShiftAssignment.user_id).where(ResourceShiftAssignment.user_id.in_(ids))
    ).all():
        history_counts[user_id] = history_counts.get(user_id, 0) + 1

    term = (q or "").strip().lower()
    shift_filter = (shift or "").strip()
    rows: list[dict[str, Any]] = []
    for user in users:
        active = is_active_employee(user)
        current = resolved.get(user.id, {}).get(when)
        assignment = current_rows.get(user.id)
        department = org_departments.get(user.org_department_id) or departments.get(user.department_id)
        if not active:
            state = SHIFT_INACTIVE
        elif current is not None:
            state = SHIFT_ASSIGNED
        else:
            state = SHIFT_NOT_ASSIGNED
        row = {
            "user_id": user.id,
            "name": display_name(user),
            "email": user.email,
            "employee_code": codes.get(user.id),
            "department": department,
            "org_department_id": user.org_department_id,
            "department_id": user.department_id,
            "designation": user.designation or roles.get(user.role_id),
            "role_name": roles.get(user.role_id),
            "manager_name": managers.get(user.manager_id) if user.manager_id else None,
            "is_active": active,
            "shift_state": state,
            "shift_id": current.id if current else None,
            "shift_code": current.code if current else None,
            "shift_name": current.name if current else None,
            "shift_start": current.start_time if current else None,
            "shift_end": current.end_time if current else None,
            "shift_display": shifts.format_shift_label(current) if current else None,
            "assignment_id": assignment.id if assignment else None,
            "assignment_type": assignment.assignment_type if assignment else None,
            "effective_from": assignment.effective_from if assignment else None,
            "effective_to": assignment.effective_to if assignment else None,
            "shift_history_count": history_counts.get(user.id, 0),
        }
        if term and not any(
            term in (value or "").lower()
            for value in (row["name"], row["email"], row["employee_code"], row["department"],
                          row["designation"])
        ):
            continue
        if shift_filter:
            if shift_filter.lower() == "none":
                if current is not None:
                    continue
            elif not current or (
                shift_filter != str(current.id) and shift_filter.upper() != (current.code or "").upper()
            ):
                continue
        rows.append(row)
    rows.sort(key=lambda r: (not r["is_active"], r["name"].lower()))

    counts = {"total": len(rows), "assigned": 0, "not_assigned": 0, "inactive": 0, "by_shift": {}}
    for row in rows:
        if row["shift_state"] == SHIFT_ASSIGNED:
            counts["assigned"] += 1
            counts["by_shift"][row["shift_code"]] = counts["by_shift"].get(row["shift_code"], 0) + 1
        elif row["shift_state"] == SHIFT_NOT_ASSIGNED:
            counts["not_assigned"] += 1
        else:
            counts["inactive"] += 1
    return {"on_date": when, "counts": counts, "rows": rows}


def _empty(when: date) -> dict[str, Any]:
    return {
        "on_date": when,
        "counts": {"total": 0, "assigned": 0, "not_assigned": 0, "inactive": 0, "by_shift": {}},
        "rows": [],
    }
