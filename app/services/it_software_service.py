"""IT software catalog, license pools, assignments, and employee requirements."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.it_operations import (
    LICENSE_TYPE_CODES,
    PURCHASED_BY_CODES,
    SOFTWARE_REQUIREMENT_LEVELS,
    Asset,
    Computer,
    EmployeeSoftwareRequirement,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Customer, User


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _active_assignment_filter():
    return SoftwareAssignment.released_date.is_(None)


def count_active_assignments(db: Session, pool_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(SoftwareAssignment)
            .where(
                SoftwareAssignment.license_pool_id == pool_id,
                _active_assignment_filter(),
            )
        )
        or 0
    )


def available_seats(db: Session, pool: SoftwareLicensePool) -> int:
    return max(0, int(pool.seat_count or 0) - count_active_assignments(db, pool.id))


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def list_software(
    db: Session,
    *,
    active_only: bool = False,
    search: str | None = None,
) -> list[SoftwareCatalog]:
    stmt = select(SoftwareCatalog).order_by(SoftwareCatalog.name)
    if active_only:
        stmt = stmt.where(SoftwareCatalog.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                SoftwareCatalog.name.ilike(term),
                SoftwareCatalog.vendor.ilike(term),
                SoftwareCatalog.code.ilike(term),
                SoftwareCatalog.category.ilike(term),
            )
        )
    return list(db.scalars(stmt).all())


def get_software(db: Session, software_id: UUID) -> SoftwareCatalog | None:
    return db.get(SoftwareCatalog, software_id)


def create_software(
    db: Session,
    *,
    name: str,
    vendor: str | None = None,
    version: str | None = None,
    edition: str | None = None,
    category: str | None = None,
    code: str | None = None,
    notes: str | None = None,
    is_active: bool = True,
) -> SoftwareCatalog:
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ProTrackValidationError("Software name is required.")
    existing = db.scalar(
        select(SoftwareCatalog).where(func.lower(SoftwareCatalog.name) == cleaned_name.lower())
    )
    if existing is not None:
        raise ProTrackValidationError("Software with this name already exists.")
    row = SoftwareCatalog(
        id=uuid4(),
        name=cleaned_name,
        vendor=_optional_str(vendor),
        version=_optional_str(version),
        edition=_optional_str(edition),
        category=_optional_str(category),
        code=_optional_str(code),
        notes=_optional_str(notes),
        is_active=bool(is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_software(
    db: Session,
    software: SoftwareCatalog,
    *,
    name: str | None = None,
    vendor: str | None = None,
    version: str | None = None,
    edition: str | None = None,
    category: str | None = None,
    code: str | None = None,
    notes: str | None = None,
    is_active: bool | None = None,
    fields_set: set[str] | None = None,
) -> SoftwareCatalog:
    touched = fields_set or set()
    if "name" in touched or (fields_set is None and name is not None):
        cleaned = (name or "").strip()
        if not cleaned:
            raise ProTrackValidationError("Software name is required.")
        clash = db.scalar(
            select(SoftwareCatalog).where(
                func.lower(SoftwareCatalog.name) == cleaned.lower(),
                SoftwareCatalog.id != software.id,
            )
        )
        if clash is not None:
            raise ProTrackValidationError("Software with this name already exists.")
        software.name = cleaned
    if "vendor" in touched or (fields_set is None and vendor is not None):
        software.vendor = _optional_str(vendor)
    if "version" in touched or (fields_set is None and version is not None):
        software.version = _optional_str(version)
    if "edition" in touched or (fields_set is None and edition is not None):
        software.edition = _optional_str(edition)
    if "category" in touched or (fields_set is None and category is not None):
        software.category = _optional_str(category)
    if "code" in touched or (fields_set is None and code is not None):
        software.code = _optional_str(code)
    if "notes" in touched or (fields_set is None and notes is not None):
        software.notes = _optional_str(notes)
    if "is_active" in touched or (fields_set is None and is_active is not None):
        software.is_active = bool(is_active)
    db.add(software)
    db.commit()
    db.refresh(software)
    return software


# ---------------------------------------------------------------------------
# License pools
# ---------------------------------------------------------------------------


def list_license_pools(
    db: Session,
    *,
    software_id: UUID | None = None,
    expiring_within_days: int | None = None,
    include_expired: bool = True,
) -> list[SoftwareLicensePool]:
    stmt = select(SoftwareLicensePool).order_by(
        SoftwareLicensePool.expiry_date.asc().nulls_last(),
        SoftwareLicensePool.created_at.desc(),
    )
    if software_id is not None:
        stmt = stmt.where(SoftwareLicensePool.software_id == software_id)
    today = date.today()
    if expiring_within_days is not None:
        until = today + timedelta(days=max(0, expiring_within_days))
        stmt = stmt.where(
            SoftwareLicensePool.expiry_date.is_not(None),
            SoftwareLicensePool.expiry_date >= today,
            SoftwareLicensePool.expiry_date <= until,
        )
    elif not include_expired:
        stmt = stmt.where(
            or_(
                SoftwareLicensePool.expiry_date.is_(None),
                SoftwareLicensePool.expiry_date >= today,
            )
        )
    return list(db.scalars(stmt).all())


def get_license_pool(db: Session, pool_id: UUID) -> SoftwareLicensePool | None:
    return db.get(SoftwareLicensePool, pool_id)


def create_license_pool(
    db: Session,
    *,
    software_id: UUID,
    seat_count: int = 1,
    purchased_by: str = "organization",
    owner_customer_id: UUID | None = None,
    license_type: str | None = None,
    cost: Decimal | None = None,
    currency_code: str | None = None,
    expiry_date: date | None = None,
    renewal_mode: str | None = None,
    notes: str | None = None,
) -> SoftwareLicensePool:
    software = get_software(db, software_id)
    if software is None:
        raise ProTrackValidationError("Software catalog entry not found.")
    if seat_count < 1:
        raise ProTrackValidationError("seat_count must be at least 1.")
    pb = (purchased_by or "organization").strip().lower()
    if pb not in PURCHASED_BY_CODES:
        raise ProTrackValidationError(f"Invalid purchased_by. Allowed: {sorted(PURCHASED_BY_CODES)}")
    if owner_customer_id is not None and db.get(Customer, owner_customer_id) is None:
        raise ProTrackValidationError("owner_customer_id not found.")
    lt = _optional_str(license_type)
    if lt is not None:
        lt = lt.lower()
        if lt not in LICENSE_TYPE_CODES:
            raise ProTrackValidationError(
                f"Invalid license_type. Allowed: {sorted(LICENSE_TYPE_CODES)}"
            )
    currency = _optional_str(currency_code)
    if currency is not None:
        currency = currency.upper()
        if len(currency) != 3:
            raise ProTrackValidationError("currency_code must be a 3-letter ISO code.")
    pool = SoftwareLicensePool(
        id=uuid4(),
        software_id=software_id,
        seat_count=int(seat_count),
        purchased_by=pb,
        owner_customer_id=owner_customer_id,
        license_type=lt,
        cost=cost,
        currency_code=currency,
        expiry_date=expiry_date,
        renewal_mode=_optional_str(renewal_mode),
        notes=_optional_str(notes),
    )
    db.add(pool)
    db.commit()
    db.refresh(pool)
    return pool


def update_license_pool(
    db: Session,
    pool: SoftwareLicensePool,
    *,
    seat_count: int | None = None,
    purchased_by: str | None = None,
    owner_customer_id: UUID | None = None,
    license_type: str | None = None,
    cost: Decimal | None = None,
    currency_code: str | None = None,
    expiry_date: date | None = None,
    renewal_mode: str | None = None,
    notes: str | None = None,
    fields_set: set[str] | None = None,
) -> SoftwareLicensePool:
    touched = fields_set or set()
    if "seat_count" in touched or (fields_set is None and seat_count is not None):
        if seat_count is None or seat_count < 1:
            raise ProTrackValidationError("seat_count must be at least 1.")
        active = count_active_assignments(db, pool.id)
        if seat_count < active:
            raise ProTrackValidationError(
                f"seat_count ({seat_count}) cannot be below active assignments ({active})."
            )
        pool.seat_count = int(seat_count)
    if "purchased_by" in touched or (fields_set is None and purchased_by is not None):
        pb = (purchased_by or pool.purchased_by).strip().lower()
        if pb not in PURCHASED_BY_CODES:
            raise ProTrackValidationError(
                f"Invalid purchased_by. Allowed: {sorted(PURCHASED_BY_CODES)}"
            )
        pool.purchased_by = pb
    if "owner_customer_id" in touched or (fields_set is None and owner_customer_id is not None):
        if owner_customer_id is not None and db.get(Customer, owner_customer_id) is None:
            raise ProTrackValidationError("owner_customer_id not found.")
        pool.owner_customer_id = owner_customer_id
    if "license_type" in touched or (fields_set is None and license_type is not None):
        lt = _optional_str(license_type)
        if lt is not None:
            lt = lt.lower()
            if lt not in LICENSE_TYPE_CODES:
                raise ProTrackValidationError(
                    f"Invalid license_type. Allowed: {sorted(LICENSE_TYPE_CODES)}"
                )
        pool.license_type = lt
    if "cost" in touched or (fields_set is None and cost is not None):
        pool.cost = cost
    if "currency_code" in touched or (fields_set is None and currency_code is not None):
        currency = _optional_str(currency_code)
        if currency is not None:
            currency = currency.upper()
            if len(currency) != 3:
                raise ProTrackValidationError("currency_code must be a 3-letter ISO code.")
        pool.currency_code = currency
    if "expiry_date" in touched or (fields_set is None and expiry_date is not None):
        pool.expiry_date = expiry_date
    if "renewal_mode" in touched or (fields_set is None and renewal_mode is not None):
        pool.renewal_mode = _optional_str(renewal_mode)
    if "notes" in touched or (fields_set is None and notes is not None):
        pool.notes = _optional_str(notes)
    db.add(pool)
    db.commit()
    db.refresh(pool)
    return pool


def expiry_summary(db: Session, *, within_days: int = 30) -> dict[str, list[dict] | int]:
    today = date.today()
    until = today + timedelta(days=max(0, within_days))
    pools = list(db.scalars(select(SoftwareLicensePool)).all())
    active: list[dict] = []
    expiring: list[dict] = []
    expired: list[dict] = []
    for pool in pools:
        soft = get_software(db, pool.software_id)
        row = {
            "id": pool.id,
            "software_id": pool.software_id,
            "software_name": soft.name if soft else None,
            "seat_count": pool.seat_count,
            "assigned_count": count_active_assignments(db, pool.id),
            "available_count": available_seats(db, pool),
            "expiry_date": pool.expiry_date,
            "license_type": pool.license_type,
            "renewal_mode": pool.renewal_mode,
        }
        if pool.expiry_date is None:
            active.append(row)
        elif pool.expiry_date < today:
            expired.append(row)
        elif pool.expiry_date <= until:
            expiring.append(row)
            active.append(row)
        else:
            active.append(row)
    return {
        "active_count": len(active),
        "expiring_30_count": len(expiring),
        "expired_count": len(expired),
        "active": active,
        "expiring_30": expiring,
        "expired": expired,
    }


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


def list_assignments(
    db: Session,
    *,
    license_pool_id: UUID | None = None,
    user_id: UUID | None = None,
    computer_id: UUID | None = None,
    asset_id: UUID | None = None,
    active_only: bool = True,
) -> list[SoftwareAssignment]:
    stmt = select(SoftwareAssignment).order_by(
        SoftwareAssignment.assigned_date.desc().nulls_last(),
        SoftwareAssignment.created_at.desc(),
    )
    if license_pool_id is not None:
        stmt = stmt.where(SoftwareAssignment.license_pool_id == license_pool_id)
    if user_id is not None:
        stmt = stmt.where(SoftwareAssignment.user_id == user_id)
    if computer_id is not None:
        stmt = stmt.where(SoftwareAssignment.computer_id == computer_id)
    if asset_id is not None:
        stmt = stmt.where(SoftwareAssignment.asset_id == asset_id)
    if active_only:
        stmt = stmt.where(_active_assignment_filter())
    return list(db.scalars(stmt).all())


def get_assignment(db: Session, assignment_id: UUID) -> SoftwareAssignment | None:
    return db.get(SoftwareAssignment, assignment_id)


def assign_license(
    db: Session,
    *,
    license_pool_id: UUID,
    user_id: UUID | None = None,
    computer_id: UUID | None = None,
    asset_id: UUID | None = None,
    assigned_date: date | None = None,
    notes: str | None = None,
    department: str | None = None,
) -> SoftwareAssignment:
    pool = get_license_pool(db, license_pool_id)
    if pool is None:
        raise ProTrackValidationError("License pool not found.")
    if user_id is None and computer_id is None and asset_id is None:
        raise ProTrackValidationError("Assign to a user, computer, and/or asset.")
    if user_id is not None:
        user = db.get(User, user_id)
        if user is None or user.is_deleted:
            raise ProTrackValidationError("User not found.")
    if computer_id is not None:
        computer = db.get(Computer, computer_id)
        if computer is None:
            raise ProTrackValidationError("Computer not found.")
        if asset_id is None:
            asset_id = computer.asset_id
    if asset_id is not None:
        asset = db.get(Asset, asset_id)
        if asset is None or asset.is_deleted:
            raise ProTrackValidationError("Asset not found.")
    if available_seats(db, pool) < 1:
        raise ProTrackValidationError("No available seats in this license pool.")

    # Prevent duplicate active assignment of same pool to same target
    dup_filters = [
        SoftwareAssignment.license_pool_id == license_pool_id,
        _active_assignment_filter(),
    ]
    target_filters = []
    if user_id is not None:
        target_filters.append(SoftwareAssignment.user_id == user_id)
    if computer_id is not None:
        target_filters.append(SoftwareAssignment.computer_id == computer_id)
    if asset_id is not None and computer_id is None:
        target_filters.append(SoftwareAssignment.asset_id == asset_id)
    if target_filters:
        existing = db.scalar(select(SoftwareAssignment).where(and_(*dup_filters, or_(*target_filters))))
        if existing is not None:
            raise ProTrackValidationError("An active assignment already exists for this target.")

    row = SoftwareAssignment(
        id=uuid4(),
        license_pool_id=license_pool_id,
        user_id=user_id,
        computer_id=computer_id,
        asset_id=asset_id,
        assigned_date=assigned_date or date.today(),
        notes=_optional_str(notes),
        department=_optional_str(department),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def unassign_license(
    db: Session,
    assignment: SoftwareAssignment,
    *,
    released_date: date | None = None,
) -> SoftwareAssignment:
    if assignment.released_date is not None:
        raise ProTrackValidationError("Assignment is already released.")
    assignment.released_date = released_date or date.today()
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


# ---------------------------------------------------------------------------
# Employee software requirements
# ---------------------------------------------------------------------------


def list_requirements(
    db: Session,
    *,
    user_id: UUID | None = None,
    software_id: UUID | None = None,
    active_on: date | None = None,
) -> list[EmployeeSoftwareRequirement]:
    stmt = select(EmployeeSoftwareRequirement).order_by(
        EmployeeSoftwareRequirement.user_id,
        EmployeeSoftwareRequirement.software_id,
    )
    if user_id is not None:
        stmt = stmt.where(EmployeeSoftwareRequirement.user_id == user_id)
    if software_id is not None:
        stmt = stmt.where(EmployeeSoftwareRequirement.software_id == software_id)
    if active_on is not None:
        stmt = stmt.where(
            or_(
                EmployeeSoftwareRequirement.effective_from.is_(None),
                EmployeeSoftwareRequirement.effective_from <= active_on,
            ),
            or_(
                EmployeeSoftwareRequirement.effective_to.is_(None),
                EmployeeSoftwareRequirement.effective_to >= active_on,
            ),
        )
    return list(db.scalars(stmt).all())


def get_requirement(db: Session, requirement_id: UUID) -> EmployeeSoftwareRequirement | None:
    return db.get(EmployeeSoftwareRequirement, requirement_id)


def create_requirement(
    db: Session,
    *,
    user_id: UUID,
    software_id: UUID,
    requirement_level: str = "required",
    version: str | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    reason: str | None = None,
    notes: str | None = None,
) -> EmployeeSoftwareRequirement:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("User not found.")
    if get_software(db, software_id) is None:
        raise ProTrackValidationError("Software catalog entry not found.")
    level = (requirement_level or "required").strip().lower()
    if level not in SOFTWARE_REQUIREMENT_LEVELS:
        raise ProTrackValidationError(
            f"Invalid requirement_level. Allowed: {sorted(SOFTWARE_REQUIREMENT_LEVELS)}"
        )
    if (
        effective_from is not None
        and effective_to is not None
        and effective_to < effective_from
    ):
        raise ProTrackValidationError("effective_to cannot be before effective_from.")
    row = EmployeeSoftwareRequirement(
        id=uuid4(),
        user_id=user_id,
        software_id=software_id,
        requirement_level=level,
        version=_optional_str(version),
        effective_from=effective_from,
        effective_to=effective_to,
        reason=_optional_str(reason),
        notes=_optional_str(notes),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_requirement(
    db: Session,
    requirement: EmployeeSoftwareRequirement,
    *,
    requirement_level: str | None = None,
    version: str | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    reason: str | None = None,
    notes: str | None = None,
    fields_set: set[str] | None = None,
) -> EmployeeSoftwareRequirement:
    touched = fields_set or set()
    if "requirement_level" in touched or (fields_set is None and requirement_level is not None):
        level = (requirement_level or requirement.requirement_level).strip().lower()
        if level not in SOFTWARE_REQUIREMENT_LEVELS:
            raise ProTrackValidationError(
                f"Invalid requirement_level. Allowed: {sorted(SOFTWARE_REQUIREMENT_LEVELS)}"
            )
        requirement.requirement_level = level
    if "version" in touched or (fields_set is None and version is not None):
        requirement.version = _optional_str(version)
    if "effective_from" in touched or (fields_set is None and effective_from is not None):
        requirement.effective_from = effective_from
    if "effective_to" in touched or (fields_set is None and effective_to is not None):
        requirement.effective_to = effective_to
    if "reason" in touched or (fields_set is None and reason is not None):
        requirement.reason = _optional_str(reason)
    if "notes" in touched or (fields_set is None and notes is not None):
        requirement.notes = _optional_str(notes)
    ef = requirement.effective_from
    et = requirement.effective_to
    if ef is not None and et is not None and et < ef:
        raise ProTrackValidationError("effective_to cannot be before effective_from.")
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def delete_requirement(db: Session, requirement: EmployeeSoftwareRequirement) -> None:
    db.delete(requirement)
    db.commit()


def user_compliance(db: Session, user_id: UUID) -> dict:
    """Compare required software vs active license assignments for a user."""
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("User not found.")
    today = date.today()
    requirements = list_requirements(db, user_id=user_id, active_on=today)
    assignments = list_assignments(db, user_id=user_id, active_only=True)
    licensed_software_ids: set[UUID] = set()
    for assignment in assignments:
        pool = get_license_pool(db, assignment.license_pool_id)
        if pool is not None:
            licensed_software_ids.add(pool.software_id)

    items: list[dict] = []
    missing_required = 0
    for req in requirements:
        soft = get_software(db, req.software_id)
        licensed = req.software_id in licensed_software_ids
        if req.requirement_level == "required" and not licensed:
            missing_required += 1
        items.append(
            {
                "requirement_id": req.id,
                "software_id": req.software_id,
                "software_name": soft.name if soft else None,
                "requirement_level": req.requirement_level,
                "version": req.version,
                "is_licensed": licensed,
                "status": "licensed" if licensed else "missing",
            }
        )
    extra_licensed = [
        {
            "software_id": sid,
            "software_name": (get_software(db, sid).name if get_software(db, sid) else None),
        }
        for sid in licensed_software_ids
        if sid not in {r.software_id for r in requirements}
    ]
    return {
        "user_id": user_id,
        "full_name": f"{user.first_name} {user.last_name}".strip() or None,
        "requirements": items,
        "missing_required_count": missing_required,
        "licensed_without_requirement": extra_licensed,
        "is_compliant": missing_required == 0,
    }


def software_counts_for_dashboard(db: Session) -> dict[str, int]:
    catalog_count = int(db.scalar(select(func.count()).select_from(SoftwareCatalog)) or 0)
    active_catalog = int(
        db.scalar(
            select(func.count())
            .select_from(SoftwareCatalog)
            .where(SoftwareCatalog.is_active.is_(True))
        )
        or 0
    )
    pool_count = int(db.scalar(select(func.count()).select_from(SoftwareLicensePool)) or 0)
    today = date.today()
    until = today + timedelta(days=30)
    expiring_30 = int(
        db.scalar(
            select(func.count())
            .select_from(SoftwareLicensePool)
            .where(
                SoftwareLicensePool.expiry_date.is_not(None),
                SoftwareLicensePool.expiry_date >= today,
                SoftwareLicensePool.expiry_date <= until,
            )
        )
        or 0
    )
    expired = int(
        db.scalar(
            select(func.count())
            .select_from(SoftwareLicensePool)
            .where(
                SoftwareLicensePool.expiry_date.is_not(None),
                SoftwareLicensePool.expiry_date < today,
            )
        )
        or 0
    )
    active_assignments = int(
        db.scalar(
            select(func.count())
            .select_from(SoftwareAssignment)
            .where(_active_assignment_filter())
        )
        or 0
    )
    return {
        "software_catalog_count": catalog_count,
        "active_software_count": active_catalog,
        "license_pool_count": pool_count,
        "software_assignments_count": active_assignments,
        "licenses_expiring_30": expiring_30,
        "licenses_expired": expired,
    }
