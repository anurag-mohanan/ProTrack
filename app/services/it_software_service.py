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
    SoftwareInstallation,
    SoftwareLicensePool,
)
from app.models.enums import ActivityAction, EntityType
from app.models.models import Customer, User
from app.services.activity_service import log_activity


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
    """Rights still free under the pool's license metric (allocation engine).

    Named/per-user: owned − distinct holders; per-device: owned − devices;
    concurrent: owned − peak scheduled/active use; site: effectively unlimited.
    """
    from app.services import resource_allocation_engine as allocation

    status = (getattr(pool, "status", None) or "active").lower()
    if status in {"terminated", "cancelled", "suspended", "draft"}:
        return 0
    summary = allocation.license_summary(db, pool)
    if summary["available_rights"] is None:
        return max(int(pool.seat_count or 0), summary["authorized_users"] + 1)
    return int(summary["available_rights"])


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
    commercial_model: str | None = None,
    assignment_model: str | None = None,
    cost: Decimal | None = None,
    currency_code: str | None = None,
    purchase_date: date | None = None,
    expiry_date: date | None = None,
    renewal_mode: str | None = None,
    renewal_frequency: str | None = None,
    renewal_amount: Decimal | None = None,
    auto_renew: bool = False,
    renewal_notice_days: int = 30,
    amc_required: bool | None = None,
    amc_percent: Decimal | None = None,
    amc_amount: Decimal | None = None,
    amc_amount_overridden: bool = False,
    expense_id: UUID | None = None,
    notes: str | None = None,
) -> SoftwareLicensePool:
    from app.models.it_operations import (
        ASSIGNMENT_LICENSE_TYPES,
        COMMERCIAL_MODELS,
        RENEWAL_FREQUENCIES,
    )
    from app.services import finance_software_bridge_service as sw_bridge

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
    model = _optional_str(commercial_model)
    if model is not None:
        model = model.lower()
        if model not in COMMERCIAL_MODELS:
            raise ProTrackValidationError(
                f"Invalid commercial_model. Allowed: {sorted(COMMERCIAL_MODELS)}"
            )
    assign_model = _optional_str(assignment_model)
    if assign_model is not None:
        assign_model = assign_model.lower()
        if assign_model not in ASSIGNMENT_LICENSE_TYPES:
            raise ProTrackValidationError(
                f"Invalid assignment_model. Allowed: {sorted(ASSIGNMENT_LICENSE_TYPES)}"
            )
    freq = _optional_str(renewal_frequency)
    if freq is not None:
        freq = freq.lower()
        if freq not in RENEWAL_FREQUENCIES:
            raise ProTrackValidationError(
                f"Invalid renewal_frequency. Allowed: {sorted(RENEWAL_FREQUENCIES)}"
            )
    currency = _optional_str(currency_code)
    if currency is not None:
        currency = currency.upper()
        if len(currency) != 3:
            raise ProTrackValidationError("currency_code must be a 3-letter ISO code.")

    computed_amc = amc_amount
    if model == "perpetual" and amc_required and not amc_amount_overridden and cost is not None:
        if amc_percent is None:
            raise ProTrackValidationError("amc_percent is required when AMC is required.")
        if Decimal(str(amc_percent)) < 0:
            raise ProTrackValidationError("amc_percent must be >= 0.")
        computed_amc = sw_bridge.calculate_amc_amount(Decimal(str(cost)), Decimal(str(amc_percent)))

    next_renewal = expiry_date
    if model == "subscription" and next_renewal is None and purchase_date is not None and freq:
        next_renewal = sw_bridge.add_renewal_period(purchase_date, freq)

    pool = SoftwareLicensePool(
        id=uuid4(),
        software_id=software_id,
        seat_count=int(seat_count),
        purchased_by=pb,
        owner_customer_id=owner_customer_id,
        license_type=lt or assign_model,
        commercial_model=model,
        assignment_model=assign_model or lt,
        status="active",
        cost=cost,
        currency_code=currency,
        purchase_date=purchase_date,
        expiry_date=next_renewal,
        renewal_mode=_optional_str(renewal_mode) or freq,
        renewal_frequency=freq,
        renewal_amount=renewal_amount if renewal_amount is not None else cost,
        auto_renew=bool(auto_renew),
        renewal_notice_days=int(renewal_notice_days or 30),
        amc_required=amc_required,
        amc_percent=amc_percent,
        amc_amount=computed_amc,
        amc_amount_overridden=bool(amc_amount_overridden),
        expense_id=expense_id,
        notes=_optional_str(notes),
    )
    if not getattr(pool, "entitlement_code", None):
        pool.entitlement_code = sw_bridge._next_entitlement_code(db, software)
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
    assignment_model: str | None = None,
    cost: Decimal | None = None,
    currency_code: str | None = None,
    expiry_date: date | None = None,
    renewal_mode: str | None = None,
    notes: str | None = None,
    fields_set: set[str] | None = None,
    actor: User | None = None,
) -> SoftwareLicensePool:
    from app.models.it_operations import ASSIGNMENT_LICENSE_TYPES
    from app.services import resource_allocation_engine as allocation

    touched = fields_set or set()
    before = allocation.license_summary(db, pool)
    if "assignment_model" in touched or (fields_set is None and assignment_model is not None):
        model = (_optional_str(assignment_model) or "").lower() or None
        if model is not None and model not in ASSIGNMENT_LICENSE_TYPES:
            raise ProTrackValidationError(
                f"Invalid assignment_model. Allowed: {sorted(ASSIGNMENT_LICENSE_TYPES)}"
            )
        pool.assignment_model = model
    if "seat_count" in touched or (fields_set is None and seat_count is not None):
        if seat_count is None or seat_count < 1:
            raise ProTrackValidationError("seat_count must be at least 1.")
        pool.seat_count = int(seat_count)
    after = allocation.license_summary(db, pool)
    if after["metric"] != allocation.METRIC_SITE and after["rights_allocated"] > int(pool.seat_count or 0):
        db.rollback()
        raise ProTrackValidationError(
            f"{after['metric_label']} with {pool.seat_count} right(s) cannot cover the "
            f"{after['rights_allocated']} rights already allocated. Release allocations or add rights first."
        )
    if before["metric"] != after["metric"] or before["rights_owned"] != after["rights_owned"]:
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_license_pool,
            entity_id=pool.id,
            action=ActivityAction.it_license_metric_changed,
            old_value={"metric": before["metric"], "rights_owned": before["rights_owned"]},
            new_value={"metric": after["metric"], "rights_owned": after["rights_owned"]},
            outcome="success",
            module="it_operations",
            commit=False,
        )
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


def _assignment_audit(row: SoftwareAssignment, pool: SoftwareLicensePool, window_label: str) -> dict:
    from app.services import resource_allocation_engine as allocation

    return {
        "license_pool_id": str(pool.id),
        "software_id": str(pool.software_id),
        "license_metric": allocation.license_metric(pool),
        "user_id": str(row.user_id) if row.user_id else None,
        "asset_id": str(row.asset_id) if row.asset_id else None,
        "shift_id": str(row.shift_id) if row.shift_id else None,
        "window": window_label,
        "start": str(row.assigned_date) if row.assigned_date else None,
        "end": str(row.planned_end_date) if row.planned_end_date else None,
        "allocation": "scheduled" if allocation.is_scheduled(row) else "authorization",
        "purpose": row.purpose,
        "override_reason": row.override_reason,
    }


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
    shift_id: UUID | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    planned_end_date: date | None = None,
    purpose: str | None = None,
    actor: User | None = None,
    force_override: bool = False,
    override_reason: str | None = None,
    commit: bool = True,
) -> SoftwareAssignment:
    """Allocate a license right after the allocation engine applies the pool's metric.

    The pool row is locked first so two simultaneous requests for the last right
    (or the same concurrent window) serialise and the second is rejected.
    """
    from app.services import resource_allocation_engine as allocation

    pool = get_license_pool(db, license_pool_id)
    if pool is None:
        raise ProTrackValidationError("License pool not found.")
    if user_id is None and computer_id is None and asset_id is None:
        raise ProTrackValidationError("Assign to a user, computer, and/or asset.")
    if user_id is not None:
        user = db.get(User, user_id)
        if user is None or user.is_deleted:
            raise ProTrackValidationError("User not found.")
        ineligible = allocation.employee_block(db, user_id)
        if ineligible:
            raise ProTrackValidationError(ineligible)
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

    allocation.lock_resource(db, pool)
    when = assigned_date or date.today()
    request = allocation.build_request(
        db,
        start_date=when,
        end_date=planned_end_date,
        shift_id=shift_id,
        start_time=start_time,
        end_time=end_time,
        user_id=user_id,
        asset_id=asset_id,
    )
    result = allocation.evaluate_license(db, pool, request)
    if result["reason_code"] == allocation.REASON_ALREADY_HOLDS:
        raise ProTrackValidationError("An active assignment already exists for this target.")
    if result["reason_code"] == allocation.REASON_POOL_INACTIVE:
        raise ProTrackValidationError(result["reason"])
    allocation.raise_if_blocked(result, override=force_override, override_reason=override_reason)
    overridden = not result["available"]

    row = SoftwareAssignment(
        id=uuid4(),
        license_pool_id=license_pool_id,
        user_id=user_id,
        computer_id=computer_id,
        asset_id=asset_id,
        assigned_date=when,
        planned_end_date=planned_end_date,
        shift_id=shift_id,
        start_time=start_time or None,
        end_time=end_time or None,
        purpose=_optional_str(purpose),
        assigned_by_user_id=actor.id if actor else None,
        override_reason=_optional_str(override_reason) if overridden else None,
        notes=_optional_str(notes),
        department=_optional_str(department),
    )
    db.add(row)
    db.flush()
    if computer_id is not None:
        ensure_installation(
            db,
            computer_id=computer_id,
            software_id=pool.software_id,
            on_date=row.assigned_date or date.today(),
            commit=False,
        )
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_license_pool,
        entity_id=pool.id,
        action=ActivityAction.it_license_assigned,
        new_value={
            **_assignment_audit(row, pool, request.window.label),
            "assignment_id": str(row.id),
            "engine_result": result["reason"],
        },
        outcome="success",
        module="it_operations",
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(row)
    return row


def unassign_license(
    db: Session,
    assignment: SoftwareAssignment,
    *,
    released_date: date | None = None,
    actor: User | None = None,
) -> SoftwareAssignment:
    if assignment.released_date is not None:
        raise ProTrackValidationError("Assignment is already released.")
    assignment.released_date = released_date or date.today()
    assignment.released_by_user_id = actor.id if actor else None
    db.add(assignment)
    pool = db.get(SoftwareLicensePool, assignment.license_pool_id)
    if pool is not None:
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_license_pool,
            entity_id=pool.id,
            action=ActivityAction.it_license_released,
            new_value={
                "assignment_id": str(assignment.id),
                "user_id": str(assignment.user_id) if assignment.user_id else None,
                "released_date": str(assignment.released_date),
            },
            outcome="success",
            module="it_operations",
            commit=False,
        )
    db.commit()
    db.refresh(assignment)
    return assignment


# ---------------------------------------------------------------------------
# License usage (check-out / check-in) — actual consumption, not allocation
# ---------------------------------------------------------------------------


def checkout_license(
    db: Session,
    pool: SoftwareLicensePool,
    *,
    user_id: UUID,
    actor: User,
    asset_id: UUID | None = None,
    notes: str | None = None,
) -> "LicenseUsageSession":
    from datetime import datetime, timezone

    from app.models.it_operations import LicenseUsageSession
    from app.services import resource_allocation_engine as allocation

    if allocation.license_metric(pool) != allocation.METRIC_CONCURRENT:
        raise ProTrackValidationError("Check-out applies to concurrent / floating licenses only.")
    allocation.lock_resource(db, pool)
    blocked = allocation._pool_block(pool, date.today())
    if blocked:
        raise ProTrackValidationError(blocked)
    today = date.today()
    authorization = db.scalar(
        select(SoftwareAssignment).where(
            SoftwareAssignment.license_pool_id == pool.id,
            SoftwareAssignment.user_id == user_id,
            SoftwareAssignment.released_date.is_(None),
            or_(SoftwareAssignment.assigned_date.is_(None), SoftwareAssignment.assigned_date <= today),
            or_(SoftwareAssignment.planned_end_date.is_(None), SoftwareAssignment.planned_end_date >= today),
        )
    )
    if authorization is None:
        raise ProTrackValidationError("Employee is not authorized for this license. Assign it first.")
    open_session = db.scalar(
        select(LicenseUsageSession).where(
            LicenseUsageSession.license_pool_id == pool.id,
            LicenseUsageSession.user_id == user_id,
            LicenseUsageSession.checked_in_at.is_(None),
        )
    )
    if open_session is not None:
        raise ProTrackValidationError("Employee already has this license checked out.")
    active = allocation.count_active_sessions(db, pool.id)
    if active >= int(pool.seat_count or 0):
        raise ProTrackValidationError(
            f"Unavailable — all concurrent rights are currently in use ({active} / {pool.seat_count}).",
            status_code=409,
        )
    session_row = LicenseUsageSession(
        id=uuid4(),
        license_pool_id=pool.id,
        assignment_id=authorization.id,
        user_id=user_id,
        asset_id=asset_id or authorization.asset_id,
        checked_out_at=datetime.now(timezone.utc).replace(tzinfo=None),
        checked_out_by_user_id=actor.id,
        notes=_optional_str(notes),
    )
    db.add(session_row)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_license_pool,
        entity_id=pool.id,
        action=ActivityAction.it_license_checked_out,
        new_value={"session_id": str(session_row.id), "user_id": str(user_id),
                   "active_usage": active + 1, "rights_owned": pool.seat_count},
        outcome="success",
        module="it_operations",
        commit=False,
    )
    db.commit()
    db.refresh(session_row)
    return session_row


def checkin_license(db: Session, session_id: UUID, *, actor: User) -> "LicenseUsageSession":
    from datetime import datetime, timezone

    from app.models.it_operations import LicenseUsageSession

    row = db.get(LicenseUsageSession, session_id)
    if row is None:
        raise ProTrackValidationError("Usage session not found.", status_code=404)
    if row.checked_in_at is not None:
        raise ProTrackValidationError("License is already released.")
    row.checked_in_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.checked_in_by_user_id = actor.id
    db.add(row)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_license_pool,
        entity_id=row.license_pool_id,
        action=ActivityAction.it_license_checked_in,
        new_value={"session_id": str(row.id), "user_id": str(row.user_id)},
        outcome="success",
        module="it_operations",
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


def list_usage_sessions(db: Session, pool_id: UUID, *, active_only: bool = False) -> list:
    from app.models.it_operations import LicenseUsageSession

    stmt = select(LicenseUsageSession).where(LicenseUsageSession.license_pool_id == pool_id)
    if active_only:
        stmt = stmt.where(LicenseUsageSession.checked_in_at.is_(None))
    return list(db.scalars(stmt.order_by(LicenseUsageSession.checked_out_at.desc()).limit(200)).all())


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
    commit: bool = True,
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
    db.flush()
    if commit:
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


def software_counts_for_dashboard(
    db: Session, *, expiring_within_days: int = 30
) -> dict[str, int]:
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
    until = today + timedelta(days=expiring_within_days)
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
    from app.services import resource_allocation_engine as allocation

    inactive = {"terminated", "cancelled", "suspended", "draft"}
    pools = [
        p for p in db.scalars(select(SoftwareLicensePool)).all()
        if (p.status or "active") not in inactive
    ]
    seats_total = seats_assigned = seats_available = 0
    active_usage = authorized = compliance_issues = unconfigured = site_pools = 0
    for pool in pools:
        s = allocation.license_summary(db, pool, on_date=today)
        authorized += s["authorized_users"]
        active_usage += s["active_usage"]
        if s["metric"] == allocation.METRIC_UNSPECIFIED:
            unconfigured += 1
        if s["compliance_status"] in {"OVER_ALLOCATED", "EXPIRED"}:
            compliance_issues += 1
        if s["metric"] == allocation.METRIC_SITE:
            site_pools += 1
            continue
        seats_total += s["rights_owned"]
        seats_assigned += s["rights_allocated"]
        seats_available += s["available_rights"] or 0
    return {
        "software_catalog_count": catalog_count,
        "active_software_count": active_catalog,
        "license_pool_count": pool_count,
        "software_assignments_count": active_assignments,
        "licenses_expiring_30": expiring_30,
        "licenses_expiring_window": expiring_30,
        "licenses_expired": expired,
        "license_seats_total": seats_total,
        "license_seats_assigned": seats_assigned,
        "license_seats_available": seats_available,
        "license_authorized_users": authorized,
        "license_active_usage": active_usage,
        "license_compliance_issues": compliance_issues,
        "license_metric_unconfigured": unconfigured,
        "license_site_pools": site_pools,
    }


def list_installations(
    db: Session, *, computer_id: UUID | None = None, active_only: bool = True
) -> list[SoftwareInstallation]:
    stmt = select(SoftwareInstallation).order_by(SoftwareInstallation.installed_date.desc())
    if computer_id is not None:
        stmt = stmt.where(SoftwareInstallation.computer_id == computer_id)
    if active_only:
        stmt = stmt.where(SoftwareInstallation.uninstalled_date.is_(None))
    return list(db.scalars(stmt).all())


def ensure_installation(
    db: Session,
    *,
    computer_id: UUID,
    software_id: UUID,
    on_date: date | None = None,
    installed_by_user_id: UUID | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> SoftwareInstallation:
    existing = db.scalar(
        select(SoftwareInstallation).where(
            SoftwareInstallation.computer_id == computer_id,
            SoftwareInstallation.software_id == software_id,
            SoftwareInstallation.uninstalled_date.is_(None),
        )
    )
    if existing is not None:
        return existing
    if db.get(Computer, computer_id) is None:
        raise ProTrackValidationError("Computer not found.")
    if db.get(SoftwareCatalog, software_id) is None:
        raise ProTrackValidationError("Software not found.")
    row = SoftwareInstallation(
        id=uuid4(),
        computer_id=computer_id,
        software_id=software_id,
        installed_date=on_date or date.today(),
        installed_by_user_id=installed_by_user_id,
        notes=_optional_str(notes),
    )
    db.add(row)
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
    return row


def uninstall_software(
    db: Session,
    installation: SoftwareInstallation,
    *,
    uninstalled_date: date | None = None,
    commit: bool = True,
) -> SoftwareInstallation:
    if installation.uninstalled_date is not None:
        raise ProTrackValidationError("Software is already uninstalled from this computer.")
    installation.uninstalled_date = uninstalled_date or date.today()
    db.add(installation)
    db.flush()
    if commit:
        db.commit()
        db.refresh(installation)
    return installation

