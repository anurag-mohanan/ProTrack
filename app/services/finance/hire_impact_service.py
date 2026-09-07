"""Finance view of a hiring decision's IT footprint (Connected ProTrack, Wave 5).

Reads IT Operations as the source of truth for computers, software requirements
and license pools. Costs are reported **only** where a cost is actually recorded
against a pool or asset — a missing cost stays missing rather than being guessed.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.it_operations import (
    Asset,
    Computer,
    EmployeeSoftwareRequirement,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import TeamMember
from app.services.resource_it_gap_service import get_computer_availability

# Recorded pool cost is treated as an annual subscription charge only for these
# license types; anything else reports a term cost with no monthly split.
ANNUALIZED_LICENSE_TYPES = frozenset({"subscription"})

ZERO = Decimal("0")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _requirement_user_ids(db: Session, team_id: UUID | None) -> set[UUID] | None:
    if team_id is None:
        return None
    return set(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id)).all()
    )


def _required_software(db: Session, team_id: UUID | None) -> list[tuple[UUID, str]]:
    """Distinct software titles that existing people are required to have."""
    stmt = (
        select(EmployeeSoftwareRequirement.software_id, SoftwareCatalog.name)
        .join(
            SoftwareCatalog,
            SoftwareCatalog.id == EmployeeSoftwareRequirement.software_id,
        )
        .where(EmployeeSoftwareRequirement.requirement_level == "required")
    )
    scoped = _requirement_user_ids(db, team_id)
    if scoped is not None:
        if not scoped:
            return []
        stmt = stmt.where(EmployeeSoftwareRequirement.user_id.in_(scoped))
    seen: dict[UUID, str] = {}
    for software_id, name in db.execute(stmt).all():
        seen.setdefault(software_id, name)
    return sorted(seen.items(), key=lambda item: item[1] or "")


def _pool_cost_per_seat(pool: SoftwareLicensePool) -> Decimal | None:
    seats = int(pool.seat_count or 0)
    if pool.cost is None or seats <= 0:
        return None
    return Decimal(pool.cost) / Decimal(seats)


def _cheapest_seat_cost(
    pools: list[SoftwareLicensePool],
) -> tuple[Decimal | None, str | None, bool]:
    """Lowest recorded per-seat cost for a software title.

    Returns (per_seat_cost, currency_code, is_annualized). All three are None /
    False when no pool for the title records a cost.
    """
    best: tuple[Decimal, str | None, bool] | None = None
    for pool in pools:
        per_seat = _pool_cost_per_seat(pool)
        if per_seat is None:
            continue
        annualized = (pool.license_type or "").strip().lower() in ANNUALIZED_LICENSE_TYPES
        candidate = (per_seat, pool.currency_code, annualized)
        if best is None or per_seat < best[0]:
            best = candidate
    if best is None:
        return None, None, False
    return best


def _average_computer_cost(db: Session) -> tuple[Decimal | None, int]:
    """Mean recorded purchase cost across computer assets that have one."""
    rows = db.scalars(
        select(Asset.purchase_cost)
        .join(Computer, Computer.asset_id == Asset.id)
        .where(Asset.is_deleted.is_(False), Asset.purchase_cost.is_not(None))
    ).all()
    costs = [Decimal(value) for value in rows if value is not None]
    if not costs:
        return None, 0
    return sum(costs, ZERO) / Decimal(len(costs)), len(costs)


def estimate_hire_impact(
    db: Session,
    *,
    headcount: int,
    team_id: UUID | None = None,
) -> dict:
    """IT + cost footprint of adding ``headcount`` people."""
    headcount = max(0, int(headcount or 0))

    availability = get_computer_availability(db)
    spare = int(availability["spare_computers"])
    required_computers = headcount  # 1:1 — no per-role computer rule exists yet
    computers_to_procure = max(0, required_computers - spare)

    pools_by_software: dict[UUID, list[SoftwareLicensePool]] = {}
    for pool in db.scalars(select(SoftwareLicensePool)).all():
        pools_by_software.setdefault(pool.software_id, []).append(pool)

    software_rows: list[dict] = []
    total_seats = 0
    license_term_cost = ZERO
    license_monthly_cost = ZERO
    currencies: set[str] = set()
    titles_without_cost = 0

    for software_id, name in _required_software(db, team_id):
        pools = pools_by_software.get(software_id, [])
        per_seat, currency, annualized = _cheapest_seat_cost(pools)
        free_seats = sum(
            max(0, int(pool.seat_count or 0)) for pool in pools
        )  # pool capacity, not availability — seats to buy are computed below
        seats_needed = headcount
        total_seats += seats_needed

        row: dict = {
            "software_id": software_id,
            "software_name": name,
            "seats_needed": seats_needed,
            "pool_seat_capacity": free_seats,
            "has_pool": bool(pools),
            "cost_per_seat": None,
            "currency_code": currency,
            "estimated_cost": None,
            "estimated_monthly_cost": None,
            "cost_basis": "not_recorded",
        }
        if per_seat is None:
            titles_without_cost += 1
        else:
            extended = per_seat * Decimal(seats_needed)
            license_term_cost += extended
            row["cost_per_seat"] = _quantize(per_seat)
            row["estimated_cost"] = _quantize(extended)
            row["cost_basis"] = "annual_subscription" if annualized else "recorded_term"
            if annualized:
                monthly = extended / Decimal(12)
                license_monthly_cost += monthly
                row["estimated_monthly_cost"] = _quantize(monthly)
            if currency:
                currencies.add(currency)
        software_rows.append(row)

    avg_computer_cost, computer_cost_sample = _average_computer_cost(db)
    hardware_cost = (
        _quantize(avg_computer_cost * Decimal(computers_to_procure))
        if avg_computer_cost is not None
        else None
    )

    assumptions: list[str] = []
    if headcount:
        assumptions.append("One computer per hire — no per-role hardware rule is defined.")
        assumptions.append(
            "License seats assume every new hire needs each software title that "
            "existing people in scope are required to have."
        )
    if computer_cost_sample:
        assumptions.append(
            f"Hardware cost uses the average recorded purchase cost of "
            f"{computer_cost_sample} computer assets."
        )
    if license_monthly_cost > ZERO:
        assumptions.append(
            "Monthly license cost divides recorded subscription pool cost by 12."
        )

    warnings: list[str] = []
    if titles_without_cost:
        warnings.append(
            f"{titles_without_cost} required software titles have no cost recorded "
            "on any license pool — excluded from the estimate."
        )
    if avg_computer_cost is None and computers_to_procure:
        warnings.append(
            "No computer asset has a recorded purchase cost — hardware cost is unavailable."
        )
    if len(currencies) > 1:
        warnings.append(
            "License pools use mixed currencies — costs are summed without conversion."
        )

    currency_code = next(iter(currencies)) if len(currencies) == 1 else None

    return {
        "headcount": headcount,
        "team_id": team_id,
        "required_computers": required_computers,
        "spare_computers": spare,
        "computers_to_procure": computers_to_procure,
        "required_license_seats": total_seats,
        "software": software_rows,
        "estimated_license_cost": _quantize(license_term_cost) if license_term_cost else None,
        "estimated_monthly_license_cost": (
            _quantize(license_monthly_cost) if license_monthly_cost else None
        ),
        "estimated_hardware_cost": hardware_cost,
        "currency_code": currency_code,
        "assumptions": assumptions,
        "warnings": warnings,
    }


__all__ = ["estimate_hire_impact"]
