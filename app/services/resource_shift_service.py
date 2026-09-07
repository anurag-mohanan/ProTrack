"""Resource Planning shifts — masters, effective-dated assignments, resolution.

``get_employee_shift`` is the engine everything else leans on: given a person
and a date it decides which shift (if any) that person is on, honouring
effective dating and rotation patterns.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.models import Team, TeamMember, User
from app.models.resource_shifts import (
    ASSIGNMENT_TYPE_PERMANENT,
    ASSIGNMENT_TYPE_ROTATIONAL,
    ResourceShift,
    ResourceShiftAssignment,
)


class ShiftConflictError(ValueError):
    """Raised when an assignment would overlap an existing permanent one."""


class ShiftValidationError(ValueError):
    """Raised for structurally invalid shift / assignment payloads."""


DEFAULT_SHIFTS: tuple[dict, ...] = (
    {
        "code": "DAY",
        "name": "Day Shift",
        "start_time": "09:00",
        "end_time": "18:00",
        "break_minutes": 60,
        "is_overnight": False,
    },
    {
        "code": "EVE",
        "name": "Evening Shift",
        "start_time": "14:00",
        "end_time": "23:00",
        "break_minutes": 60,
        "is_overnight": False,
    },
    {
        "code": "NGT",
        "name": "Night Shift",
        "start_time": "22:00",
        "end_time": "07:00",
        "break_minutes": 60,
        "is_overnight": True,
    },
)


# --------------------------------------------------------------------------
# Shift duration
# --------------------------------------------------------------------------


def _minutes_of(hhmm: str) -> int:
    try:
        hours, minutes = str(hhmm).split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError) as exc:
        raise ShiftValidationError(f"Invalid time value: {hhmm!r}") from exc


def shift_duration_hours(shift: ResourceShift) -> Decimal:
    """Paid hours in one occurrence of ``shift`` (span minus unpaid break)."""
    start = _minutes_of(shift.start_time)
    end = _minutes_of(shift.end_time)
    span = end - start
    if span <= 0 or shift.is_overnight:
        span += 24 * 60
    span -= int(shift.break_minutes or 0)
    if span <= 0:
        return Decimal("0")
    return (Decimal(span) / Decimal(60)).quantize(Decimal("0.01"))


# --------------------------------------------------------------------------
# Shift masters
# --------------------------------------------------------------------------


def list_shifts(db: Session, *, active_only: bool = False) -> list[ResourceShift]:
    stmt = select(ResourceShift)
    if active_only:
        stmt = stmt.where(ResourceShift.is_active.is_(True))
    return list(db.scalars(stmt.order_by(ResourceShift.start_time, ResourceShift.code)).all())


def get_shift(db: Session, shift_id: uuid.UUID) -> ResourceShift | None:
    return db.get(ResourceShift, shift_id)


def create_shift(db: Session, payload: dict) -> ResourceShift:
    code = str(payload.get("code", "")).strip().upper()
    if not code:
        raise ShiftValidationError("Shift code is required.")
    existing = db.scalar(select(ResourceShift).where(ResourceShift.code == code))
    if existing is not None:
        raise ShiftConflictError(f"Shift code '{code}' already exists.")
    shift = ResourceShift(
        id=uuid.uuid4(),
        code=code,
        name=str(payload.get("name", "")).strip() or code,
        start_time=payload.get("start_time") or "09:00",
        end_time=payload.get("end_time") or "18:00",
        break_minutes=int(payload.get("break_minutes") or 0),
        is_overnight=bool(payload.get("is_overnight", False)),
        is_active=bool(payload.get("is_active", True)),
        notes=payload.get("notes"),
    )
    # Surfaces a bad time string before it reaches the database.
    shift_duration_hours(shift)
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def update_shift(db: Session, shift: ResourceShift, payload: dict) -> ResourceShift:
    for field in (
        "name",
        "start_time",
        "end_time",
        "break_minutes",
        "is_overnight",
        "is_active",
        "notes",
    ):
        if field in payload and payload[field] is not None:
            setattr(shift, field, payload[field])
    if payload.get("code"):
        code = str(payload["code"]).strip().upper()
        clash = db.scalar(
            select(ResourceShift).where(
                ResourceShift.code == code, ResourceShift.id != shift.id
            )
        )
        if clash is not None:
            raise ShiftConflictError(f"Shift code '{code}' already exists.")
        shift.code = code
    shift_duration_hours(shift)
    db.commit()
    db.refresh(shift)
    return shift


# --------------------------------------------------------------------------
# Rotation matching
# --------------------------------------------------------------------------


def _rotation_config(assignment: ResourceShiftAssignment) -> dict:
    raw = assignment.rotation_json
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _weekdays_of(config: dict) -> set[int]:
    values = config.get("weekdays")
    if not isinstance(values, list):
        return set()
    return {int(value) for value in values if isinstance(value, int) and 0 <= value <= 6}


def assignment_weekdays(assignment: ResourceShiftAssignment) -> list[int]:
    """Weekday numbers (0 = Monday) a rotational assignment is scheduled on."""
    return sorted(_weekdays_of(_rotation_config(assignment)))


def _rotation_matches(assignment: ResourceShiftAssignment, on_date: date) -> bool:
    """Whether a rotational assignment is 'on' for ``on_date``."""
    pattern = (assignment.rotation_pattern or "daily").lower()
    config = _rotation_config(assignment)
    weekdays = _weekdays_of(config)

    if weekdays and on_date.weekday() not in weekdays:
        return False

    if pattern in ("daily", "weekly", "custom"):
        # Weekly/custom without an explicit weekday list behaves like daily.
        return True

    if pattern == "biweekly":
        anchor = assignment.effective_from
        # Compare from the anchor's own week start so the cycle is stable
        # regardless of which weekday the assignment happened to begin on.
        anchor_week = anchor - timedelta(days=anchor.weekday())
        current_week = on_date - timedelta(days=on_date.weekday())
        weeks = (current_week - anchor_week).days // 7
        cycle_index = int(config.get("cycle_index") or 0)
        return weeks % 2 == cycle_index % 2

    if pattern == "monthly":
        days_of_month = config.get("days_of_month")
        if isinstance(days_of_month, list) and days_of_month:
            return on_date.day in {int(value) for value in days_of_month if isinstance(value, int)}
        anchor = assignment.effective_from
        months = (on_date.year - anchor.year) * 12 + (on_date.month - anchor.month)
        cycle_months = max(int(config.get("cycle_months") or 1), 1)
        cycle_index = int(config.get("cycle_index") or 0)
        return months % cycle_months == cycle_index % cycle_months

    return True


def _covers(assignment: ResourceShiftAssignment, on_date: date) -> bool:
    if not assignment.is_active:
        return False
    if assignment.effective_from > on_date:
        return False
    if assignment.effective_to is not None and assignment.effective_to < on_date:
        return False
    return True


def _applies_on(assignment: ResourceShiftAssignment, on_date: date) -> bool:
    if not _covers(assignment, on_date):
        return False
    if assignment.assignment_type == ASSIGNMENT_TYPE_ROTATIONAL:
        return _rotation_matches(assignment, on_date)
    return True


def _precedence(assignment: ResourceShiftAssignment) -> tuple:
    """Rotational beats permanent (it is the more specific override), then
    the assignment that started most recently wins."""
    rotational = 1 if assignment.assignment_type == ASSIGNMENT_TYPE_ROTATIONAL else 0
    created = assignment.created_at.timestamp() if assignment.created_at else 0.0
    return (rotational, assignment.effective_from, created)


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------


def _assignments_for_users(
    db: Session,
    user_ids: Iterable[uuid.UUID],
    *,
    start: date,
    end: date,
) -> list[ResourceShiftAssignment]:
    ids = list(user_ids)
    if not ids:
        return []
    return list(
        db.scalars(
            select(ResourceShiftAssignment).where(
                ResourceShiftAssignment.user_id.in_(ids),
                ResourceShiftAssignment.is_active.is_(True),
                ResourceShiftAssignment.effective_from <= end,
                or_(
                    ResourceShiftAssignment.effective_to.is_(None),
                    ResourceShiftAssignment.effective_to >= start,
                ),
            )
        ).all()
    )


def get_employee_shift(
    db: Session,
    employee_id: uuid.UUID,
    on_date: date,
) -> ResourceShift | None:
    """Resolve the shift an employee is on for ``on_date``, or ``None``."""
    candidates = [
        assignment
        for assignment in _assignments_for_users(db, [employee_id], start=on_date, end=on_date)
        if _applies_on(assignment, on_date)
    ]
    if not candidates:
        return None
    winner = max(candidates, key=_precedence)
    return db.get(ResourceShift, winner.shift_id)


def resolve_shifts_for_range(
    db: Session,
    user_ids: Iterable[uuid.UUID],
    start: date,
    end: date,
) -> dict[uuid.UUID, dict[date, ResourceShift]]:
    """Batched ``get_employee_shift`` — one query set for the whole window."""
    ids = list(user_ids)
    if not ids or start > end:
        return {}
    assignments = _assignments_for_users(db, ids, start=start, end=end)
    if not assignments:
        return {}
    shifts = {
        shift.id: shift
        for shift in db.scalars(
            select(ResourceShift).where(
                ResourceShift.id.in_({item.shift_id for item in assignments})
            )
        ).all()
    }

    by_user: dict[uuid.UUID, list[ResourceShiftAssignment]] = {}
    for assignment in assignments:
        by_user.setdefault(assignment.user_id, []).append(assignment)

    result: dict[uuid.UUID, dict[date, ResourceShift]] = {}
    for user_id, user_assignments in by_user.items():
        per_day: dict[date, ResourceShift] = {}
        day = start
        while day <= end:
            matching = [item for item in user_assignments if _applies_on(item, day)]
            if matching:
                shift = shifts.get(max(matching, key=_precedence).shift_id)
                if shift is not None:
                    per_day[day] = shift
            day += timedelta(days=1)
        if per_day:
            result[user_id] = per_day
    return result


def shift_hours_for_range(
    db: Session,
    user_ids: Iterable[uuid.UUID],
    start: date,
    end: date,
) -> dict[uuid.UUID, dict[date, Decimal]]:
    """Per-user, per-day paid shift hours — the capacity-integration entry point."""
    resolved = resolve_shifts_for_range(db, user_ids, start, end)
    return {
        user_id: {day: shift_duration_hours(shift) for day, shift in per_day.items()}
        for user_id, per_day in resolved.items()
    }


# --------------------------------------------------------------------------
# Assignments
# --------------------------------------------------------------------------


def list_assignments(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_inactive: bool = False,
) -> list[ResourceShiftAssignment]:
    stmt = select(ResourceShiftAssignment)
    if user_id is not None:
        stmt = stmt.where(ResourceShiftAssignment.user_id == user_id)
    if not include_inactive:
        stmt = stmt.where(ResourceShiftAssignment.is_active.is_(True))
    if date_to is not None:
        stmt = stmt.where(ResourceShiftAssignment.effective_from <= date_to)
    if date_from is not None:
        stmt = stmt.where(
            or_(
                ResourceShiftAssignment.effective_to.is_(None),
                ResourceShiftAssignment.effective_to >= date_from,
            )
        )
    return list(
        db.scalars(stmt.order_by(ResourceShiftAssignment.effective_from.desc())).all()
    )


def _ranges_overlap(
    a_from: date, a_to: date | None, b_from: date, b_to: date | None
) -> bool:
    if a_to is not None and b_from > a_to:
        return False
    if b_to is not None and a_from > b_to:
        return False
    return True


def _find_permanent_overlaps(
    db: Session,
    user_id: uuid.UUID,
    effective_from: date,
    effective_to: date | None,
    *,
    exclude_id: uuid.UUID | None = None,
) -> list[ResourceShiftAssignment]:
    existing = db.scalars(
        select(ResourceShiftAssignment).where(
            ResourceShiftAssignment.user_id == user_id,
            ResourceShiftAssignment.is_active.is_(True),
            ResourceShiftAssignment.assignment_type == ASSIGNMENT_TYPE_PERMANENT,
        )
    ).all()
    return [
        item
        for item in existing
        if item.id != exclude_id
        and _ranges_overlap(
            item.effective_from, item.effective_to, effective_from, effective_to
        )
    ]


def assign_shift(db: Session, payload: dict, *, commit: bool = True) -> ResourceShiftAssignment:
    """Create an effective-dated assignment.

    Overlapping permanent ranges are rejected unless ``end_date_existing`` is
    set, in which case the earlier row is end-dated rather than rewritten.
    """
    user_id = payload["user_id"]
    shift_id = payload["shift_id"]
    effective_from: date = payload["effective_from"]
    effective_to: date | None = payload.get("effective_to")
    assignment_type = str(payload.get("assignment_type") or ASSIGNMENT_TYPE_PERMANENT)
    rotation_pattern = payload.get("rotation_pattern")

    if effective_to is not None and effective_to < effective_from:
        raise ShiftValidationError("effective_to must not precede effective_from.")

    shift = db.get(ResourceShift, shift_id)
    if shift is None:
        raise ShiftValidationError("Shift not found.")
    if not shift.is_active:
        raise ShiftValidationError(f"Shift '{shift.code}' is inactive.")
    if db.get(User, user_id) is None:
        raise ShiftValidationError("User not found.")

    if assignment_type == ASSIGNMENT_TYPE_ROTATIONAL and not rotation_pattern:
        raise ShiftValidationError("Rotational assignments require a rotation pattern.")
    if assignment_type == ASSIGNMENT_TYPE_PERMANENT:
        rotation_pattern = None

    rotation_json = None
    weekdays = payload.get("rotation_weekdays") or []
    if assignment_type == ASSIGNMENT_TYPE_ROTATIONAL:
        config: dict = {}
        cleaned = sorted({int(day) for day in weekdays if 0 <= int(day) <= 6})
        if cleaned:
            config["weekdays"] = cleaned
        if payload.get("cycle_index") is not None:
            config["cycle_index"] = int(payload["cycle_index"])
        rotation_json = json.dumps(config) if config else None

    if assignment_type == ASSIGNMENT_TYPE_PERMANENT:
        overlaps = _find_permanent_overlaps(db, user_id, effective_from, effective_to)
        if overlaps:
            if not payload.get("end_date_existing"):
                clash = overlaps[0]
                raise ShiftConflictError(
                    "User already has a permanent shift assignment covering "
                    f"{effective_from.isoformat()}"
                    f" (from {clash.effective_from.isoformat()})."
                )
            for clash in overlaps:
                if clash.effective_from >= effective_from:
                    raise ShiftConflictError(
                        "Cannot end-date an assignment that starts on or after "
                        f"{effective_from.isoformat()}."
                    )
                clash.effective_to = effective_from - timedelta(days=1)

    assignment = ResourceShiftAssignment(
        id=uuid.uuid4(),
        user_id=user_id,
        shift_id=shift_id,
        assignment_type=assignment_type,
        rotation_pattern=rotation_pattern,
        rotation_json=rotation_json,
        effective_from=effective_from,
        effective_to=effective_to,
        is_active=True,
        notes=payload.get("notes"),
    )
    db.add(assignment)
    if commit:
        db.commit()
        db.refresh(assignment)
    else:
        db.flush()
    return assignment


def end_assignment(
    db: Session,
    assignment: ResourceShiftAssignment,
    effective_to: date,
) -> ResourceShiftAssignment:
    """End-date an assignment; never deletes, so history survives."""
    if effective_to < assignment.effective_from:
        raise ShiftValidationError("effective_to must not precede effective_from.")
    assignment.effective_to = effective_to
    db.commit()
    db.refresh(assignment)
    return assignment


def bulk_assign(db: Session, payload: dict) -> tuple[list[ResourceShiftAssignment], list[dict]]:
    """Assign one shift to many users; returns (created, conflicts)."""
    created: list[ResourceShiftAssignment] = []
    conflicts: list[dict] = []
    for user_id in payload.get("user_ids", []):
        item = dict(payload)
        item.pop("user_ids", None)
        item["user_id"] = user_id
        try:
            created.append(assign_shift(db, item, commit=False))
        except (ShiftConflictError, ShiftValidationError) as exc:
            user = db.get(User, user_id)
            conflicts.append(
                {
                    "user_id": user_id,
                    "user_name": display_name(user) if user else None,
                    "reason": str(exc),
                }
            )
    if created:
        db.commit()
        for assignment in created:
            db.refresh(assignment)
    return created, conflicts


# --------------------------------------------------------------------------
# Calendar
# --------------------------------------------------------------------------


def display_name(user: User) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or "")




def _team_scoped_user_ids(db: Session, team_id: uuid.UUID) -> set[uuid.UUID]:
    member_ids = set(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)).all()
    )
    assigned_ids = set(
        db.scalars(
            select(User.id).where(User.team_id == team_id, User.is_deleted.is_(False))
        ).all()
    )
    return member_ids | assigned_ids


def shift_calendar(
    db: Session,
    *,
    start: date,
    end: date,
    team_id: uuid.UUID | None = None,
) -> dict:
    """Who is on which shift, per day, across ``start``..``end``."""
    if end < start:
        raise ShiftValidationError("'to' must not precede 'from'.")

    stmt = select(User).where(User.is_deleted.is_(False), User.is_active.is_(True))
    if team_id is not None:
        scoped = _team_scoped_user_ids(db, team_id)
        if not scoped:
            return {"start_date": start, "end_date": end, "shifts": [], "rows": []}
        stmt = stmt.where(User.id.in_(scoped))
    users = list(db.scalars(stmt).all())

    team_names = {team.id: team.name for team in db.scalars(select(Team)).all()}
    resolved = resolve_shifts_for_range(db, [user.id for user in users], start, end)

    rows = []
    for user in sorted(users, key=display_name):
        per_day = resolved.get(user.id)
        if not per_day:
            continue
        days = []
        day = start
        while day <= end:
            shift = per_day.get(day)
            days.append(
                {
                    "day": day,
                    "shift_id": shift.id if shift else None,
                    "shift_code": shift.code if shift else None,
                    "shift_name": shift.name if shift else None,
                    "is_overnight": bool(shift.is_overnight) if shift else False,
                    "shift_hours": shift_duration_hours(shift) if shift else None,
                }
            )
            day += timedelta(days=1)
        rows.append(
            {
                "user_id": user.id,
                "user_name": display_name(user),
                "team_name": team_names.get(user.team_id),
                "days": days,
            }
        )

    return {
        "start_date": start,
        "end_date": end,
        "shifts": list_shifts(db, active_only=True),
        "rows": rows,
    }


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------


def seed_default_shifts(db: Session) -> int:
    """Create Day/Evening/Night if the tenant has no shifts yet."""
    if db.scalar(select(ResourceShift).limit(1)) is not None:
        return 0
    for spec in DEFAULT_SHIFTS:
        db.add(ResourceShift(id=uuid.uuid4(), is_active=True, **spec))
    db.commit()
    return len(DEFAULT_SHIFTS)
