"""Computers grouped by shift for Resource Planning.

Uses AssetAssignment windows evaluated by the central allocation engine.
Open computers are those still free in at least one shift.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.it_operations import CURRENT_INVENTORY_STATUSES, Asset, AssetAssignment, Computer
from app.models.models import User
from app.services import it_asset_service
from app.services import it_computer_reconciliation_service as recon
from app.services import resource_shift_service


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def _computer_row(db: Session, computer: Computer, *, on_date: date) -> dict:
    resolved = recon.resolve_computer_display(db, computer, on_date=on_date)
    asset = computer.asset
    assignee = resolved["assignee"]
    assignment = resolved["assignment"]
    return {
        "computer_id": str(computer.id),
        "asset_id": str(computer.asset_id),
        "computer_name": computer.computer_name,
        "asset_number": asset.asset_number if asset else None,
        "status": (asset.status if asset else None),
        "location": asset.location if asset else None,
        "is_open": (asset.status or "").lower() == "available" if asset else False,
        "assigned_to_user_id": str(assignee.id) if assignee else None,
        "assigned_to_name": _full_name(assignee),
        "assigned_to_team": resolved["team_name"],
        "assigned_date": assignment.assigned_date.isoformat() if assignment else None,
        "current_shift_code": resolved["shift_code"],
        "current_shift_name": resolved["shift_name"],
        "current_shift_display": resolved["shift_display"],
        "next_shift_code": resolved.get("next_shift_code"),
        "next_shift_name": resolved.get("next_shift_name"),
        "next_shift_display": resolved.get("next_shift_display"),
        "next_change_date": resolved.get("next_change_date"),
        "previous_user_id": resolved.get("previous_user_id"),
        "previous_user_name": resolved.get("previous_user_name"),
        "other_shift_user_id": resolved.get("other_shift_user_id"),
        "other_shift_user_name": resolved.get("other_shift_user_name"),
        "other_shift_code": resolved.get("other_shift_code"),
        "other_shift_name": resolved.get("other_shift_name"),
        "other_shift_display": resolved.get("other_shift_display"),
        "is_shared_candidate": bool(resolved.get("is_shared_candidate")),
        "data_quality_flags": resolved.get("data_quality") or [],
    }


def computers_by_shift(
    db: Session,
    *,
    on_date: date | None = None,
    team_id: UUID | None = None,
) -> dict:
    """Computers bucketed by shift; free/busy per slot comes from the allocation engine.

    A shared workstation appears under every shift it is scheduled in (with that
    shift's occupant) and in ``open_computers`` while any shift is still free.
    """
    from app.models.resource_shifts import ResourceShift
    from app.services import it_availability_service
    from app.services import resource_allocation_engine as allocation

    on_date = on_date or date.today()
    resource_shift_service.ensure_company_standard_shifts(db)
    shifts = resource_shift_service.list_shifts(db, active_only=True)
    matrix = it_availability_service.computer_availability(db, on_date=on_date)
    slots_by_asset = {row["asset_id"]: row["shifts"] for row in matrix["computers"]}

    computers = list(
        db.scalars(
            select(Computer)
            .options(selectinload(Computer.asset).selectinload(Asset.asset_type))
            .order_by(Computer.computer_name)
        ).all()
    )
    team_members: set[UUID] | None = None
    if team_id is not None:
        from app.models.models import TeamMember

        team_members = set(db.scalars(select(User.id).where(User.team_id == team_id)).all())
        team_members |= set(db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)).all())
    shift_map = {s.id: s for s in db.scalars(select(ResourceShift)).all()}

    open_rows: list[dict] = []
    maintenance_rows: list[dict] = []
    retired_rows: list[dict] = []
    by_shift: dict[str, list[dict]] = {shift.code: [] for shift in shifts}
    unassigned_shift: list[dict] = []
    shared_rows: list[dict] = []

    for computer in computers:
        asset = computer.asset
        if asset is None or getattr(asset, "is_deleted", False):
            continue
        status = (asset.status or "").lower()
        if status not in CURRENT_INVENTORY_STATUSES and status not in {"retired", "disposed", "returned"}:
            continue
        row = _computer_row(db, computer, on_date=on_date)
        slots = slots_by_asset.get(str(asset.id), [])
        free = [s["shift_code"] for s in slots if s["status"] == "AVAILABLE"]
        row["free_shifts"] = free
        row["is_open"] = bool(free)
        if status == "maintenance":
            maintenance_rows.append(row)
            continue
        if status in {"retired", "disposed", "returned"}:
            retired_rows.append(row)
            continue
        if free:
            open_rows.append(row)

        occupants = [
            r for r in it_asset_service.list_open_assignments(db, asset.id)
            if allocation.dates_overlap(*allocation._row_dates(r), on_date, on_date)
        ]
        if len(occupants) > 1:
            shared_rows.append(row)
        for assignment in occupants:
            if team_members is not None and assignment.assigned_to_user_id not in team_members:
                continue
            user = db.get(User, assignment.assigned_to_user_id)
            window = allocation.window_for_row(assignment, shift_map)
            occupant_row = {
                **row,
                "assigned_to_user_id": str(assignment.assigned_to_user_id),
                "assigned_to_name": _full_name(user),
                "assigned_date": assignment.assigned_date.isoformat(),
                "assignment_window": window.label,
                "needs_review": window.legacy,
            }
            placed = False
            if window.all_day:
                employee_shift = resource_shift_service.get_employee_shift(db, assignment.assigned_to_user_id, on_date)
                if employee_shift is not None and employee_shift.code in by_shift:
                    by_shift[employee_shift.code].append(
                        {**occupant_row, "current_shift_code": employee_shift.code,
                         "current_shift_name": employee_shift.name,
                         "current_shift_display": resource_shift_service.format_shift_label(employee_shift)}
                    )
                    placed = True
            else:
                for shift in shifts:
                    if assignment.shift_id == shift.id or (
                        not assignment.shift_id
                        and allocation.windows_overlap(window, allocation.window_for_shift(shift))
                    ):
                        by_shift[shift.code].append(
                            {**occupant_row, "current_shift_code": shift.code, "current_shift_name": shift.name,
                             "current_shift_display": resource_shift_service.format_shift_label(shift)}
                        )
                        placed = True
            if not placed:
                unassigned_shift.append(occupant_row)

    shift_sections = []
    for shift in shifts:
        rows = by_shift.get(shift.code, [])
        shift_sections.append(
            {
                "shift_id": str(shift.id),
                "shift_code": shift.code,
                "shift_name": shift.name,
                "shift_display": resource_shift_service.format_shift_label(shift),
                "assigned_count": len(rows),
                "available_count": sum(
                    1 for slots in slots_by_asset.values()
                    for s in slots if s["shift_code"] == shift.code and s["status"] == "AVAILABLE"
                ),
                "computers": rows,
            }
        )

    return {
        "on_date": on_date.isoformat(),
        "team_id": str(team_id) if team_id else None,
        "summary": {
            "open": len(open_rows),
            "maintenance": len(maintenance_rows),
            "retired": len(retired_rows),
            "assigned_with_shift": sum(s["assigned_count"] for s in shift_sections),
            "assigned_without_shift": len(unassigned_shift),
            "shared_candidates": len(shared_rows),
        },
        "open_computers": open_rows,
        "maintenance_computers": maintenance_rows,
        "shifts": shift_sections,
        "assigned_without_shift": unassigned_shift,
        "shared_computers": shared_rows,
    }


def last_used_by(db: Session, asset_id: UUID) -> tuple[UUID | None, str | None]:
    """Previous assignee from closed history (not the current open assignment)."""
    current = it_asset_service.get_current_assignment(db, asset_id)
    current_user_id = current.assigned_to_user_id if current else None
    rows = list(
        db.scalars(
            select(AssetAssignment)
            .where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.returned_date.is_not(None),
            )
            .order_by(
                AssetAssignment.returned_date.desc(),
                AssetAssignment.assigned_date.desc(),
            )
        ).all()
    )
    for row in rows:
        if current_user_id is not None and row.assigned_to_user_id == current_user_id:
            continue
        user = db.get(User, row.assigned_to_user_id)
        return row.assigned_to_user_id, _full_name(user)
    # If unassigned, last closed row is last used by
    if current is None and rows:
        user = db.get(User, rows[0].assigned_to_user_id)
        return rows[0].assigned_to_user_id, _full_name(user)
    return None, None


def other_shift_peer(
    db: Session,
    asset_id: UUID,
    *,
    current_user_id: UUID | None,
    on_date: date,
) -> dict | None:
    """Prefer a live shared-desk open assignment on another shift; else historical peer."""
    open_rows = it_asset_service.list_open_assignments(db, asset_id)
    for row in open_rows:
        if current_user_id is not None and row.assigned_to_user_id == current_user_id:
            continue
        user = db.get(User, row.assigned_to_user_id)
        if user is None or getattr(user, "is_deleted", False) or not user.is_active:
            continue
        shift = None
        if row.shift_id is not None:
            from app.models.resource_shifts import ResourceShift

            shift = db.get(ResourceShift, row.shift_id)
        if shift is None:
            shift = resource_shift_service.get_employee_shift(db, user.id, on_date)
        if shift is None:
            continue
        return {
            "user_id": str(user.id),
            "user_name": _full_name(user),
            "shift_code": shift.code,
            "shift_name": shift.name,
            "shift_display": resource_shift_service.format_shift_label(shift),
            "live_assignment": True,
        }

    if current_user_id is None:
        return None
    current_shift = resource_shift_service.get_employee_shift(db, current_user_id, on_date)
    current_shift_id = current_shift.id if current_shift else None

    prior_user_ids = list(
        db.scalars(
            select(AssetAssignment.assigned_to_user_id)
            .where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.assigned_to_user_id != current_user_id,
            )
            .distinct()
        ).all()
    )
    for user_id in prior_user_ids:
        user = db.get(User, user_id)
        if user is None or getattr(user, "is_deleted", False) or not user.is_active:
            continue
        shift = resource_shift_service.get_employee_shift(db, user_id, on_date)
        if shift is None:
            continue
        if current_shift_id is not None and shift.id == current_shift_id:
            continue
        return {
            "user_id": str(user_id),
            "user_name": _full_name(user),
            "shift_code": shift.code,
            "shift_name": shift.name,
            "shift_display": resource_shift_service.format_shift_label(shift),
            "live_assignment": False,
        }
    return None
