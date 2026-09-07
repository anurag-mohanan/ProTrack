"""IT computer ↔ employee data-quality reconciliation.

Repairs only confident inconsistencies (status=assigned with no open assignment).
Does not invent employee/team/location links.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.it_operations import Asset, AssetAssignment, Computer
from app.models.models import Team, User
from app.services import it_asset_service
from app.services import resource_shift_service


def _open_assignment_asset_ids(db: Session) -> set[UUID]:
    rows = db.scalars(
        select(AssetAssignment.asset_id).where(AssetAssignment.returned_date.is_(None))
    ).all()
    return set(rows)


def computer_data_quality_report(db: Session) -> dict:
    """Counts and sample rows for Resource Planning / IT data quality."""
    open_ids = _open_assignment_asset_ids(db)
    computers = list(
        db.scalars(
            select(Computer).options(selectinload(Computer.asset)).order_by(Computer.computer_name)
        ).all()
    )

    assigned_no_employee: list[dict] = []
    available_with_assignment: list[dict] = []
    no_location: list[dict] = []
    no_ram: list[dict] = []
    no_team: list[dict] = []

    for computer in computers:
        asset = computer.asset
        if asset is None or getattr(asset, "is_deleted", False):
            continue
        status = (asset.status or "").lower()
        has_open = asset.id in open_ids
        row = {
            "computer_id": str(computer.id),
            "computer_name": computer.computer_name,
            "asset_number": asset.asset_number,
            "status": status,
        }
        if status == "assigned" and not has_open:
            assigned_no_employee.append(row)
        if status == "available" and has_open:
            available_with_assignment.append(row)
        if not (asset.location or "").strip():
            no_location.append(row)
        if computer.ram_gb is None:
            no_ram.append(row)
        if has_open:
            assignment, user = it_asset_service.get_computer_current_assignee(db, asset.id)
            _ = assignment
            if user is not None and not _resolve_team_name(db, user):
                no_team.append({**row, "user_id": str(user.id), "user_name": _full_name(user)})

    employees_no_computer = _employees_without_computer(db, open_ids)
    employees_no_shift = _employees_without_shift_today(db)

    return {
        "computers_total": len(computers),
        "assigned_without_employee": len(assigned_no_employee),
        "available_with_open_assignment": len(available_with_assignment),
        "computers_without_location": len(no_location),
        "computers_without_ram": len(no_ram),
        "assigned_without_team": len(no_team),
        "employees_without_computer": len(employees_no_computer),
        "employees_without_shift_today": len(employees_no_shift),
        "samples": {
            "assigned_without_employee": assigned_no_employee[:50],
            "available_with_open_assignment": available_with_assignment[:50],
            "assigned_without_team": no_team[:50],
            "employees_without_computer": employees_no_computer[:50],
            "employees_without_shift_today": employees_no_shift[:50],
        },
    }


def repair_orphan_assigned_status(
    db: Session,
    *,
    commit: bool = True,
) -> dict:
    """Reset Asset.status from assigned → available when no open assignment exists.

    Does not invent assignees. Safe consistency repair only.
    """
    open_ids = _open_assignment_asset_ids(db)
    assets = list(
        db.scalars(
            select(Asset).where(
                Asset.is_deleted.is_(False),
                Asset.status == "assigned",
            )
        ).all()
    )
    repaired: list[dict] = []
    for asset in assets:
        if asset.id in open_ids:
            continue
        asset.status = "available"
        db.add(asset)
        repaired.append(
            {
                "asset_id": str(asset.id),
                "asset_number": asset.asset_number,
                "previous_status": "assigned",
                "new_status": "available",
            }
        )
    if commit and repaired:
        db.commit()
    elif repaired:
        db.flush()
    return {"repaired_count": len(repaired), "repaired": repaired}


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def _resolve_team_name(db: Session, user: User) -> str | None:
    if getattr(user, "team", None) is not None and user.team is not None:
        return user.team.name
    if user.team_id:
        team = db.get(Team, user.team_id)
        if team is not None:
            return team.name
    from app.models.models import TeamMember

    member = db.scalar(
        select(TeamMember)
        .where(TeamMember.user_id == user.id, TeamMember.is_primary.is_(True))
        .limit(1)
    )
    if member is None:
        member = db.scalar(select(TeamMember).where(TeamMember.user_id == user.id).limit(1))
    if member is not None:
        team = db.get(Team, member.team_id)
        return team.name if team else None
    return None


def resolve_computer_display(
    db: Session,
    computer: Computer,
    *,
    on_date: date | None = None,
) -> dict:
    """Authoritative display fields for computer list/detail (no invented data)."""
    from app.services import it_computer_shift_service as shift_computers

    on_date = on_date or date.today()
    asset = computer.asset
    assignment = None
    assignee = None
    team_name = None
    shift_code = None
    shift_name = None
    shift_display = None
    next_shift_code = None
    next_shift_name = None
    next_shift_display = None
    next_change_date = None
    previous_user_id = None
    previous_user_name = None
    other_shift_user_id = None
    other_shift_user_name = None
    other_shift_code = None
    other_shift_name = None
    other_shift_display = None
    is_shared_candidate = False
    data_quality: list[str] = []

    if asset is not None:
        assignment, assignee = it_asset_service.get_computer_current_assignee(db, asset.id)
        prev_id, prev_name = shift_computers.last_used_by(db, asset.id)
        previous_user_id = str(prev_id) if prev_id else None
        previous_user_name = prev_name

        # Shared-desk candidate: more than one distinct historical assignee
        distinct_users = set(
            db.scalars(
                select(AssetAssignment.assigned_to_user_id).where(
                    AssetAssignment.asset_id == asset.id
                )
            ).all()
        )
        is_shared_candidate = len(distinct_users) > 1

        if assignee is not None:
            team_name = _resolve_team_name(db, assignee)
            shift = resource_shift_service.get_employee_shift(db, assignee.id, on_date)
            if shift is not None:
                shift_code = shift.code
                shift_name = shift.name
                shift_display = resource_shift_service.format_shift_label(shift)
            nxt = resource_shift_service.next_employee_shift(
                db, assignee.id, after_date=on_date
            )
            if nxt and nxt.get("next_shift") is not None:
                next_shift = nxt["next_shift"]
                next_shift_code = next_shift.code
                next_shift_name = next_shift.name
                next_shift_display = resource_shift_service.format_shift_label(next_shift)
                next_change_date = (
                    nxt["next_change_date"].isoformat() if nxt.get("next_change_date") else None
                )
            peer = shift_computers.other_shift_peer(
                db,
                asset.id,
                current_user_id=assignee.id,
                on_date=on_date,
            )
            if peer:
                other_shift_user_id = peer["user_id"]
                other_shift_user_name = peer["user_name"]
                other_shift_code = peer["shift_code"]
                other_shift_name = peer["shift_name"]
                other_shift_display = peer["shift_display"]

        status = (asset.status or "").lower()
        if status == "assigned" and assignee is None:
            data_quality.append("status_assigned_without_employee")
        if assignee is not None and not team_name:
            data_quality.append("employee_without_team")
        if not (asset.location or "").strip():
            data_quality.append("missing_location")

    return {
        "assignment": assignment,
        "assignee": assignee,
        "team_name": team_name,
        "shift_code": shift_code,
        "shift_name": shift_name,
        "shift_display": shift_display,
        "next_shift_code": next_shift_code,
        "next_shift_name": next_shift_name,
        "next_shift_display": next_shift_display,
        "next_change_date": next_change_date,
        "previous_user_id": previous_user_id,
        "previous_user_name": previous_user_name,
        "other_shift_user_id": other_shift_user_id,
        "other_shift_user_name": other_shift_user_name,
        "other_shift_code": other_shift_code,
        "other_shift_name": other_shift_name,
        "other_shift_display": other_shift_display,
        "is_shared_candidate": is_shared_candidate,
        "data_quality": data_quality,
    }


def _employees_without_computer(db: Session, open_assignment_asset_ids: set[UUID]) -> list[dict]:
    _ = open_assignment_asset_ids
    assigned_user_ids = set(
        db.scalars(
            select(AssetAssignment.assigned_to_user_id).where(
                AssetAssignment.returned_date.is_(None)
            )
        ).all()
    )
    users = db.scalars(
        select(User).where(User.is_deleted.is_(False), User.is_active.is_(True))
    ).all()
    out = []
    for user in users:
        if user.id in assigned_user_ids:
            continue
        out.append({"user_id": str(user.id), "user_name": _full_name(user)})
    return out


def _employees_without_shift_today(db: Session) -> list[dict]:
    from datetime import date

    today = date.today()
    users = db.scalars(
        select(User).where(User.is_deleted.is_(False), User.is_active.is_(True))
    ).all()
    out = []
    for user in users:
        if resource_shift_service.get_employee_shift(db, user.id, today) is None:
            out.append({"user_id": str(user.id), "user_name": _full_name(user)})
    return out
