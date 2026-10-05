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
        "code": "FIRST",
        "name": "First Shift",
        "start_time": "06:00",
        "end_time": "14:00",
        # Preserve prior seed convention (Day/Eve used 60); do not invent a new policy.
        "break_minutes": 60,
        "is_overnight": False,
    },
    {
        "code": "SECOND",
        "name": "Second Shift",
        "start_time": "14:00",
        "end_time": "22:00",
        "break_minutes": 60,
        "is_overnight": False,
    },
    {
        "code": "GENERAL",
        "name": "General Shift",
        "start_time": "09:00",
        "end_time": "18:00",
        "break_minutes": 60,
        "is_overnight": False,
    },
)

# Obsolete seed codes from the initial Day/Evening/Night catalog.
LEGACY_SHIFT_CODES: frozenset[str] = frozenset({"DAY", "EVE", "NGT"})


# --------------------------------------------------------------------------
# Shift duration / display
# --------------------------------------------------------------------------


def _minutes_of(hhmm: str) -> int:
    try:
        hours, minutes = str(hhmm).split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError) as exc:
        raise ShiftValidationError(f"Invalid time value: {hhmm!r}") from exc


def format_shift_clock(hhmm: str) -> str:
    """Format ``HH:MM`` as ``6:00 AM`` / ``2:00 PM`` for consistent UI display."""
    minutes = _minutes_of(hhmm)
    hour24, minute = divmod(minutes, 60)
    period = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12
    if hour12 == 0:
        hour12 = 12
    return f"{hour12}:{minute:02d} {period}"


def format_shift_window(start_time: str, end_time: str) -> str:
    return f"{format_shift_clock(start_time)} – {format_shift_clock(end_time)}"


def format_shift_label(shift: ResourceShift, *, include_code: bool = False) -> str:
    window = format_shift_window(shift.start_time, shift.end_time)
    if include_code:
        return f"{shift.name} ({shift.code}) — {window}"
    return f"{shift.name} — {window}"


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
    """Whether a rotational assignment is 'on' for ``on_date``.

    Sequence-based rotations (multi-shift cycles) always match on covered dates;
    the active shift is chosen in ``_shift_id_for_date``.
    """
    config = _rotation_config(assignment)
    if _sequence_segments(config):
        weekdays = _weekdays_of(config)
        if weekdays and on_date.weekday() not in weekdays:
            return False
        return True

    pattern = (assignment.rotation_pattern or "daily").lower()
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


def _sequence_segments(config: dict) -> list[dict]:
    """Normalize rotation sequence config into ``[{shift_id, days}, ...]``.

    Supported forms:
    - segments: [{shift_id, days}]
    - sequence: [shift_id, ...] with slot_days (default 7) or period per slot
    """
    segments = config.get("segments")
    if isinstance(segments, list) and segments:
        out = []
        for item in segments:
            if not isinstance(item, dict):
                continue
            days = max(int(item.get("days") or 0), 0)
            if days <= 0:
                continue
            sid = item.get("shift_id")
            out.append({"shift_id": str(sid) if sid else None, "days": days})
        return out

    sequence = config.get("sequence")
    if isinstance(sequence, list) and sequence:
        slot = max(int(config.get("slot_days") or config.get("period") or 7), 1)
        out = []
        for sid in sequence:
            out.append({"shift_id": str(sid) if sid else None, "days": slot})
        return out
    return []


def _shift_id_for_date(assignment: ResourceShiftAssignment, on_date: date) -> uuid.UUID | None:
    """Resolve which shift master applies on ``on_date`` for this assignment."""
    config = _rotation_config(assignment)
    segments = _sequence_segments(config)
    if not segments:
        return assignment.shift_id

    cycle_len = sum(seg["days"] for seg in segments)
    if cycle_len <= 0:
        return assignment.shift_id
    offset = (on_date - assignment.effective_from).days
    if offset < 0:
        return None
    pos = offset % cycle_len
    cursor = 0
    for seg in segments:
        cursor += seg["days"]
        if pos < cursor:
            sid = seg["shift_id"]
            if not sid:
                return None  # Off day in custom cycle
            try:
                return uuid.UUID(str(sid))
            except (ValueError, TypeError):
                return assignment.shift_id
    return assignment.shift_id


def next_employee_shift(
    db: Session,
    employee_id: uuid.UUID,
    *,
    after_date: date | None = None,
    horizon_days: int = 366,
) -> dict | None:
    """Return current shift (on after_date) and the next change within horizon."""
    start = after_date or date.today()
    current = get_employee_shift(db, employee_id, start)
    current_id = current.id if current else None
    day = start + timedelta(days=1)
    end = start + timedelta(days=max(1, horizon_days))
    while day <= end:
        nxt = get_employee_shift(db, employee_id, day)
        nxt_id = nxt.id if nxt else None
        if nxt_id != current_id:
            return {
                "on_date": start,
                "current_shift": current,
                "next_change_date": day,
                "next_shift": nxt,
            }
        day += timedelta(days=1)
    return {
        "on_date": start,
        "current_shift": current,
        "next_change_date": None,
        "next_shift": None,
    }


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
    shift_id = _shift_id_for_date(winner, on_date)
    if shift_id is None:
        return None
    return db.get(ResourceShift, shift_id)


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

    # Collect every shift id referenced by assignment.shift_id or sequences.
    shift_ids: set[uuid.UUID] = {item.shift_id for item in assignments}
    for item in assignments:
        for seg in _sequence_segments(_rotation_config(item)):
            sid = seg.get("shift_id")
            if sid:
                try:
                    shift_ids.add(uuid.UUID(str(sid)))
                except (ValueError, TypeError):
                    pass
    shifts = {
        shift.id: shift
        for shift in db.scalars(select(ResourceShift).where(ResourceShift.id.in_(shift_ids))).all()
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
                winner = max(matching, key=_precedence)
                sid = _shift_id_for_date(winner, day)
                shift = shifts.get(sid) if sid else None
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
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ShiftValidationError("User not found.")
    if not user.is_active or user.is_archived:
        raise ShiftValidationError(
            f"{display_name(user)} is inactive — shifts can only be assigned to active employees."
        )

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
        if payload.get("slot_days") is not None:
            config["slot_days"] = max(int(payload["slot_days"]), 1)
        if payload.get("period") is not None:
            config["period"] = max(int(payload["period"]), 1)
        if payload.get("unit"):
            config["unit"] = str(payload["unit"]).lower()
        sequence = payload.get("rotation_sequence") or payload.get("sequence") or []
        if isinstance(sequence, list) and sequence:
            config["sequence"] = [str(item) for item in sequence if item]
            # Primary shift_id becomes first sequence entry when not already meaningful.
            try:
                first = uuid.UUID(str(config["sequence"][0]))
                if db.get(ResourceShift, first) is not None:
                    shift_id = first
            except (ValueError, TypeError):
                pass
        segments = payload.get("rotation_segments") or payload.get("segments") or []
        if isinstance(segments, list) and segments:
            cleaned_segments = []
            for item in segments:
                if not isinstance(item, dict):
                    continue
                days = max(int(item.get("days") or 0), 0)
                if days <= 0:
                    continue
                cleaned_segments.append(
                    {
                        "shift_id": str(item["shift_id"]) if item.get("shift_id") else None,
                        "days": days,
                    }
                )
            if cleaned_segments:
                config["segments"] = cleaned_segments
                if cleaned_segments[0].get("shift_id"):
                    try:
                        shift_id = uuid.UUID(str(cleaned_segments[0]["shift_id"]))
                    except (ValueError, TypeError):
                        pass
        days_of_month = payload.get("days_of_month") or []
        if isinstance(days_of_month, list) and days_of_month:
            config["days_of_month"] = sorted(
                {int(day) for day in days_of_month if isinstance(day, int) and 1 <= int(day) <= 31}
            )
        if payload.get("cycle_months") is not None:
            config["cycle_months"] = max(int(payload["cycle_months"]), 1)
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
                if clash.effective_from > effective_from:
                    raise ShiftConflictError(
                        "Cannot end-date an assignment that starts after "
                        f"{effective_from.isoformat()}."
                    )
                if clash.effective_from == effective_from:
                    # Same-day reassign: supersede the prior row (preserve history).
                    clash.is_active = False
                    clash.effective_to = effective_from
                else:
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


def reassign_employee_shift(
    db: Session,
    *,
    user_id: uuid.UUID,
    new_shift_id: uuid.UUID,
    effective_from: date,
    assignment_type: str = ASSIGNMENT_TYPE_PERMANENT,
    notes: str | None = None,
    commit: bool = True,
) -> ResourceShiftAssignment:
    """Move an employee to a new permanent shift effective_from (history preserved)."""
    payload = {
        "user_id": user_id,
        "shift_id": new_shift_id,
        "assignment_type": assignment_type,
        "effective_from": effective_from,
        "end_date_existing": True,
        "notes": notes,
    }
    return assign_shift(db, payload, commit=commit)


def bulk_reassign_employee_shifts(
    db: Session,
    *,
    user_ids: list[uuid.UUID],
    new_shift_id: uuid.UUID,
    effective_from: date,
    assignment_type: str = ASSIGNMENT_TYPE_PERMANENT,
    notes: str | None = None,
) -> tuple[list[ResourceShiftAssignment], list[dict]]:
    """Bulk move employees to a shift. Returns (created, conflicts)."""
    return bulk_assign(
        db,
        {
            "user_ids": user_ids,
            "shift_id": new_shift_id,
            "assignment_type": assignment_type,
            "effective_from": effective_from,
            "end_date_existing": True,
            "notes": notes,
        },
    )


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

    stmt = select(User).where(
        User.is_deleted.is_(False), User.is_active.is_(True), User.is_archived.is_(False)
    )
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
        per_day = resolved.get(user.id) or {}
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


def shift_overview(db: Session, *, on_date: date | None = None, team_id: uuid.UUID | None = None) -> dict:
    """Management summary: headcount by shift, permanent vs rotational, unassigned."""
    on_date = on_date or date.today()
    stmt = select(User).where(User.is_deleted.is_(False), User.is_active.is_(True))
    if team_id is not None:
        scoped = _team_scoped_user_ids(db, team_id)
        if not scoped:
            return {
                "on_date": on_date,
                "total_employees": 0,
                "unassigned": 0,
                "permanent": 0,
                "rotational": 0,
                "by_shift": [],
            }
        stmt = stmt.where(User.id.in_(scoped))
    users = list(db.scalars(stmt).all())
    resolved = resolve_shifts_for_range(db, [u.id for u in users], on_date, on_date)
    assignments = _assignments_for_users(db, [u.id for u in users], start=on_date, end=on_date)

    permanent_users: set[uuid.UUID] = set()
    rotational_users: set[uuid.UUID] = set()
    for assignment in assignments:
        if not _applies_on(assignment, on_date):
            continue
        if assignment.assignment_type == ASSIGNMENT_TYPE_ROTATIONAL:
            rotational_users.add(assignment.user_id)
        else:
            permanent_users.add(assignment.user_id)

    by_shift: dict[uuid.UUID, dict] = {}
    for shift in list_shifts(db, active_only=True):
        by_shift[shift.id] = {
            "shift_id": shift.id,
            "shift_code": shift.code,
            "shift_name": shift.name,
            "display_label": format_shift_label(shift),
            "employee_count": 0,
        }

    assigned_count = 0
    for user in users:
        shift = resolved.get(user.id, {}).get(on_date)
        if shift is None:
            continue
        assigned_count += 1
        bucket = by_shift.get(shift.id)
        if bucket is not None:
            bucket["employee_count"] += 1

    return {
        "on_date": on_date,
        "total_employees": len(users),
        "assigned": assigned_count,
        "unassigned": max(0, len(users) - assigned_count),
        "permanent": len(permanent_users - rotational_users),
        "rotational": len(rotational_users),
        "by_shift": list(by_shift.values()),
    }


def shift_board(db: Session, *, on_date: date | None = None, team_id: uuid.UUID | None = None) -> dict:
    """Visual board: employees grouped under each shift for ``on_date``."""
    on_date = on_date or date.today()
    stmt = select(User).where(User.is_deleted.is_(False), User.is_active.is_(True))
    if team_id is not None:
        scoped = _team_scoped_user_ids(db, team_id)
        if not scoped:
            return {"on_date": on_date, "columns": []}
        stmt = stmt.where(User.id.in_(scoped))
    users = list(db.scalars(stmt).all())
    team_names = {team.id: team.name for team in db.scalars(select(Team)).all()}
    resolved = resolve_shifts_for_range(db, [u.id for u in users], on_date, on_date)

    # Optional computer names for board rows
    from app.models.it_operations import AssetAssignment, Computer

    open_assigns = list(
        db.scalars(
            select(AssetAssignment).where(AssetAssignment.returned_date.is_(None))
        ).all()
    )
    asset_to_user = {a.asset_id: a.assigned_to_user_id for a in open_assigns}
    computers = list(db.scalars(select(Computer)).all())
    user_computer: dict[uuid.UUID, str] = {}
    for computer in computers:
        uid = asset_to_user.get(computer.asset_id)
        if uid:
            user_computer[uid] = computer.computer_name

    columns = []
    for shift in list_shifts(db, active_only=True):
        people = []
        for user in sorted(users, key=display_name):
            day_shift = resolved.get(user.id, {}).get(on_date)
            if day_shift is None or day_shift.id != shift.id:
                continue
            nxt = next_employee_shift(db, user.id, after_date=on_date, horizon_days=60)
            people.append(
                {
                    "user_id": user.id,
                    "user_name": display_name(user),
                    "team_name": team_names.get(user.team_id),
                    "computer_name": user_computer.get(user.id),
                    "next_change_date": nxt.get("next_change_date") if nxt else None,
                    "next_shift_code": (
                        nxt["next_shift"].code if nxt and nxt.get("next_shift") else None
                    ),
                }
            )
        columns.append(
            {
                "shift_id": shift.id,
                "shift_code": shift.code,
                "shift_name": shift.name,
                "display_label": format_shift_label(shift),
                "start_time": shift.start_time,
                "end_time": shift.end_time,
                "employee_count": len(people),
                "employees": people,
            }
        )
    unassigned = [
        {
            "user_id": user.id,
            "user_name": display_name(user),
            "team_name": team_names.get(user.team_id),
            "computer_name": user_computer.get(user.id),
        }
        for user in sorted(users, key=display_name)
        if resolved.get(user.id, {}).get(on_date) is None
    ]
    return {"on_date": on_date, "columns": columns, "unassigned": unassigned}


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------


def seed_default_shifts(db: Session) -> int:
    """Create company standard shifts when the tenant has none; otherwise migrate."""
    if db.scalar(select(ResourceShift).limit(1)) is not None:
        return ensure_company_standard_shifts(db)
    for spec in DEFAULT_SHIFTS:
        db.add(ResourceShift(id=uuid.uuid4(), is_active=True, **spec))
    db.commit()
    return len(DEFAULT_SHIFTS)


def ensure_company_standard_shifts(db: Session) -> int:
    """Upsert First/Second/General and safely deactivate obsolete seed shifts.

    Historical assignments keep pointing at the same shift rows; obsolete
    masters are only marked inactive so they drop out of future dropdowns.
    """
    by_code = {
        shift.code.upper(): shift
        for shift in db.scalars(select(ResourceShift)).all()
    }
    changed = 0

    # Prefer remapping the old Day seed onto General (same 09:00–18:00 window)
    # so existing assignment history keeps its shift_id and meaning.
    day = by_code.get("DAY")
    general = by_code.get("GENERAL")
    if day is not None and general is None:
        day.code = "GENERAL"
        day.name = "General Shift"
        day.start_time = "09:00"
        day.end_time = "18:00"
        day.is_overnight = False
        day.is_active = True
        by_code["GENERAL"] = day
        by_code.pop("DAY", None)
        changed += 1

    for spec in DEFAULT_SHIFTS:
        code = spec["code"]
        existing = by_code.get(code)
        if existing is None:
            shift = ResourceShift(id=uuid.uuid4(), is_active=True, **spec)
            db.add(shift)
            by_code[code] = shift
            changed += 1
            continue
        dirty = False
        if existing.name != spec["name"]:
            existing.name = spec["name"]
            dirty = True
        if existing.start_time != spec["start_time"]:
            existing.start_time = spec["start_time"]
            dirty = True
        if existing.end_time != spec["end_time"]:
            existing.end_time = spec["end_time"]
            dirty = True
        if existing.is_overnight != spec["is_overnight"]:
            existing.is_overnight = spec["is_overnight"]
            dirty = True
        if not existing.is_active:
            existing.is_active = True
            dirty = True
        if dirty:
            changed += 1

    for legacy_code in LEGACY_SHIFT_CODES:
        legacy = by_code.get(legacy_code)
        if legacy is not None and legacy.is_active:
            legacy.is_active = False
            changed += 1

    if changed:
        db.commit()
    return changed
