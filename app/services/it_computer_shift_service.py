"""Computers grouped by shift for Resource Planning.

Uses existing AssetAssignment + get_employee_shift — no shared-desk master.
Open computers are the shared pool available to any shift.
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
    """Availability and assignments bucketed by company shift masters."""
    on_date = on_date or date.today()
    resource_shift_service.ensure_company_standard_shifts(db)
    shifts = resource_shift_service.list_shifts(db, active_only=True)

    computers = list(
        db.scalars(
            select(Computer)
            .options(selectinload(Computer.asset).selectinload(Asset.asset_type))
            .order_by(Computer.computer_name)
        ).all()
    )

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
        if status not in CURRENT_INVENTORY_STATUSES and status not in {
            "retired",
            "disposed",
            "returned",
        }:
            continue

        row = _computer_row(db, computer, on_date=on_date)

        if status == "available":
            open_rows.append(row)
            continue
        if status == "maintenance":
            maintenance_rows.append(row)
            continue
        if status in {"retired", "disposed", "returned"}:
            retired_rows.append(row)
            continue

        if team_id is not None and row["assigned_to_user_id"]:
            from app.models.models import TeamMember

            assignee_id = UUID(row["assigned_to_user_id"])
            assignee = db.get(User, assignee_id)
            in_team = False
            if assignee is not None and assignee.team_id == team_id:
                in_team = True
            elif db.scalar(
                select(TeamMember.id).where(
                    TeamMember.user_id == assignee_id,
                    TeamMember.team_id == team_id,
                ).limit(1)
            ):
                in_team = True
            if not in_team:
                continue

        code = row["current_shift_code"]
        if code and code in by_shift:
            by_shift[code].append(row)
        else:
            unassigned_shift.append(row)

        if row["is_shared_candidate"]:
            shared_rows.append(row)

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
