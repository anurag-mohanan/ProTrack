"""IT Users/People — views over ProTrack User (employee) master. No employee copy."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.it_operations import (
    Asset,
    AssetAssignment,
    Computer,
    ITUserAccount,
)
from app.models.models import OrgDepartment, Team, User


def _full_name(user: User) -> str:
    return f"{user.first_name} {user.last_name}".strip()


def _employment_status(user: User) -> str:
    if user.is_deleted or user.is_archived:
        return "former"
    if not user.is_active:
        return "inactive"
    return "active"


def _dept_name(user: User) -> str | None:
    if user.org_department is not None:
        return user.org_department.name
    if user.department is not None:
        return user.department.name
    return None


def list_it_people(
    db: Session,
    *,
    status: str = "active",
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """List employees/resources for IT Users. status: active|inactive|former|all."""
    stmt = (
        select(User)
        .options(
            selectinload(User.team),
            selectinload(User.department),
            selectinload(User.org_department),
        )
        .where(User.is_deleted.is_(False))
    )
    status_norm = (status or "active").strip().lower()
    if status_norm == "active":
        stmt = stmt.where(User.is_active.is_(True), User.is_archived.is_(False))
    elif status_norm == "inactive":
        stmt = stmt.where(User.is_active.is_(False), User.is_archived.is_(False))
    elif status_norm == "former":
        stmt = stmt.where(or_(User.is_archived.is_(True), User.leaving_date.is_not(None)))
    # all: no extra filter beyond not deleted

    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(q),
                User.last_name.ilike(q),
                User.email.ilike(q),
                User.designation.ilike(q),
            )
        )

    people = list(
        db.scalars(stmt.order_by(User.first_name, User.last_name)).all()
    )

    # Enrich with computer / assets / accounts
    open_assignments = {
        row.assigned_to_user_id: row
        for row in db.scalars(
            select(AssetAssignment).where(AssetAssignment.returned_date.is_(None))
        ).all()
    }
    computers_by_asset = {
        c.asset_id: c
        for c in db.scalars(select(Computer)).all()
    }
    assets_by_id = {
        a.id: a
        for a in db.scalars(select(Asset).where(Asset.is_deleted.is_(False))).all()
    }
    account_counts: dict[UUID, int] = {}
    for uid, n in db.execute(
        select(ITUserAccount.user_id, func.count())
        .group_by(ITUserAccount.user_id)
    ).all():
        account_counts[uid] = int(n)

    rows: list[dict[str, Any]] = []
    for user in people:
        assignment = open_assignments.get(user.id)
        computer = None
        asset = None
        if assignment is not None:
            asset = assets_by_id.get(assignment.asset_id)
            computer = computers_by_asset.get(assignment.asset_id)
        other_assets = 0
        if assignment is not None:
            other_assets = sum(
                1
                for a_uid, a_row in open_assignments.items()
                if a_uid == user.id and a_row.asset_id != assignment.asset_id
            )
        rows.append(
            {
                "user_id": user.id,
                "full_name": _full_name(user),
                "email": user.email,
                "designation": user.designation,
                "department": _dept_name(user),
                "team": user.team.name if user.team else None,
                "employment_status": _employment_status(user),
                "is_active": user.is_active,
                "has_protrack_login": bool(user.is_active and not user.is_archived),
                "assigned_computer_id": computer.id if computer else None,
                "assigned_computer_name": computer.computer_name if computer else None,
                "assigned_asset_number": asset.asset_number if asset else None,
                "computer_status": asset.status if asset else None,
                "other_assigned_assets": other_assets,
                "it_account_count": account_counts.get(user.id, 0),
            }
        )

    # Optional search by computer/asset after enrichment
    if search:
        q = search.strip().lower()
        rows = [
            r
            for r in rows
            if q in (r["full_name"] or "").lower()
            or q in (r["email"] or "").lower()
            or q in (r["designation"] or "").lower()
            or q in (r["department"] or "").lower()
            or q in (r["team"] or "").lower()
            or q in (r["assigned_computer_name"] or "").lower()
            or q in (r["assigned_asset_number"] or "").lower()
        ]

    total = len(rows)
    return rows[skip : skip + limit], total


def get_it_person(db: Session, user_id: UUID) -> dict[str, Any] | None:
    user = db.scalar(
        select(User)
        .options(
            selectinload(User.team),
            selectinload(User.department),
            selectinload(User.org_department),
        )
        .where(User.id == user_id, User.is_deleted.is_(False))
    )
    if user is None:
        return None

    assignments = list(
        db.scalars(
            select(AssetAssignment)
            .where(AssetAssignment.assigned_to_user_id == user_id)
            .order_by(AssetAssignment.assigned_date.desc())
        ).all()
    )
    open_asg = next((a for a in assignments if a.returned_date is None), None)
    computer = None
    asset = None
    if open_asg:
        asset = db.get(Asset, open_asg.asset_id)
        computer = db.scalar(
            select(Computer).where(Computer.asset_id == open_asg.asset_id)
        )

    accounts = list(
        db.scalars(
            select(ITUserAccount).where(ITUserAccount.user_id == user_id)
        ).all()
    )
    open_assets = []
    for asg in assignments:
        if asg.returned_date is not None:
            continue
        a = db.get(Asset, asg.asset_id)
        if a is None or a.is_deleted:
            continue
        c = db.scalar(select(Computer).where(Computer.asset_id == a.id))
        open_assets.append(
            {
                "asset_id": a.id,
                "asset_number": a.asset_number,
                "status": a.status,
                "make": a.make,
                "model": a.model,
                "is_computer": c is not None,
                "computer_name": c.computer_name if c else None,
                "assigned_date": asg.assigned_date,
            }
        )

    return {
        "user_id": user.id,
        "full_name": _full_name(user),
        "email": user.email,
        "designation": user.designation,
        "department": _dept_name(user),
        "team": user.team.name if user.team else None,
        "employment_status": _employment_status(user),
        "is_active": user.is_active,
        "joining_date": user.joining_date,
        "leaving_date": user.leaving_date,
        "assigned_computer": (
            {
                "computer_id": computer.id,
                "computer_name": computer.computer_name,
                "asset_id": asset.id if asset else None,
                "asset_number": asset.asset_number if asset else None,
                "status": asset.status if asset else None,
                "os": computer.os,
                "mac_address": computer.mac_address,
                "assigned_date": open_asg.assigned_date if open_asg else None,
            }
            if computer and asset
            else None
        ),
        "assigned_assets": open_assets,
        "accounts": [
            {
                "id": acc.id,
                "account_type": acc.account_type,
                "username": acc.username,
                "display_name": acc.display_name,
                "status": acc.status,
                "credential_status": acc.credential_status,
            }
            for acc in accounts
        ],
        "assignment_history": [
            {
                "assignment_id": a.id,
                "asset_id": a.asset_id,
                "assigned_date": a.assigned_date,
                "returned_date": a.returned_date,
                "notes": a.notes,
            }
            for a in assignments
        ],
    }


def computer_availability_summary(db: Session) -> dict[str, int]:
    """Computer counts by operational status (via linked asset.status)."""
    rows = db.execute(
        select(Asset.status, func.count())
        .select_from(Computer)
        .join(Asset, Computer.asset_id == Asset.id)
        .where(Asset.is_deleted.is_(False))
        .group_by(Asset.status)
    ).all()
    by_status = {str(status): int(n) for status, n in rows}
    total = sum(by_status.values())
    assigned = by_status.get("assigned", 0)
    available = by_status.get("available", 0)
    maintenance = by_status.get("maintenance", 0)
    reserved = by_status.get("awaiting_return", 0)  # closest existing bucket
    retired = by_status.get("retired", 0)
    disposed = by_status.get("disposed", 0)
    # Open = Available + no open assignment (should match available if assign rule holds)
    open_count = available
    return {
        "total_computers": total,
        "assigned_computers": assigned,
        "open_computers": open_count,
        "available_computers": available,
        "reserved_computers": reserved,
        "maintenance_computers": maintenance,
        "retired_computers": retired,
        "disposed_computers": disposed,
    }


def count_active_employees_without_computer(db: Session) -> int:
    active_ids = set(
        db.scalars(
            select(User.id).where(
                User.is_deleted.is_(False),
                User.is_active.is_(True),
                User.is_archived.is_(False),
            )
        ).all()
    )
    assigned_user_ids = set()
    for asg in db.scalars(
        select(AssetAssignment).where(AssetAssignment.returned_date.is_(None))
    ).all():
        # Only count computer assets
        comp = db.scalar(select(Computer).where(Computer.asset_id == asg.asset_id))
        if comp is not None:
            assigned_user_ids.add(asg.assigned_to_user_id)
    return len(active_ids - assigned_user_ids)
