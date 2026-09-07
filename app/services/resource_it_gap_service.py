"""Resource Planning ← IT readiness reads (Connected ProTrack, Wave 4).

Reads the IT Operations models as the single source of truth for computers and
software licensing. Deliberately owns no tables and writes nothing — Resource
Planning only consumes what IT already maintains.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.it_operations import (
    Asset,
    AssetAssignment,
    Computer,
    EmployeeSoftwareRequirement,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Team, TeamMember, User
from app.services.it_software_service import available_seats

# License types where a seat is shared over time rather than bound to a person.
FLOATING_LICENSE_TYPES = frozenset({"floating", "concurrent", "network"})

EXPIRING_SOON_DAYS = 30


def _full_name(user: User) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or "")


def _active_user_stmt():
    return select(User).where(
        User.is_deleted.is_(False),
        User.is_active.is_(True),
        User.is_archived.is_(False),
    )


def _team_user_ids(db: Session, team_id: UUID) -> set[UUID]:
    return set(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)).all()
    )


def _scoped_users(db: Session, team_id: UUID | None) -> list[User]:
    users = list(db.scalars(_active_user_stmt()).all())
    if team_id is None:
        return sorted(users, key=_full_name)
    member_ids = _team_user_ids(db, team_id)
    return sorted((u for u in users if u.id in member_ids), key=_full_name)


def _computer_assignment_map(db: Session, on_date: date) -> dict[UUID, dict]:
    """user_id → assigned computer, for assignments open on ``on_date``."""
    rows = db.execute(
        select(AssetAssignment, Computer, Asset)
        .join(Computer, Computer.asset_id == AssetAssignment.asset_id)
        .join(Asset, Asset.id == AssetAssignment.asset_id)
        .where(
            Asset.is_deleted.is_(False),
            AssetAssignment.assigned_date <= on_date,
            or_(
                AssetAssignment.returned_date.is_(None),
                AssetAssignment.returned_date > on_date,
            ),
        )
    ).all()
    assigned: dict[UUID, dict] = {}
    for assignment, computer, asset in rows:
        assigned.setdefault(
            assignment.assigned_to_user_id,
            {
                "computer_id": computer.id,
                "computer_name": computer.computer_name,
                "asset_id": asset.id,
                "asset_number": asset.asset_number,
                "asset_status": asset.status,
                "assigned_date": assignment.assigned_date,
            },
        )
    return assigned


def get_computer_availability(db: Session, on_date: date | None = None) -> dict:
    """Free vs assigned computers, derived from Computer/Asset/AssetAssignment."""
    on_date = on_date or date.today()
    computers = db.execute(
        select(Computer, Asset)
        .join(Asset, Asset.id == Computer.asset_id)
        .where(Asset.is_deleted.is_(False))
    ).all()
    assigned_asset_ids = set(
        db.scalars(
            select(AssetAssignment.asset_id).where(
                AssetAssignment.assigned_date <= on_date,
                or_(
                    AssetAssignment.returned_date.is_(None),
                    AssetAssignment.returned_date > on_date,
                ),
            )
        ).all()
    )

    total = 0
    assigned = 0
    spare: list[dict] = []
    unavailable = 0
    for computer, asset in computers:
        total += 1
        if asset.id in assigned_asset_ids:
            assigned += 1
        elif asset.status in {"retired", "disposed", "maintenance", "awaiting_return"}:
            unavailable += 1
        else:
            spare.append(
                {
                    "computer_id": computer.id,
                    "computer_name": computer.computer_name,
                    "asset_number": asset.asset_number,
                    "status": asset.status,
                }
            )
    return {
        "on_date": on_date,
        "total_computers": total,
        "assigned_computers": assigned,
        "spare_computers": len(spare),
        "unavailable_computers": unavailable,
        "spare": spare,
    }


def get_software_requirements(
    db: Session, user_ids: list[UUID] | None = None, *, on_date: date | None = None
) -> dict[UUID, list[dict]]:
    """user_id → active software requirements, joined to catalog names."""
    on_date = on_date or date.today()
    stmt = (
        select(EmployeeSoftwareRequirement, SoftwareCatalog)
        .join(
            SoftwareCatalog,
            SoftwareCatalog.id == EmployeeSoftwareRequirement.software_id,
        )
        .where(
            or_(
                EmployeeSoftwareRequirement.effective_from.is_(None),
                EmployeeSoftwareRequirement.effective_from <= on_date,
            ),
            or_(
                EmployeeSoftwareRequirement.effective_to.is_(None),
                EmployeeSoftwareRequirement.effective_to >= on_date,
            ),
        )
    )
    if user_ids is not None:
        if not user_ids:
            return {}
        stmt = stmt.where(EmployeeSoftwareRequirement.user_id.in_(user_ids))

    result: dict[UUID, list[dict]] = {}
    for requirement, software in db.execute(stmt).all():
        result.setdefault(requirement.user_id, []).append(
            {
                "requirement_id": requirement.id,
                "software_id": requirement.software_id,
                "software_name": software.name,
                "requirement_level": requirement.requirement_level,
                "version": requirement.version,
            }
        )
    return result


def get_license_availability(db: Session) -> list[dict]:
    """Seat math per license pool, grouped by software."""
    today = date.today()
    expiring_before = today + timedelta(days=EXPIRING_SOON_DAYS)
    rows = db.execute(
        select(SoftwareLicensePool, SoftwareCatalog)
        .join(SoftwareCatalog, SoftwareCatalog.id == SoftwareLicensePool.software_id)
        .order_by(SoftwareCatalog.name)
    ).all()

    pools: list[dict] = []
    for pool, software in rows:
        free = available_seats(db, pool)
        seats = int(pool.seat_count or 0)
        license_type = (pool.license_type or "").strip().lower()
        pools.append(
            {
                "pool_id": pool.id,
                "software_id": pool.software_id,
                "software_name": software.name,
                "license_type": pool.license_type,
                "is_floating": license_type in FLOATING_LICENSE_TYPES,
                "seat_count": seats,
                "assigned_seats": seats - free,
                "available_seats": free,
                "expiry_date": pool.expiry_date,
                "is_expired": pool.expiry_date is not None and pool.expiry_date < today,
                "expires_soon": (
                    pool.expiry_date is not None
                    and today <= pool.expiry_date <= expiring_before
                ),
            }
        )
    return pools


def _seats_by_software(pools: list[dict]) -> dict[UUID, dict]:
    """Collapse pools to per-software totals so demand can be compared to supply."""
    totals: dict[UUID, dict] = {}
    for pool in pools:
        entry = totals.setdefault(
            pool["software_id"],
            {
                "software_id": pool["software_id"],
                "software_name": pool["software_name"],
                "seat_count": 0,
                "assigned_seats": 0,
                "available_seats": 0,
                "is_floating": False,
                "pool_count": 0,
                "expired_pools": 0,
                "expiring_pools": 0,
            },
        )
        entry["seat_count"] += pool["seat_count"]
        entry["assigned_seats"] += pool["assigned_seats"]
        entry["available_seats"] += pool["available_seats"]
        entry["is_floating"] = entry["is_floating"] or pool["is_floating"]
        entry["pool_count"] += 1
        entry["expired_pools"] += 1 if pool["is_expired"] else 0
        entry["expiring_pools"] += 1 if pool["expires_soon"] else 0
    return totals


def _licensed_software_by_user(db: Session) -> dict[UUID, set[UUID]]:
    rows = db.execute(
        select(SoftwareAssignment.user_id, SoftwareLicensePool.software_id)
        .join(
            SoftwareLicensePool,
            SoftwareLicensePool.id == SoftwareAssignment.license_pool_id,
        )
        .where(
            SoftwareAssignment.released_date.is_(None),
            SoftwareAssignment.user_id.is_not(None),
        )
    ).all()
    licensed: dict[UUID, set[UUID]] = {}
    for user_id, software_id in rows:
        licensed.setdefault(user_id, set()).add(software_id)
    return licensed


def get_resource_gaps(
    db: Session,
    *,
    team_id: UUID | None = None,
    on_date: date | None = None,
) -> dict:
    """IT readiness gaps for the planned workforce — read-only, no writes."""
    on_date = on_date or date.today()
    users = _scoped_users(db, team_id)
    user_ids = [user.id for user in users]

    computers = get_computer_availability(db, on_date)
    assigned_computers = _computer_assignment_map(db, on_date)
    requirements = get_software_requirements(db, user_ids, on_date=on_date)
    licensed = _licensed_software_by_user(db)
    pools = get_license_availability(db)
    software_totals = _seats_by_software(pools)

    users_without_computer: list[dict] = []
    users_missing_licenses: list[dict] = []
    # Demand per software: how many scoped people require it but hold no seat.
    unmet_demand: dict[UUID, int] = {}
    required_headcount: dict[UUID, int] = {}

    for user in users:
        if user.id not in assigned_computers:
            users_without_computer.append(
                {"user_id": user.id, "full_name": _full_name(user), "email": user.email}
            )
        held = licensed.get(user.id, set())
        missing = [
            row
            for row in requirements.get(user.id, [])
            if row["requirement_level"] == "required" and row["software_id"] not in held
        ]
        for row in requirements.get(user.id, []):
            if row["requirement_level"] == "required":
                required_headcount[row["software_id"]] = (
                    required_headcount.get(row["software_id"], 0) + 1
                )
        for row in missing:
            unmet_demand[row["software_id"]] = unmet_demand.get(row["software_id"], 0) + 1
        if missing:
            users_missing_licenses.append(
                {
                    "user_id": user.id,
                    "full_name": _full_name(user),
                    "email": user.email,
                    "missing": [
                        {
                            "software_id": row["software_id"],
                            "software_name": row["software_name"],
                        }
                        for row in missing
                    ],
                }
            )

    license_demand: list[dict] = []
    for software_id, headcount in sorted(
        required_headcount.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        totals = software_totals.get(software_id)
        unmet = unmet_demand.get(software_id, 0)
        free = int(totals["available_seats"]) if totals else 0
        # TODO (Wave 3 shifts): when shift schedules exist, estimate floating /
        # concurrent peak from overlapping shift windows instead of headcount.
        license_demand.append(
            {
                "software_id": software_id,
                "software_name": (
                    totals["software_name"]
                    if totals
                    else _software_name(db, software_id)
                ),
                "required_headcount": headcount,
                "unmet_headcount": unmet,
                "seat_count": int(totals["seat_count"]) if totals else 0,
                "assigned_seats": int(totals["assigned_seats"]) if totals else 0,
                "available_seats": free,
                "is_floating": bool(totals["is_floating"]) if totals else False,
                "peak_estimate": headcount,
                "seat_shortfall": max(0, unmet - free),
                "has_pool": totals is not None,
            }
        )

    oversubscribed = [
        row
        for row in license_demand
        if row["has_pool"] and row["required_headcount"] > row["seat_count"]
    ]
    no_pool = [row for row in license_demand if not row["has_pool"]]
    expiring_pools = [row for row in pools if row["expires_soon"]]
    expired_pools = [row for row in pools if row["is_expired"]]

    alerts: list[dict] = []
    if users_without_computer:
        alerts.append(
            {
                "severity": "error",
                "code": "users_without_computer",
                "message": (
                    f"{len(users_without_computer)} active people have no computer "
                    f"assigned on {on_date.isoformat()}."
                ),
                "count": len(users_without_computer),
            }
        )
    if users_missing_licenses:
        alerts.append(
            {
                "severity": "error",
                "code": "users_missing_licenses",
                "message": (
                    f"{len(users_missing_licenses)} people are missing a required "
                    "software license."
                ),
                "count": len(users_missing_licenses),
            }
        )
    if oversubscribed:
        alerts.append(
            {
                "severity": "warning",
                "code": "pools_oversubscribed",
                "message": (
                    f"{len(oversubscribed)} software titles need more seats than the "
                    "license pools hold."
                ),
                "count": len(oversubscribed),
            }
        )
    if no_pool:
        alerts.append(
            {
                "severity": "warning",
                "code": "software_without_pool",
                "message": (
                    f"{len(no_pool)} required software titles have no license pool "
                    "recorded in IT."
                ),
                "count": len(no_pool),
            }
        )
    if expired_pools:
        alerts.append(
            {
                "severity": "error",
                "code": "licenses_expired",
                "message": f"{len(expired_pools)} license pools have already expired.",
                "count": len(expired_pools),
            }
        )
    if expiring_pools:
        alerts.append(
            {
                "severity": "warning",
                "code": "licenses_expiring",
                "message": (
                    f"{len(expiring_pools)} license pools expire within "
                    f"{EXPIRING_SOON_DAYS} days."
                ),
                "count": len(expiring_pools),
            }
        )
    if not alerts:
        alerts.append(
            {
                "severity": "success",
                "code": "ready",
                "message": "No IT readiness gaps for the selected scope.",
                "count": 0,
            }
        )

    return {
        "on_date": on_date,
        "team_id": team_id,
        "headcount": len(users),
        "users_without_computer": users_without_computer,
        "users_missing_licenses": users_missing_licenses,
        "license_demand": license_demand,
        "oversubscribed_software": oversubscribed,
        "software_without_pool": no_pool,
        "expiring_pools": expiring_pools,
        "expired_pools": expired_pools,
        "spare_computers": computers["spare_computers"],
        "total_computers": computers["total_computers"],
        "alerts": alerts,
    }


def _software_name(db: Session, software_id: UUID) -> str | None:
    software = db.get(SoftwareCatalog, software_id)
    return software.name if software else None


def get_resource_matrix(
    db: Session,
    *,
    from_date: date,
    to_date: date,
    team_id: UUID | None = None,
) -> dict:
    """People × (computer assigned?, license compliance) over a date window.

    Computer readiness is evaluated on ``to_date`` — the end of the planning
    window is what matters for "can this person start work by then".
    """
    if to_date < from_date:
        from_date, to_date = to_date, from_date

    users = _scoped_users(db, team_id)
    user_ids = [user.id for user in users]
    assigned_computers = _computer_assignment_map(db, to_date)
    requirements = get_software_requirements(db, user_ids, on_date=to_date)
    licensed = _licensed_software_by_user(db)
    team_names = _team_name_map(db, user_ids)

    rows: list[dict] = []
    ready = 0
    for user in users:
        computer = assigned_computers.get(user.id)
        reqs = requirements.get(user.id, [])
        held = licensed.get(user.id, set())
        required = [row for row in reqs if row["requirement_level"] == "required"]
        missing = [row for row in required if row["software_id"] not in held]
        is_ready = computer is not None and not missing
        ready += 1 if is_ready else 0
        rows.append(
            {
                "user_id": user.id,
                "full_name": _full_name(user),
                "email": user.email,
                "team_name": team_names.get(user.id),
                "has_computer": computer is not None,
                "computer_name": computer["computer_name"] if computer else None,
                "asset_number": computer["asset_number"] if computer else None,
                "required_software_count": len(required),
                "licensed_software_count": len(required) - len(missing),
                "missing_software": [row["software_name"] for row in missing],
                "is_compliant": not missing,
                "is_ready": is_ready,
            }
        )

    return {
        "from_date": from_date,
        "to_date": to_date,
        "team_id": team_id,
        "headcount": len(rows),
        "ready_count": ready,
        "not_ready_count": len(rows) - ready,
        "rows": rows,
    }


def _team_name_map(db: Session, user_ids: list[UUID]) -> dict[UUID, str]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(TeamMember.user_id, Team.name)
        .join(Team, Team.id == TeamMember.team_id)
        .where(TeamMember.user_id.in_(user_ids))
        .order_by(TeamMember.is_primary.desc())
    ).all()
    names: dict[UUID, str] = {}
    for user_id, name in rows:
        names.setdefault(user_id, name)
    return names


def _employee_shift(db: Session, user_id: UUID) -> dict | None:
    """Shift lookup is optional — degrade gracefully if shifts aren't seeded."""
    try:
        from datetime import date

        from app.services.resource_shift_service import get_employee_shift
    except Exception:
        return None
    try:
        shift = get_employee_shift(db, user_id, date.today())
    except Exception:
        return None
    if shift is None:
        return None
    if isinstance(shift, dict):
        return shift
    return {
        "id": str(getattr(shift, "id", "") or "") or None,
        "name": getattr(shift, "name", None),
        "code": getattr(shift, "code", None),
        "start_time": str(getattr(shift, "start_time", "") or "") or None,
        "end_time": str(getattr(shift, "end_time", "") or "") or None,
    }


def get_employee_it_snapshot(db: Session, user_id: UUID) -> dict:
    """Read-only aggregate: assigned computer, software, shift. Writes nothing."""
    on_date = date.today()
    computer = _computer_assignment_map(db, on_date).get(user_id)

    software_rows = db.execute(
        select(SoftwareAssignment, SoftwareLicensePool, SoftwareCatalog)
        .join(
            SoftwareLicensePool,
            SoftwareLicensePool.id == SoftwareAssignment.license_pool_id,
        )
        .join(SoftwareCatalog, SoftwareCatalog.id == SoftwareLicensePool.software_id)
        .where(
            SoftwareAssignment.user_id == user_id,
            SoftwareAssignment.released_date.is_(None),
        )
        .order_by(SoftwareCatalog.name)
    ).all()

    requirements = get_software_requirements(db, [user_id], on_date=on_date).get(user_id, [])
    held = {pool.software_id for _, pool, _ in software_rows}
    missing = [
        row["software_name"]
        for row in requirements
        if row["requirement_level"] == "required" and row["software_id"] not in held
    ]

    return {
        "user_id": user_id,
        "computer": computer,
        "software": [
            {
                "assignment_id": assignment.id,
                "license_pool_id": pool.id,
                "software_id": software.id,
                "software_name": software.name,
                "license_type": pool.license_type,
                "assigned_date": assignment.assigned_date,
            }
            for assignment, pool, software in software_rows
        ],
        "required_software_count": sum(
            1 for row in requirements if row["requirement_level"] == "required"
        ),
        "missing_software": missing,
        "is_compliant": not missing,
        "shift": _employee_shift(db, user_id),
    }


def gap_counts_for_dashboard(db: Session) -> dict[str, int]:
    """Compact counters for the IT dashboard summary card."""
    gaps = get_resource_gaps(db)
    return {
        "gap_users_without_computer": len(gaps["users_without_computer"]),
        "gap_users_missing_licenses": len(gaps["users_missing_licenses"]),
        "gap_oversubscribed_software": len(gaps["oversubscribed_software"]),
        "gap_software_without_pool": len(gaps["software_without_pool"]),
        "gap_spare_computers": int(gaps["spare_computers"]),
    }


__all__ = [
    "gap_counts_for_dashboard",
    "get_computer_availability",
    "get_employee_it_snapshot",
    "get_license_availability",
    "get_resource_gaps",
    "get_resource_matrix",
    "get_software_requirements",
]
