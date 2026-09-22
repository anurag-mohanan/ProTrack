"""Deterministic computer ranking, duplicate checks, and assignment previews.

Suggestions are explainable and based on live ProTrack inventory — never AI.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.it_operations import (
    CURRENT_INVENTORY_STATUSES,
    Asset,
    AssetAssignment,
    Computer,
    EmployeeSoftwareRequirement,
    IPAddress,
    SoftwareInstallation,
)
from app.models.models import User
from app.services import it_asset_service
from app.services import it_computer_suggest_service as suggest
from app.services import resource_it_gap_service
from app.services import resource_shift_service


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def _asset_search_href(asset_number: str | None) -> str | None:
    if not asset_number:
        return None
    return f"/it/assets?search={asset_number}"


def check_duplicates(
    db: Session,
    *,
    asset_number: str | None = None,
    computer_name: str | None = None,
    serial_number: str | None = None,
    service_tag: str | None = None,
    mac_address: str | None = None,
    ip_address: str | None = None,
    exclude_asset_id: UUID | None = None,
) -> dict:
    """Preview uniqueness conflicts before save. Does not allocate."""
    conflicts: list[dict] = []

    number = (asset_number or "").strip()
    if number and it_asset_service.asset_number_is_reserved(
        db, number, exclude_asset_id=exclude_asset_id
    ):
        conflicts.append(
            {
                "field": "asset_number",
                "value": number,
                "message": f"Asset number {number} is already used or historically reserved.",
            }
        )

    name = (computer_name or "").strip()
    exclude_computer_id = None
    if exclude_asset_id is not None:
        existing = db.scalar(select(Computer).where(Computer.asset_id == exclude_asset_id))
        if existing is not None:
            exclude_computer_id = existing.id
    if name and suggest.computer_name_is_taken(
        db, name, exclude_computer_id=exclude_computer_id
    ):
        owner = db.scalar(
            select(Computer)
            .options(selectinload(Computer.asset))
            .where(func.lower(Computer.computer_name) == name.lower())
        )
        asset_no = owner.asset.asset_number if owner and owner.asset else None
        conflicts.append(
            {
                "field": "computer_name",
                "value": name,
                "asset_number": asset_no,
                "href": _asset_search_href(asset_no),
                "message": (
                    f"Computer name {name} is already in use"
                    + (f" ({asset_no})." if asset_no else ".")
                ),
            }
        )

    serial = (serial_number or "").strip()
    if serial:
        other = it_asset_service._serial_conflict(db, serial, exclude_asset_id=exclude_asset_id)
        if other is not None:
            conflicts.append(
                {
                    "field": "serial_number",
                    "value": serial,
                    "asset_number": other.asset_number,
                    "href": _asset_search_href(other.asset_number),
                    "message": f"Serial number {serial} is already assigned to {other.asset_number}.",
                }
            )

    tag = (service_tag or "").strip()
    if tag:
        stmt = select(Asset).where(
            Asset.is_deleted.is_(False),
            func.lower(Asset.service_tag) == tag.lower(),
        )
        if exclude_asset_id is not None:
            stmt = stmt.where(Asset.id != exclude_asset_id)
        other = db.scalar(stmt.limit(1))
        if other is not None:
            conflicts.append(
                {
                    "field": "service_tag",
                    "value": tag,
                    "asset_number": other.asset_number,
                    "href": _asset_search_href(other.asset_number),
                    "message": f"Service tag {tag} is already assigned to {other.asset_number}.",
                }
            )

    mac = suggest.normalize_mac(mac_address)
    if mac:
        owner = suggest.mac_is_taken(db, mac, exclude_computer_id=exclude_computer_id)
        if owner is not None:
            asset_no = owner.asset.asset_number if owner.asset else None
            conflicts.append(
                {
                    "field": "mac_address",
                    "value": mac,
                    "asset_number": asset_no,
                    "computer_name": owner.computer_name,
                    "href": _asset_search_href(asset_no),
                    "message": f"MAC address {mac} is already assigned to {owner.computer_name}.",
                }
            )

    addr = (ip_address or "").strip()
    if addr:
        ip = db.scalar(select(IPAddress).where(IPAddress.address == addr))
        if ip is not None and ip.status != "available":
            from app.models.it_operations import IPAssignmentHistory

            open_hist = db.scalar(
                select(IPAssignmentHistory).where(
                    IPAssignmentHistory.ip_address_id == ip.id,
                    IPAssignmentHistory.released_date.is_(None),
                )
            )
            asset_no = None
            computer_name = None
            if open_hist and open_hist.assigned_to_asset_id:
                asset = db.get(Asset, open_hist.assigned_to_asset_id)
                asset_no = asset.asset_number if asset else None
                computer = db.scalar(
                    select(Computer).where(Computer.asset_id == open_hist.assigned_to_asset_id)
                )
                computer_name = computer.computer_name if computer else None
            conflicts.append(
                {
                    "field": "ip_address",
                    "value": addr,
                    "asset_number": asset_no,
                    "computer_name": computer_name,
                    "href": _asset_search_href(asset_no),
                    "message": (
                        f"{addr} is already assigned"
                        + (
                            f" to {computer_name or asset_no}."
                            if (computer_name or asset_no)
                            else "."
                        )
                    ),
                }
            )

    return {"ok": len(conflicts) == 0, "conflicts": conflicts}


def assignment_preview(
    db: Session,
    *,
    asset_id: UUID,
    user_id: UUID | None = None,
    shift_id: UUID | None = None,
) -> dict:
    """Read-only checks before assigning an asset. Does not write."""
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        return {"ok": False, "checks": [{"code": "asset", "ok": False, "message": "Asset not found."}]}

    computer = getattr(asset, "computer", None)
    ip = suggest.current_ip_for_asset(db, asset.id)
    status = (asset.status or "").lower()
    checks: list[dict] = []

    available = status in {"available", "assigned"}
    checks.append(
        {
            "code": "status",
            "ok": available and status != "maintenance",
            "message": (
                f"Status: {status}"
                if available
                else f"Cannot assign an asset with status '{status}'."
            ),
        }
    )
    if computer is not None:
        checks.append(
            {
                "code": "ip",
                "ok": ip is not None,
                "message": (
                    f"IP {ip['address']} available on this computer."
                    if ip
                    else "Computer has no primary IP assigned."
                ),
            }
        )

    if user_id is not None:
        user = db.get(User, user_id)
        eligible = (
            user is not None
            and not getattr(user, "is_deleted", False)
            and bool(getattr(user, "is_active", True))
            and not bool(getattr(user, "is_archived", False))
        )
        checks.append(
            {
                "code": "user",
                "ok": eligible,
                "message": (
                    f"{_full_name(user)} is active."
                    if eligible
                    else "Selected person is missing, inactive, or archived."
                ),
                "team": user.team.name if user and getattr(user, "team", None) else None,
                "location": getattr(user, "location", None) or asset.location,
            }
        )
        shift = resource_shift_service.get_employee_shift(db, user_id, date.today()) if user else None
        checks.append(
            {
                "code": "shift",
                "ok": True,
                "message": (
                    f"Shift: {shift.name} ({shift.start_time}–{shift.end_time})"
                    if shift and getattr(shift, "start_time", None)
                    else (f"Shift: {shift.name}" if shift else "No shift assigned today in Resource Planning.")
                ),
                "shift_id": str(shift.id) if shift else None,
                "derived": True,
            }
        )

    open_rows = it_asset_service.list_open_assignments(db, asset.id)
    conflict_ok = True
    conflict_msg = "No conflicting assignment."
    if shift_id is None and open_rows:
        conflict_ok = False
        conflict_msg = "Asset already has an open assignment. Provide a shift slot for shared-desk use, or return the current user first."
    elif shift_id is not None:
        for row in open_rows:
            if row.shift_id == shift_id:
                conflict_ok = False
                conflict_msg = "This asset already has an open assignment for that shift."
                break
            if row.shift_id is None:
                conflict_ok = False
                conflict_msg = "A legacy assignment without a shift is still open."
                break
    checks.append({"code": "conflict", "ok": conflict_ok, "message": conflict_msg})

    return {
        "ok": all(row["ok"] for row in checks),
        "asset_number": asset.asset_number,
        "computer_name": computer.computer_name if computer else None,
        "status": status,
        "primary_ip": ip["address"] if ip else None,
        "mac_address": computer.mac_address if computer else None,
        "checks": checks,
    }


def recommend_computers(
    db: Session,
    *,
    user_id: UUID,
    limit: int = 8,
) -> dict:
    """Rank spare computers for an employee. Recommendation only — never auto-assigns."""
    user = db.get(User, user_id)
    if user is None or getattr(user, "is_deleted", False):
        return {"user_id": str(user_id), "recommendations": [], "message": "User not found."}

    on_date = date.today()
    availability = resource_it_gap_service.get_computer_availability(db, on_date)
    required_ids = set(
        db.scalars(
            select(EmployeeSoftwareRequirement.software_id).where(
                EmployeeSoftwareRequirement.user_id == user_id,
                EmployeeSoftwareRequirement.requirement_level == "required",
            )
        ).all()
    )
    shift = resource_shift_service.get_employee_shift(db, user_id, on_date)
    team_name = user.team.name if getattr(user, "team", None) else None
    user_location = (getattr(user, "location", None) or "").strip() or None

    ranked: list[dict] = []
    spare_ids = [row["computer_id"] for row in availability.get("spare") or []]
    if not spare_ids:
        return {
            "user_id": str(user_id),
            "user_name": _full_name(user),
            "shift": shift.name if shift else None,
            "team": team_name,
            "recommendations": [],
            "message": "No available computers in inventory.",
        }

    computers = list(
        db.scalars(
            select(Computer)
            .options(selectinload(Computer.asset), selectinload(Computer.interfaces))
            .where(Computer.id.in_(spare_ids))
        ).all()
    )
    for computer in computers:
        asset = computer.asset
        if asset is None or getattr(asset, "is_deleted", False):
            continue
        status = (asset.status or "").lower()
        if status not in CURRENT_INVENTORY_STATUSES:
            continue
        reasons: list[str] = []
        score = 0
        if status == "available":
            score += 100
            reasons.append("Available")
        elif status == "assigned":
            score += 20
            reasons.append("Already assigned (shared-desk candidate)")
        if status == "maintenance":
            score -= 80
            reasons.append("In maintenance")

        ip = suggest.current_ip_for_asset(db, asset.id)
        if ip:
            score += 25
            reasons.append(f"IP {ip['address']} available")
        else:
            reasons.append("No IP assigned")

        mac = computer.mac_address or next(
            (row.mac_address for row in (computer.interfaces or []) if row.mac_address),
            None,
        )
        if mac:
            score += 5
            reasons.append("MAC on file")

        loc = (asset.location or "").strip()
        if user_location and loc and user_location.lower() == loc.lower():
            score += 20
            reasons.append(f"Location matches ({loc})")
        elif loc:
            reasons.append(f"Location {loc}")

        installed = set(
            db.scalars(
                select(SoftwareInstallation.software_id).where(
                    SoftwareInstallation.computer_id == computer.id,
                    SoftwareInstallation.uninstalled_date.is_(None),
                )
            ).all()
        )
        matched = required_ids & installed
        if matched:
            score += 12 * len(matched)
            reasons.append(f"{len(matched)} required title(s) already installed")
        elif required_ids:
            reasons.append("Required software not yet installed")

        if shift:
            score += 8
            reasons.append(f"Employee shift {shift.name} — confirm shared-desk rules")

        ranked.append(
            {
                "computer_id": str(computer.id),
                "asset_id": str(asset.id),
                "computer_name": computer.computer_name,
                "asset_number": asset.asset_number,
                "make": asset.make,
                "model": asset.model,
                "status": status,
                "primary_ip": ip["address"] if ip else None,
                "mac_address": mac,
                "location": loc or None,
                "score": score,
                "reasons": reasons,
                "href": _asset_search_href(asset.asset_number),
            }
        )

    ranked.sort(key=lambda row: (-row["score"], row["computer_name"] or ""))
    top = ranked[: max(1, min(limit, 20))]
    return {
        "user_id": str(user_id),
        "user_name": _full_name(user),
        "team": team_name,
        "shift": shift.name if shift else None,
        "recommendations": top,
        "message": (
            f"Ranked {len(top)} available computer(s) from live inventory."
            if top
            else "No matching computers."
        ),
    }
