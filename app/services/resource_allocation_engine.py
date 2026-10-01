"""Central shift-aware resource allocation engine.

The single authority for "who can use which resource, when". Asset assignment,
license assignment, Virtual Seats, availability search, reservations, reports and
the IT dashboard all evaluate through this module:

* Time windows — a shift or a custom ``HH:MM``–``HH:MM`` range, normalised to
  minute segments so overnight windows (22:00–06:00) split across midnight.
  Two windows overlap when ``startA < endB and startB < endA`` for any pair of
  segments; touching boundaries (…–06:00 vs 06:00–…) do not overlap.
* Date ranges — assignment start date through planned end / release date.
* Asset sharing policy — configured per asset type (defaults by component role).
* License metrics — named/per-user, per-device, concurrent/floating, site.
* Reservations — hold a resource for a person/onboarding over a window.
* Locking — ``lock_row`` takes a row lock (Postgres) / write lock (SQLite)
  before validation so two simultaneous requests cannot both pass.

Asset lifecycle ``status`` only answers "can this asset be used at all"
(maintenance, retired …). Availability is always computed from assignments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError

from app.core.exceptions import ProTrackValidationError
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    LicenseUsageSession,
    ResourceReservation,
    SoftwareAssignment,
    SoftwareLicensePool,
)
from app.models.models import User
from app.models.resource_shifts import ResourceShift
from app.services import it_inventory_rules as rules

DAY_MINUTES = 24 * 60

# --- Availability result vocabulary ----------------------------------------------------

AVAILABLE = "AVAILABLE"
ASSIGNED = "ASSIGNED"
CONFLICT = "CONFLICT"
RESERVED = "RESERVED"
UNAVAILABLE = "UNAVAILABLE"
NOT_ALLOWED = "NOT_ALLOWED"

REASON_OK = "OK"
REASON_ALREADY_HOLDS = "ALREADY_HOLDS"
REASON_LIFECYCLE = "LIFECYCLE"
REASON_SAME_SLOT = "SAME_SLOT"
REASON_TIME_OVERLAP = "TIME_OVERLAP"
REASON_LEGACY = "LEGACY_ALL_HOURS"
REASON_NOT_SHAREABLE = "NOT_SHAREABLE"
REASON_RESERVED = "RESERVED"
REASON_CAPACITY = "CAPACITY"
REASON_METRIC = "METRIC_RULE"
REASON_POOL_INACTIVE = "POOL_INACTIVE"

# Only these may be overridden (with permission + reason); lifecycle / metric never.
OVERRIDABLE_REASONS = frozenset({REASON_TIME_OVERLAP, REASON_LEGACY, REASON_RESERVED})

ASSIGNABLE_ASSET_STATUSES = frozenset({"available", "assigned"})
LIFECYCLE_REASONS = {
    "maintenance": "In maintenance",
    "reserved": "Reserved",
    "awaiting_return": "Pending return",
    "damaged": "Damaged",
    "lost": "Lost",
    "retired": "Retired",
    "disposed": "Disposed",
    "returned_to_customer": "Returned to customer",
}


# --- Time windows -------------------------------------------------------------------


def parse_hhmm(value: str | None) -> int:
    raw = (value or "").strip()
    if not raw:
        raise ProTrackValidationError("Time is required (HH:MM).")
    parts = raw.split(":")
    try:
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
    except ValueError as exc:
        raise ProTrackValidationError(f"Invalid time '{value}'. Use HH:MM.") from exc
    if not (0 <= hours <= 24 and 0 <= minutes < 60) or (hours == 24 and minutes):
        raise ProTrackValidationError(f"Invalid time '{value}'. Use HH:MM.")
    return hours * 60 + minutes


def fmt_minutes(value: int) -> str:
    value = value % (DAY_MINUTES + 1)
    return f"{value // 60:02d}:{value % 60:02d}"


@dataclass(frozen=True)
class Window:
    """A daily wall-clock window. ``end <= start`` means it ends the next day."""

    start: int
    end: int
    all_day: bool = False
    shift_id: UUID | None = None
    shift_name: str | None = None
    legacy: bool = False

    def segments(self) -> list[tuple[int, int]]:
        if self.all_day:
            return [(0, DAY_MINUTES)]
        if self.end > self.start:
            return [(self.start, self.end)]
        return [(self.start, DAY_MINUTES), (0, self.end)]

    @property
    def label(self) -> str:
        if self.all_day:
            return "All hours"
        times = f"{fmt_minutes(self.start)}–{fmt_minutes(self.end)}"
        return f"{self.shift_name} ({times})" if self.shift_name else times

    @property
    def times(self) -> str:
        return "00:00–24:00" if self.all_day else f"{fmt_minutes(self.start)}–{fmt_minutes(self.end)}"


ALL_HOURS = Window(0, DAY_MINUTES, all_day=True)


def window_from_times(
    start_time: str, end_time: str, *, shift: ResourceShift | None = None
) -> Window:
    start = parse_hhmm(start_time)
    end = parse_hhmm(end_time)
    if start == end or (start == 0 and end == DAY_MINUTES):
        return Window(0, DAY_MINUTES, all_day=True, shift_id=shift.id if shift else None,
                      shift_name=shift.name if shift else None)
    return Window(
        start % DAY_MINUTES,
        end % DAY_MINUTES if end != DAY_MINUTES else DAY_MINUTES,
        shift_id=shift.id if shift else None,
        shift_name=shift.name if shift else None,
    )


def window_for_shift(shift: ResourceShift) -> Window:
    start = parse_hhmm(shift.start_time)
    end = parse_hhmm(shift.end_time)
    if shift.is_overnight and end > start:
        return Window(0, DAY_MINUTES, all_day=True, shift_id=shift.id, shift_name=shift.name)
    return window_from_times(shift.start_time, shift.end_time, shift=shift)


def window_for_row(row: Any, shift_map: dict[UUID, ResourceShift]) -> Window:
    """Window of an assignment/reservation row (custom times win over its shift)."""
    shift = shift_map.get(row.shift_id) if getattr(row, "shift_id", None) else None
    if getattr(row, "start_time", None) and getattr(row, "end_time", None):
        return window_from_times(row.start_time, row.end_time, shift=shift)
    if shift is not None:
        return window_for_shift(shift)
    return Window(0, DAY_MINUTES, all_day=True, legacy=True)


def overlap_segments(a: Window, b: Window) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a0, a1 in a.segments():
        for b0, b1 in b.segments():
            lo, hi = max(a0, b0), min(a1, b1)
            if lo < hi:
                out.append((lo, hi))
    return sorted(out)


def windows_overlap(a: Window, b: Window) -> bool:
    return bool(overlap_segments(a, b))


def describe_overlap(a: Window, b: Window) -> str:
    segs = overlap_segments(a, b)
    # Rejoin an overnight overlap that was split at midnight.
    if len(segs) == 2 and segs[0][0] == 0 and segs[1][1] == DAY_MINUTES:
        return f"{fmt_minutes(segs[1][0])}–{fmt_minutes(segs[0][1])}"
    return ", ".join(f"{fmt_minutes(s)}–{fmt_minutes(e)}" for s, e in segs)


def resolve_window(
    db: Session,
    *,
    shift_id: UUID | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> Window:
    """Window for a request: custom times, else the shift, else exclusive all hours."""
    shift = None
    if shift_id is not None:
        shift = db.get(ResourceShift, shift_id)
        if shift is None or not shift.is_active:
            raise ProTrackValidationError("Shift not found or inactive.")
    if (start_time or end_time) and not (start_time and end_time):
        raise ProTrackValidationError("Provide both start time and end time.")
    if start_time and end_time:
        return window_from_times(start_time, end_time, shift=shift)
    if shift is not None:
        return window_for_shift(shift)
    return ALL_HOURS


# --- Date ranges --------------------------------------------------------------------


def _row_dates(row: Any) -> tuple[date, date | None]:
    start = getattr(row, "assigned_date", None) or getattr(row, "start_date", None) or date.min
    end: date | None = getattr(row, "planned_end_date", None) or getattr(row, "end_date", None)
    released = getattr(row, "returned_date", None) or getattr(row, "released_date", None)
    if released is not None:
        last = released - timedelta(days=1)
        end = min(end, last) if end else last
    return start, end


def dates_overlap(s1: date, e1: date | None, s2: date, e2: date | None) -> bool:
    return (e2 is None or s1 <= e2) and (e1 is None or s2 <= e1)


def fmt_range(start: date, end: date | None) -> str:
    return f"{start.isoformat()} → {end.isoformat() if end else 'open'}"


@dataclass
class AllocationRequest:
    start_date: date
    end_date: date | None
    window: Window
    user_id: UUID | None = None
    asset_id: UUID | None = None  # device for per-device licenses
    exclude_ids: frozenset[UUID] = field(default_factory=frozenset)
    reservation_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ProTrackValidationError("End date cannot be before start date.")


def build_request(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    shift_id: UUID | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    user_id: UUID | None = None,
    asset_id: UUID | None = None,
    exclude_ids: Iterable[UUID] = (),
    reservation_id: UUID | None = None,
) -> AllocationRequest:
    return AllocationRequest(
        start_date=start_date or date.today(),
        end_date=end_date,
        window=resolve_window(db, shift_id=shift_id, start_time=start_time, end_time=end_time),
        user_id=user_id,
        asset_id=asset_id,
        exclude_ids=frozenset(exclude_ids),
        reservation_id=reservation_id,
    )


# --- Shared lookups -----------------------------------------------------------------


def _shift_map(db: Session, rows: Iterable[Any], extra: dict[UUID, ResourceShift] | None = None):
    ids = {r.shift_id for r in rows if getattr(r, "shift_id", None)}
    found = dict(extra or {})
    missing = ids - set(found)
    if missing:
        found.update({s.id: s for s in db.scalars(select(ResourceShift).where(ResourceShift.id.in_(missing))).all()})
    return found


def _names(db: Session, user_ids: Iterable[UUID | None]) -> dict[UUID, str]:
    ids = {u for u in user_ids if u}
    if not ids:
        return {}
    return {
        u.id: (f"{u.first_name} {u.last_name}".strip() or u.email)
        for u in db.scalars(select(User).where(User.id.in_(ids))).all()
    }


def lock_row(db: Session, model: Any, row_id: UUID) -> None:
    """Serialise writers on one resource until the transaction ends.

    A no-op ``UPDATE`` takes a row lock on Postgres and the database write lock on
    SQLite, so a concurrent request blocks here and re-reads committed state.
    SQLite reports lock contention it cannot wait out as "database is locked";
    that loser is rejected as a conflict instead of surfacing a server error.
    """
    try:
        db.execute(update(model).where(model.id == row_id).values(id=model.id))
    except OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        db.rollback()
        raise ProTrackValidationError(_BUSY_MESSAGE, status_code=409) from exc


_BUSY_MESSAGE = "Another change to this resource is being saved right now — refresh and try again."


def lock_resource(db: Session, obj: Any) -> None:
    """Lock ``obj``'s row and reload it so the caller evaluates committed state."""
    lock_row(db, type(obj), obj.id)
    try:
        db.refresh(obj)
    except (ObjectDeletedError, OperationalError) as exc:
        if isinstance(exc, OperationalError) and "locked" not in str(exc).lower():
            raise
        db.rollback()
        raise ProTrackValidationError(_BUSY_MESSAGE, status_code=409) from exc


# --- Asset sharing policy -----------------------------------------------------------

_SHAREABLE_ROLES = frozenset(
    {rules.ROLE_COMPUTER, rules.ROLE_MONITOR, rules.ROLE_MOUSE_3D, rules.ROLE_DOCK,
     rules.ROLE_WEBCAM, rules.ROLE_SPEAKERS}
)
_SHIFT_ROLES = frozenset({rules.ROLE_COMPUTER})


def sharing_policy(asset_type: AssetType | None) -> dict[str, Any]:
    role = rules.role_for_asset_type(asset_type)
    default_shareable = role in _SHAREABLE_ROLES
    default_shift = role in _SHIFT_ROLES
    shareable = getattr(asset_type, "is_shareable", None)
    requires_shift = getattr(asset_type, "requires_shift", None)
    return {
        "role": role,
        "role_label": rules.ROLE_LABELS.get(role, role),
        "tracking": "serialized",
        "shareable": default_shareable if shareable is None else bool(shareable),
        "requires_shift": default_shift if requires_shift is None else bool(requires_shift),
        "shareable_default": default_shareable,
        "requires_shift_default": default_shift,
        "configured": shareable is not None or requires_shift is not None,
    }


# --- Asset evaluation ---------------------------------------------------------------


def _active_asset_rows(db: Session, asset_id: UUID, req: AllocationRequest) -> list[AssetAssignment]:
    rows = db.scalars(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset_id,
            or_(AssetAssignment.returned_date.is_(None), AssetAssignment.returned_date > req.start_date),
        )
    ).all()
    out = []
    for row in rows:
        if row.id in req.exclude_ids:
            continue
        s, e = _row_dates(row)
        if dates_overlap(s, e, req.start_date, req.end_date):
            out.append(row)
    return out


def _active_reservations(
    db: Session, req: AllocationRequest, *, asset_id: UUID | None = None, pool_id: UUID | None = None
) -> list[ResourceReservation]:
    stmt = select(ResourceReservation).where(ResourceReservation.status == "ACTIVE")
    if asset_id is not None:
        stmt = stmt.where(ResourceReservation.asset_id == asset_id)
    if pool_id is not None:
        stmt = stmt.where(ResourceReservation.license_pool_id == pool_id)
    out = []
    for row in db.scalars(stmt).all():
        if row.id in req.exclude_ids:
            continue
        if dates_overlap(row.start_date, row.end_date, req.start_date, req.end_date):
            out.append(row)
    return out


def _conflict_entry(row: Any, window: Window, req: AllocationRequest, names: dict, *, kind: str) -> dict:
    s, e = _row_dates(row)
    user_id = getattr(row, "assigned_to_user_id", None) or getattr(row, "user_id", None)
    return {
        "kind": kind,
        "id": str(row.id),
        "user_id": str(user_id) if user_id else None,
        "user_name": names.get(user_id) if user_id else (getattr(row, "reserved_for", None) or None),
        "window": window.label,
        "times": window.times,
        "shift_id": str(row.shift_id) if getattr(row, "shift_id", None) else None,
        "dates": fmt_range(s, e),
        "overlap": describe_overlap(window, req.window),
        "legacy": window.legacy,
    }


def _result(status: str, reason_code: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "available": status == AVAILABLE,
        "status": status,
        "reason_code": reason_code,
        "reason": reason,
        "overridable": reason_code in OVERRIDABLE_REASONS,
        "conflicting_assignments": extra.pop("conflicts", []),
        **extra,
    }


def evaluate_asset(
    db: Session,
    asset: Asset,
    req: AllocationRequest,
    *,
    rows: list[AssetAssignment] | None = None,
    reservations: list[ResourceReservation] | None = None,
    shift_map: dict[UUID, ResourceShift] | None = None,
    names: dict[UUID, str] | None = None,
    check_packages: bool = True,
) -> dict[str, Any]:
    """Can ``req`` use this physical asset? Returns the standard result dict."""
    asset_type = asset.asset_type or db.get(AssetType, asset.asset_type_id)
    policy = sharing_policy(asset_type)
    base = {
        "resource_type": "asset",
        "resource_id": str(asset.id),
        "resource_label": asset.asset_number,
        "requested_window": req.window.label,
        "requested_dates": fmt_range(req.start_date, req.end_date),
        "policy": policy,
    }
    if asset.is_deleted or asset.status not in ASSIGNABLE_ASSET_STATUSES:
        label = LIFECYCLE_REASONS.get(asset.status or "", asset.status)
        return _result(UNAVAILABLE, REASON_LIFECYCLE, f"{asset.asset_number}: {label}",
                       remaining_capacity=0, **base)

    rows = _active_asset_rows(db, asset.id, req) if rows is None else [
        r for r in rows if r.id not in req.exclude_ids
        and dates_overlap(*_row_dates(r), req.start_date, req.end_date)
    ]
    reservations = (
        _active_reservations(db, req, asset_id=asset.id) if reservations is None else reservations
    )
    shift_map = _shift_map(db, [*rows, *reservations], shift_map)
    names = names if names is not None else _names(
        db, [r.assigned_to_user_id for r in rows] + [r.user_id for r in reservations]
    )

    same_slot: list[dict] = []
    overlaps: list[dict] = []
    legacy: list[dict] = []
    own: list[dict] = []
    for row in rows:
        w = window_for_row(row, shift_map)
        if not windows_overlap(w, req.window):
            continue
        entry = _conflict_entry(row, w, req, names, kind="assignment")
        if req.user_id is not None and row.assigned_to_user_id == req.user_id:
            own.append(entry)
        elif w.legacy:
            legacy.append(entry)
        elif req.window.shift_id and row.shift_id == req.window.shift_id and not row.start_time:
            same_slot.append(entry)
        else:
            overlaps.append(entry)

    if own:
        return _result(ASSIGNED, REASON_ALREADY_HOLDS,
                       f"Already assigned to {own[0]['user_name']} during {own[0]['window']}.",
                       conflicts=own, remaining_capacity=0, **base)

    others = [r for r in rows if req.user_id is None or r.assigned_to_user_id != req.user_id]
    if not policy["shareable"] and others:
        holder = names.get(others[0].assigned_to_user_id) or "another employee"
        return _result(
            CONFLICT, REASON_NOT_SHAREABLE,
            f"{policy['role_label']} assets are not shareable; {asset.asset_number} is assigned to {holder}.",
            conflicts=[_conflict_entry(r, window_for_row(r, shift_map), req, names, kind="assignment")
                       for r in others],
            remaining_capacity=0, **base,
        )
    if same_slot:
        c = same_slot[0]
        return _result(
            ASSIGNED, REASON_SAME_SLOT,
            f"This asset already has an open assignment for that shift ({c['user_name']}, {c['window']}).",
            conflicts=same_slot + overlaps + legacy, remaining_capacity=0, **base,
        )
    if legacy:
        c = legacy[0]
        return _result(
            CONFLICT, REASON_LEGACY,
            f"Assigned to {c['user_name']} for all hours (legacy assignment without shift — needs review).",
            conflicts=legacy + overlaps, remaining_capacity=0, **base,
        )
    if overlaps:
        parts = "; ".join(f"{c['user_name']} {c['window']} (overlap {c['overlap']})" for c in overlaps)
        if req.window.all_day:
            reason = (
                "Asset already has an open assignment. Provide shift_id for shared-desk occupancy, "
                f"or return the current user first. Assigned: {parts}."
            )
        else:
            reason = f"Workstation is already assigned during part of this employee's scheduled shift: {parts}."
        return _result(CONFLICT, REASON_TIME_OVERLAP, reason, conflicts=overlaps,
                       remaining_capacity=0, **base)

    blocking_res = []
    for res in reservations:
        if req.reservation_id == res.id or (req.user_id and res.user_id == req.user_id):
            continue
        w = window_for_row(res, shift_map)
        if windows_overlap(w, req.window):
            blocking_res.append(_conflict_entry(res, w, req, names, kind="reservation"))
    if blocking_res:
        c = blocking_res[0]
        return _result(
            RESERVED, REASON_RESERVED,
            f"Reserved for {c['user_name'] or 'another request'} during {c['window']} ({c['dates']}).",
            conflicts=blocking_res, remaining_capacity=0, **base,
        )
    if req.window.shift_id and check_packages:
        from app.services import workstation_package_service as legacy_packages

        blocked = legacy_packages._package_blocks_asset(
            db, asset.id, shift_id=req.window.shift_id, on_date=req.start_date
        )
        if blocked:
            return _result(CONFLICT, REASON_TIME_OVERLAP, blocked.get("reason") or "Used by a workstation package.",
                           remaining_capacity=0, **base)
    return _result(AVAILABLE, REASON_OK, f"Available — no overlapping assignment for {req.window.label}.",
                   remaining_capacity=1, **base)


# --- License metrics ----------------------------------------------------------------

METRIC_NAMED_USER = "NAMED_USER"
METRIC_PER_USER = "PER_USER"
METRIC_PER_DEVICE = "PER_DEVICE"
METRIC_CONCURRENT = "CONCURRENT"
METRIC_SITE = "SITE"
METRIC_UNSPECIFIED = "UNSPECIFIED"

_METRIC_BY_CODE = {
    "named_user": METRIC_NAMED_USER,
    "per_user": METRIC_PER_USER,
    "device_bound": METRIC_PER_DEVICE,
    "per_device": METRIC_PER_DEVICE,
    "floating": METRIC_CONCURRENT,
    "concurrent": METRIC_CONCURRENT,
    "network": METRIC_CONCURRENT,
    "site": METRIC_SITE,
}

METRIC_INFO: dict[str, dict[str, Any]] = {
    METRIC_NAMED_USER: {
        "label": "Named User", "shareable": False, "shift_aware": False,
        "rule": "1 right → 1 named employee. Cannot be shared between employees, regardless of shift.",
    },
    METRIC_PER_USER: {
        "label": "Per User", "shareable": False, "shift_aware": False,
        "rule": "1 right → 1 employee. Cannot be shared between employees, regardless of shift.",
    },
    METRIC_PER_DEVICE: {
        "label": "Per Device", "shareable": True, "shift_aware": False,
        "rule": "1 right → 1 device. Any employee using that device is covered; a new device consumes a new right.",
    },
    METRIC_CONCURRENT: {
        "label": "Concurrent / Floating", "shareable": True, "shift_aware": True,
        "rule": "Any number of authorized employees; scheduled or active simultaneous use cannot exceed rights owned.",
    },
    METRIC_SITE: {
        "label": "Site", "shareable": True, "shift_aware": False,
        "rule": "Site-wide entitlement covering every employee at the site.",
    },
    METRIC_UNSPECIFIED: {
        "label": "Metric not set", "shareable": False, "shift_aware": False,
        "rule": "License metric is not configured — treated as one right per assignment. Set the metric to enable sharing.",
    },
}


def license_metric(pool: SoftwareLicensePool) -> str:
    for code in (pool.assignment_model, pool.license_type):
        metric = _METRIC_BY_CODE.get((code or "").strip().lower())
        if metric:
            return metric
    return METRIC_UNSPECIFIED


def _pool_block(pool: SoftwareLicensePool, on_date: date) -> str | None:
    status = (pool.status or "active").lower()
    if status in {"terminated", "cancelled", "suspended", "draft"}:
        return f"License pool is {status} and cannot accept new assignments."
    if pool.expiry_date and pool.expiry_date < on_date:
        return f"License expired on {pool.expiry_date.isoformat()}."
    return None


def _active_license_rows(db: Session, pool_id: UUID, req: AllocationRequest) -> list[SoftwareAssignment]:
    rows = db.scalars(
        select(SoftwareAssignment).where(
            SoftwareAssignment.license_pool_id == pool_id,
            or_(SoftwareAssignment.released_date.is_(None), SoftwareAssignment.released_date > req.start_date),
        )
    ).all()
    out = []
    for row in rows:
        if row.id in req.exclude_ids:
            continue
        start = row.assigned_date or date.min
        _, end = _row_dates(row)
        if dates_overlap(start, end, req.start_date, req.end_date):
            out.append(row)
    return out


def is_scheduled(row: Any) -> bool:
    return bool(getattr(row, "shift_id", None) or getattr(row, "start_time", None))


def _holder_key(row: Any, metric: str) -> Any:
    if metric == METRIC_PER_DEVICE:
        return ("asset", row.asset_id) if row.asset_id else ("user", row.user_id or row.id)
    return ("user", row.user_id) if row.user_id else ("asset", row.asset_id or row.id)


def peak_concurrency(windows: list[Window], within: Window | None = None) -> int:
    """Max number of ``windows`` covering any minute (inside ``within`` if given)."""
    scope = within.segments() if within else [(0, DAY_MINUTES)]
    points = {s for s, _ in scope}
    for w in windows:
        for s, _ in w.segments():
            points.add(s)
    peak = 0
    for p in points:
        if not any(s <= p < e for s, e in scope):
            continue
        peak = max(peak, sum(1 for w in windows if any(s <= p < e for s, e in w.segments())))
    return peak


def evaluate_license(
    db: Session,
    pool: SoftwareLicensePool,
    req: AllocationRequest,
) -> dict[str, Any]:
    """Can ``req`` be allocated a right from this license pool?"""
    metric = license_metric(pool)
    info = METRIC_INFO[metric]
    seats = int(pool.seat_count or 0)
    rows = _active_license_rows(db, pool.id, req)
    reservations = _active_reservations(db, req, pool_id=pool.id)
    names = _names(db, [r.user_id for r in rows] + [r.user_id for r in reservations])
    base = {
        "resource_type": "license",
        "resource_id": str(pool.id),
        "resource_label": pool.entitlement_code or str(pool.id),
        "metric": metric,
        "metric_label": info["label"],
        "metric_rule": info["rule"],
        "rights_owned": seats,
        "authorized_users": len({r.user_id for r in rows if r.user_id}),
        "requested_window": req.window.label,
        "requested_dates": fmt_range(req.start_date, req.end_date),
    }
    blocked = _pool_block(pool, req.start_date)
    if blocked:
        return _result(NOT_ALLOWED, REASON_POOL_INACTIVE, blocked, remaining_capacity=0, **base)

    if metric == METRIC_SITE:
        return _result(AVAILABLE, REASON_OK, "Available — site license covers every employee.",
                       remaining_capacity=None, **base)

    if metric in {METRIC_NAMED_USER, METRIC_PER_USER, METRIC_PER_DEVICE, METRIC_UNSPECIFIED}:
        if metric == METRIC_PER_DEVICE and req.asset_id is None:
            return _result(NOT_ALLOWED, REASON_METRIC,
                           "Per Device licenses follow a device — select the computer to license.",
                           remaining_capacity=0, **base)
        if metric == METRIC_UNSPECIFIED:
            holders = {("row", r.id) for r in rows} | {("res", r.id) for r in reservations
                                                       if r.user_id != req.user_id}
            mine = None
            if req.user_id:
                mine = next((r for r in rows if r.user_id == req.user_id), None)
        else:
            holders = {_holder_key(r, metric) for r in rows}
            holders |= {("user", r.user_id) if r.user_id else ("res", r.id) for r in reservations
                        if not (req.user_id and r.user_id == req.user_id)}
            key = ("asset", req.asset_id) if metric == METRIC_PER_DEVICE else ("user", req.user_id)
            mine = next((r for r in rows if _holder_key(r, metric) == key), None)
        used = len(holders)
        base.update(rights_allocated=used)
        if mine is not None:
            who = "this device" if metric == METRIC_PER_DEVICE else (names.get(req.user_id) or "this employee")
            return _result(ASSIGNED, REASON_ALREADY_HOLDS,
                           f"Already allocated to {who} — no additional right consumed.",
                           remaining_capacity=max(0, seats - used), **base)
        if used >= seats:
            holder_names = sorted({names.get(r.user_id) for r in rows if r.user_id and names.get(r.user_id)})
            if metric in {METRIC_NAMED_USER, METRIC_PER_USER}:
                who = ", ".join(holder_names) or "other employees"
                reason = (
                    f"Not available — this is a {info['label']} license already assigned to {who}. "
                    f"{info['label']} licenses cannot be shared between employees."
                    if seats == 1
                    else f"No available {info['label'].lower()} entitlement ({used} of {seats} rights allocated)."
                )
            elif metric == METRIC_PER_DEVICE:
                reason = f"No available device right ({used} of {seats} devices licensed)."
            else:
                reason = f"No available licenses ({used} of {seats} allocated). {info['rule']}"
            return _result(NOT_ALLOWED, REASON_CAPACITY, reason,
                           conflicts=[{"kind": "assignment", "id": str(r.id),
                                       "user_id": str(r.user_id) if r.user_id else None,
                                       "user_name": names.get(r.user_id), "window": "All hours",
                                       "times": "00:00–24:00", "dates": fmt_range(*_row_dates(r)),
                                       "overlap": "", "legacy": False} for r in rows],
                           remaining_capacity=0, **base)
        return _result(AVAILABLE, REASON_OK,
                       f"Available — {seats - used} of {seats} rights free. {info['rule']}",
                       remaining_capacity=seats - used, **base)

    # Concurrent / floating: scheduled windows may not exceed rights at any minute.
    shift_map = _shift_map(db, [*rows, *reservations])
    scheduled = [(r, window_for_row(r, shift_map)) for r in rows if is_scheduled(r)]
    scheduled += [(r, window_for_row(r, shift_map)) for r in reservations
                  if not (req.user_id and r.user_id == req.user_id)]
    active_usage = count_active_sessions(db, pool.id)
    base.update(scheduled_users=len({getattr(r, "user_id", None) for r, _ in scheduled}),
                active_usage=active_usage)
    if req.user_id and any(r.user_id == req.user_id for r in rows):
        own = [r for r in rows if r.user_id == req.user_id]
        own_sched = [(r, window_for_row(r, shift_map)) for r in own if is_scheduled(r)]
        if req.window.all_day and not req.window.shift_id:
            return _result(ASSIGNED, REASON_ALREADY_HOLDS,
                           f"{names.get(req.user_id) or 'Employee'} is already authorized for this license.",
                           remaining_capacity=None, **base)
        if any(windows_overlap(w, req.window) for _, w in own_sched):
            return _result(ASSIGNED, REASON_ALREADY_HOLDS,
                           f"{names.get(req.user_id) or 'Employee'} is already scheduled during {req.window.label}.",
                           remaining_capacity=None, **base)
    if req.window.all_day and not req.window.shift_id:
        return _result(AVAILABLE, REASON_OK,
                       "Authorized — an unscheduled authorization does not consume a concurrent right "
                       "until usage is scheduled or the license is checked out.",
                       remaining_capacity=seats - peak_concurrency([w for _, w in scheduled]), **base)
    overlapping = [(r, w) for r, w in scheduled if windows_overlap(w, req.window)]
    peak = peak_concurrency([w for _, w in overlapping], within=req.window)
    remaining = seats - peak
    conflicts = [_conflict_entry(r, w, req, names,
                                 kind="reservation" if isinstance(r, ResourceReservation) else "assignment")
                 for r, w in overlapping]
    base.update(scheduled_peak=peak)
    if remaining < 1:
        holders = ", ".join(f"{c['user_name'] or 'reservation'} {c['window']}" for c in conflicts)
        return _result(
            CONFLICT, REASON_CAPACITY,
            f"LICENSE CONCURRENCY CONFLICT — {seats} concurrent right{'s' if seats != 1 else ''} "
            f"already scheduled during {req.window.label}: {holders}.",
            conflicts=conflicts, remaining_capacity=0, **base,
        )
    return _result(
        AVAILABLE, REASON_OK,
        f"Available — no concurrent conflict ({peak} of {seats} rights scheduled during {req.window.label}).",
        conflicts=conflicts, remaining_capacity=remaining, **base,
    )


# --- License usage (check-out / check-in) -------------------------------------------


def count_active_sessions(db: Session, pool_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(LicenseUsageSession).where(
                LicenseUsageSession.license_pool_id == pool_id,
                LicenseUsageSession.checked_in_at.is_(None),
            )
        )
        or 0
    )


def license_free_in_window(
    db: Session, pool: SoftwareLicensePool, window: Window, *, on_date: date | None = None
) -> int | None:
    """Rights still free during ``window`` (None = unlimited site license)."""
    when = on_date or date.today()
    metric = license_metric(pool)
    if metric == METRIC_SITE:
        return None
    if _pool_block(pool, when):
        return 0
    seats = int(pool.seat_count or 0)
    probe = AllocationRequest(start_date=when, end_date=when, window=ALL_HOURS)
    rows = _active_license_rows(db, pool.id, probe)
    reservations = _active_reservations(db, probe, pool_id=pool.id)
    if metric != METRIC_CONCURRENT:
        if metric == METRIC_UNSPECIFIED:
            used = len(rows) + len(reservations)
        else:
            used = len({_holder_key(r, metric) for r in rows}) + len(reservations)
        return max(0, seats - used)
    shift_map = _shift_map(db, [*rows, *reservations])
    windows = [window_for_row(r, shift_map) for r in rows if is_scheduled(r)]
    windows += [window_for_row(r, shift_map) for r in reservations]
    return max(0, seats - peak_concurrency(windows, within=window))


def license_summary(db: Session, pool: SoftwareLicensePool, *, on_date: date | None = None) -> dict[str, Any]:
    """Entitlement vs allocation vs consumption + compliance for one pool."""
    when = on_date or date.today()
    metric = license_metric(pool)
    info = METRIC_INFO[metric]
    seats = int(pool.seat_count or 0)
    probe = AllocationRequest(start_date=when, end_date=when, window=ALL_HOURS)
    rows = _active_license_rows(db, pool.id, probe)
    authorized = len({r.user_id for r in rows if r.user_id})
    active = count_active_sessions(db, pool.id)
    scheduled_peak = None
    if metric == METRIC_SITE:
        allocated, available = authorized, None
    elif metric == METRIC_CONCURRENT:
        shift_map = _shift_map(db, rows)
        scheduled_peak = peak_concurrency([window_for_row(r, shift_map) for r in rows if is_scheduled(r)])
        allocated = scheduled_peak
        available = max(0, seats - max(scheduled_peak, active))
    elif metric == METRIC_UNSPECIFIED:
        allocated = len(rows)
        available = max(0, seats - allocated)
    else:
        allocated = len({_holder_key(r, metric) for r in rows})
        available = max(0, seats - allocated)
    consumed = active if metric == METRIC_CONCURRENT else allocated
    if pool.expiry_date and pool.expiry_date < when and rows:
        status, why = "EXPIRED", f"Expired on {pool.expiry_date.isoformat()} with {len(rows)} active assignment(s)."
    elif metric != METRIC_SITE and (allocated > seats or active > seats):
        status, why = "OVER_ALLOCATED", f"{max(allocated, active)} rights in use but only {seats} owned."
    elif metric != METRIC_SITE and allocated == seats and seats > 0:
        status, why = "FULLY_ALLOCATED", "All rights are allocated; the next request will be blocked."
    else:
        status, why = "COMPLIANT", "Allocation is within the rights owned."
    return {
        "metric": metric,
        "metric_label": info["label"],
        "metric_rule": info["rule"],
        "shareable": info["shareable"],
        "rights_owned": seats,
        "rights_allocated": allocated,
        "rights_consumed": consumed,
        "available_rights": available,
        "authorized_users": authorized,
        "scheduled_peak": scheduled_peak,
        "active_usage": active,
        "compliance_status": status,
        "compliance_reason": why,
    }


# --- Schedules ----------------------------------------------------------------------


def _timeline(entries: list[tuple[Window, dict]], capacity: int | None) -> list[dict[str, Any]]:
    """Split the day into blocks with their occupants and remaining capacity."""
    bounds = {0, DAY_MINUTES}
    for w, _ in entries:
        for s, e in w.segments():
            bounds.update({s, e})
    points = sorted(bounds)
    blocks: list[dict[str, Any]] = []
    for lo, hi in zip(points, points[1:]):
        occupants = [meta for w, meta in entries if any(s <= lo < e for s, e in w.segments())]
        remaining = None if capacity is None else capacity - len(occupants)
        key = tuple(sorted(o["id"] for o in occupants))
        if blocks and blocks[-1]["_key"] == key:
            blocks[-1]["end"] = fmt_minutes(hi)
            continue
        blocks.append({"_key": key, "start": fmt_minutes(lo), "end": fmt_minutes(hi),
                       "occupants": occupants, "remaining_capacity": remaining,
                       "available": remaining is None or remaining > 0})
    for b in blocks:
        b.pop("_key")
    return blocks


def asset_schedule(db: Session, asset: Asset, *, on_date: date | None = None) -> dict[str, Any]:
    when = on_date or date.today()
    probe = AllocationRequest(start_date=when, end_date=when, window=ALL_HOURS)
    rows = _active_asset_rows(db, asset.id, probe)
    reservations = _active_reservations(db, probe, asset_id=asset.id)
    shift_map = _shift_map(db, [*rows, *reservations])
    names = _names(db, [r.assigned_to_user_id for r in rows] + [r.user_id for r in reservations])
    entries = []
    for row in rows:
        w = window_for_row(row, shift_map)
        entries.append((w, {"id": str(row.id), "kind": "assignment", "user_id": str(row.assigned_to_user_id),
                            "user_name": names.get(row.assigned_to_user_id), "window": w.label,
                            "times": w.times, "legacy": w.legacy, "assignment_type": row.assignment_type,
                            "dates": fmt_range(*_row_dates(row))}))
    for res in reservations:
        w = window_for_row(res, shift_map)
        entries.append((w, {"id": str(res.id), "kind": "reservation",
                            "user_id": str(res.user_id) if res.user_id else None,
                            "user_name": names.get(res.user_id) if res.user_id else res.reserved_for,
                            "window": w.label, "times": w.times, "legacy": False,
                            "assignment_type": "RESERVED", "dates": fmt_range(res.start_date, res.end_date)}))
    lifecycle_ok = not asset.is_deleted and asset.status in ASSIGNABLE_ASSET_STATUSES
    blocks = _timeline(entries, 1 if lifecycle_ok else 0)
    policy = sharing_policy(asset.asset_type or db.get(AssetType, asset.asset_type_id))
    if not policy["shareable"] and rows:
        for b in blocks:
            b["available"] = False
            b["remaining_capacity"] = 0
    return {
        "resource_type": "asset",
        "resource_id": str(asset.id),
        "resource_label": asset.asset_number,
        "on_date": when.isoformat(),
        "lifecycle_status": asset.status,
        "lifecycle_ok": lifecycle_ok,
        "lifecycle_reason": None if lifecycle_ok else LIFECYCLE_REASONS.get(asset.status or "", asset.status),
        "policy": policy,
        "assignments": [meta for _, meta in entries],
        "blocks": blocks,
    }


def license_schedule(db: Session, pool: SoftwareLicensePool, *, on_date: date | None = None) -> dict[str, Any]:
    when = on_date or date.today()
    probe = AllocationRequest(start_date=when, end_date=when, window=ALL_HOURS)
    rows = _active_license_rows(db, pool.id, probe)
    reservations = _active_reservations(db, probe, pool_id=pool.id)
    shift_map = _shift_map(db, [*rows, *reservations])
    names = _names(db, [r.user_id for r in rows] + [r.user_id for r in reservations])
    metric = license_metric(pool)
    entries, authorized = [], []
    for row in rows:
        meta = {"id": str(row.id), "kind": "assignment", "user_id": str(row.user_id) if row.user_id else None,
                "user_name": names.get(row.user_id) if row.user_id else None,
                "asset_id": str(row.asset_id) if row.asset_id else None,
                "dates": fmt_range(*_row_dates(row))}
        if metric == METRIC_CONCURRENT and is_scheduled(row):
            w = window_for_row(row, shift_map)
            entries.append((w, {**meta, "window": w.label, "times": w.times}))
        else:
            authorized.append({**meta, "window": "Unscheduled" if metric == METRIC_CONCURRENT else "All hours"})
    for res in reservations:
        w = window_for_row(res, shift_map)
        entries.append((w, {"id": str(res.id), "kind": "reservation",
                            "user_id": str(res.user_id) if res.user_id else None,
                            "user_name": names.get(res.user_id) if res.user_id else res.reserved_for,
                            "window": w.label, "times": w.times,
                            "dates": fmt_range(res.start_date, res.end_date)}))
    capacity = None if metric == METRIC_SITE else int(pool.seat_count or 0)
    return {
        "resource_type": "license",
        "resource_id": str(pool.id),
        "on_date": when.isoformat(),
        "summary": license_summary(db, pool, on_date=when),
        "scheduled": [meta for _, meta in entries],
        "authorized_only": authorized,
        "blocks": _timeline(entries, capacity) if metric == METRIC_CONCURRENT else [],
    }


# --- Dispatcher ---------------------------------------------------------------------


def calculate_resource_availability(
    db: Session,
    *,
    resource_type: str,
    resource_id: UUID,
    req: AllocationRequest,
) -> dict[str, Any]:
    if resource_type == "asset":
        asset = db.get(Asset, resource_id)
        if asset is None:
            raise ProTrackValidationError("Asset not found.", status_code=404)
        return evaluate_asset(db, asset, req)
    if resource_type == "license":
        pool = db.get(SoftwareLicensePool, resource_id)
        if pool is None:
            raise ProTrackValidationError("License pool not found.", status_code=404)
        return evaluate_license(db, pool, req)
    raise ProTrackValidationError("resource_type must be 'asset' or 'license'.")


def raise_if_blocked(result: dict[str, Any], *, override: bool = False, override_reason: str | None = None) -> None:
    """Translate a blocking result into the API error (409 for schedule conflicts)."""
    if result["available"]:
        return
    if override and result["overridable"]:
        if not (override_reason or "").strip():
            raise ProTrackValidationError("override_reason is required when forcing a schedule conflict.")
        return
    schedule_conflict = result["reason_code"] in {
        REASON_TIME_OVERLAP, REASON_SAME_SLOT, REASON_LEGACY, REASON_RESERVED, REASON_NOT_SHAREABLE,
    } or (result["reason_code"] == REASON_CAPACITY and result["status"] == CONFLICT)
    code = 409 if schedule_conflict else 422
    raise ProTrackValidationError(result["reason"], status_code=code)
