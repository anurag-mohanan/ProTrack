"""Finance ↔ IT software license bridge.

Finance records the purchase/renewal expense. IT owns the operational
``SoftwareLicensePool`` entitlement (seats, assignments, renewal/AMC, termination).
Both sides share ``SoftwareCatalog`` as the single software master.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import CostCentre, Expense
from app.models.it_operations import (
    ASSIGNMENT_LICENSE_TYPES,
    COMMERCIAL_MODELS,
    LICENSE_POOL_STATUSES,
    LICENSE_TYPE_CODES,
    PURCHASED_BY_CODES,
    RENEWAL_FREQUENCIES,
    SoftwareCatalog,
    SoftwareLicensePool,
    SoftwareLicenseRenewal,
)
from app.models.models import User
from app.services import it_software_service


SOFTWARE_CENTRE_CODES = frozenset({"SW_LICENSES", "SW_RENEWALS", "CLOUD"})


def _add_months(start: date, months: int) -> date:
    """Calendar month add without external dependencies."""
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    # Clamp day for shorter months.
    for day in range(start.day, 0, -1):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return date(year, month, 1)


def is_software_cost_centre(db: Session, cost_centre_id: UUID | None) -> bool:
    if cost_centre_id is None:
        return False
    centre = db.get(CostCentre, cost_centre_id)
    return bool(centre and (centre.code or "").upper() in SOFTWARE_CENTRE_CODES)


def add_renewal_period(start: date, frequency: str) -> date:
    freq = (frequency or "").strip().lower()
    if freq == "monthly":
        return _add_months(start, 1)
    if freq == "quarterly":
        return _add_months(start, 3)
    if freq == "half_yearly":
        return _add_months(start, 6)
    if freq == "yearly":
        return _add_months(start, 12)
    if freq == "every_2_years":
        return _add_months(start, 24)
    if freq == "custom":
        raise ProTrackValidationError(
            "Custom renewal frequency requires an explicit next renewal date."
        )
    raise ProTrackValidationError(
        f"Invalid renewal_frequency. Allowed: {sorted(RENEWAL_FREQUENCIES)}"
    )


def calculate_amc_amount(license_cost: Decimal | None, percent: Decimal | None) -> Decimal | None:
    if license_cost is None or percent is None:
        return None
    if percent < 0:
        raise ProTrackValidationError("AMC percentage must be greater than or equal to 0.")
    return (Decimal(license_cost) * Decimal(percent) / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def resolve_commercial_model(pool: SoftwareLicensePool) -> str | None:
    if pool.commercial_model in COMMERCIAL_MODELS:
        return pool.commercial_model
    if pool.license_type in COMMERCIAL_MODELS:
        return pool.license_type
    return None


def pool_is_assignable(pool: SoftwareLicensePool) -> bool:
    status = (pool.status or "active").lower()
    if status in {"terminated", "cancelled", "suspended", "draft"}:
        return False
    return True


def find_software_by_name(db: Session, name: str) -> SoftwareCatalog | None:
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    return db.scalar(
        select(SoftwareCatalog).where(func.lower(SoftwareCatalog.name) == cleaned.lower())
    )


def find_or_create_software(
    db: Session,
    *,
    name: str,
    vendor: str | None = None,
    category: str | None = None,
    version: str | None = None,
    commit: bool = False,
) -> SoftwareCatalog:
    existing = find_software_by_name(db, name)
    if existing is not None:
        return existing
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ProTrackValidationError("Software name is required.")
    from uuid import uuid4 as _uuid4

    row = SoftwareCatalog(
        id=_uuid4(),
        name=cleaned_name,
        vendor=(vendor or "").strip() or None,
        category=(category or "").strip() or None,
        version=(version or "").strip() or None,
        is_active=True,
    )
    db.add(row)
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
    return row


def _next_entitlement_code(db: Session, software: SoftwareCatalog) -> str:
    prefix = (software.code or software.name or "LIC").strip().upper()
    prefix = "".join(ch for ch in prefix if ch.isalnum())[:8] or "LIC"
    year = date.today().year
    count = int(
        db.scalar(
            select(func.count())
            .select_from(SoftwareLicensePool)
            .where(SoftwareLicensePool.software_id == software.id)
        )
        or 0
    )
    return f"{prefix}-{year}-{count + 1:04d}"


def _map_paid_by_to_purchased_by(paid_by: str | None) -> str:
    value = (paid_by or "prosohm").strip().lower()
    if value == "customer":
        return "customer"
    return "organization"


def create_entitlement_from_expense(
    db: Session,
    *,
    expense: Expense,
    actor: User | None = None,
    software_id: UUID | None = None,
    software_name: str | None = None,
    vendor: str | None = None,
    commercial_model: str | None = None,
    assignment_model: str | None = None,
    seat_count: int = 1,
    renewal_frequency: str | None = None,
    next_renewal_date: date | None = None,
    amc_required: bool | None = None,
    amc_percent: Decimal | None = None,
    amc_amount: Decimal | None = None,
    amc_amount_overridden: bool = False,
    auto_renew: bool = False,
    renewal_notice_days: int = 30,
    owner_customer_id: UUID | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> SoftwareLicensePool:
    """Create (or reuse) software master + license pool linked to ``expense``."""
    if expense.license_pool_id is not None:
        existing = db.get(SoftwareLicensePool, expense.license_pool_id)
        if existing is not None:
            return existing

    if software_id is not None:
        software = it_software_service.get_software(db, software_id)
        if software is None:
            raise ProTrackValidationError("Software catalog entry not found.")
    else:
        name = (software_name or expense.name or "").strip()
        if not name:
            raise ProTrackValidationError("Software name is required to create an IT license.")
        software = find_or_create_software(
            db, name=name, vendor=vendor or expense.vendor_name
        )

    model = (commercial_model or "").strip().lower() or None
    if model is not None and model not in COMMERCIAL_MODELS:
        raise ProTrackValidationError(
            f"Invalid commercial_model. Allowed: {sorted(COMMERCIAL_MODELS)}"
        )

    assign_model = (assignment_model or "").strip().lower() or None
    if assign_model is not None and assign_model not in ASSIGNMENT_LICENSE_TYPES:
        raise ProTrackValidationError(
            f"Invalid assignment_model. Allowed: {sorted(ASSIGNMENT_LICENSE_TYPES)}"
        )

    freq = (renewal_frequency or "").strip().lower() or None
    if model == "subscription":
        if not freq:
            # Infer from expense frequency when possible.
            exp_freq = getattr(expense.frequency, "value", expense.frequency)
            exp_freq = str(exp_freq or "").lower()
            if exp_freq in RENEWAL_FREQUENCIES:
                freq = exp_freq
            elif exp_freq == "yearly":
                freq = "yearly"
            else:
                freq = "yearly"
        if freq not in RENEWAL_FREQUENCIES:
            raise ProTrackValidationError(
                f"Invalid renewal_frequency. Allowed: {sorted(RENEWAL_FREQUENCIES)}"
            )

    seats = max(1, int(seat_count or 1))
    purchase = expense.purchase_date or date.today()
    renewal = next_renewal_date or expense.next_renewal_date
    if model == "subscription" and renewal is None and freq and freq != "custom":
        renewal = add_renewal_period(purchase, freq)

    amc_req = amc_required
    amc_pct = amc_percent
    amc_amt = amc_amount
    if model == "perpetual":
        if amc_req is None:
            amc_req = False
        if amc_req:
            if amc_pct is None:
                raise ProTrackValidationError("AMC percentage is required when AMC is Yes.")
            if Decimal(amc_pct) < 0:
                raise ProTrackValidationError("AMC percentage must be greater than or equal to 0.")
            if not amc_amount_overridden or amc_amt is None:
                amc_amt = calculate_amc_amount(expense.amount, Decimal(amc_pct))

    # Prefer explicit assignment model; fall back to legacy license_type codes.
    legacy_type = assign_model or model

    pool = SoftwareLicensePool(
        id=uuid4(),
        software_id=software.id,
        entitlement_code=_next_entitlement_code(db, software),
        purchased_by=_map_paid_by_to_purchased_by(
            getattr(expense.paid_by, "value", expense.paid_by)
        ),
        owner_customer_id=owner_customer_id,
        seat_count=seats,
        license_type=legacy_type,
        commercial_model=model,
        assignment_model=assign_model,
        status="active",
        cost=expense.amount,
        currency_code=expense.currency_code,
        purchase_date=purchase,
        expiry_date=renewal,
        renewal_mode=freq,
        subscription_start_date=purchase if model == "subscription" else None,
        renewal_frequency=freq,
        renewal_amount=expense.amount if model == "subscription" else None,
        auto_renew=bool(auto_renew),
        renewal_notice_days=int(renewal_notice_days or 30),
        amc_required=amc_req,
        amc_percent=amc_pct,
        amc_amount=amc_amt,
        amc_amount_overridden=bool(amc_amount_overridden),
        amc_start_date=purchase if amc_req else None,
        amc_due_date=add_renewal_period(purchase, "yearly") if amc_req else None,
        amc_vendor=expense.vendor_name if amc_req else None,
        expense_id=expense.id,
        notes=notes,
        source_system="finance_expense",
    )
    if pool.purchased_by not in PURCHASED_BY_CODES:
        pool.purchased_by = "organization"

    db.add(pool)
    db.flush()
    expense.software_id = software.id
    expense.license_pool_id = pool.id

    if model == "subscription":
        db.add(
            SoftwareLicenseRenewal(
                id=uuid4(),
                license_pool_id=pool.id,
                kind="subscription",
                period_start=purchase,
                period_end=renewal,
                amount=expense.amount,
                currency_code=expense.currency_code,
                expense_id=expense.id,
                notes="Initial purchase from Finance expense",
                recorded_by_user_id=actor.id if actor else None,
            )
        )
    elif model == "perpetual":
        db.add(
            SoftwareLicenseRenewal(
                id=uuid4(),
                license_pool_id=pool.id,
                kind="purchase",
                period_start=purchase,
                period_end=None,
                amount=expense.amount,
                currency_code=expense.currency_code,
                expense_id=expense.id,
                notes="Perpetual license purchase from Finance expense",
                recorded_by_user_id=actor.id if actor else None,
            )
        )

    if commit:
        db.commit()
        db.refresh(pool)
    return pool


def terminate_license_pool(
    db: Session,
    pool: SoftwareLicensePool,
    *,
    termination_date: date,
    reason: str | None,
    actor: User,
    notes: str | None = None,
) -> SoftwareLicensePool:
    if (pool.status or "").lower() == "terminated":
        raise ProTrackValidationError("License is already terminated.")
    pool.status = "terminated"
    pool.terminated_at = termination_date
    pool.termination_reason = (reason or "").strip() or "Terminated"
    pool.terminated_by_user_id = actor.id
    if notes:
        existing = pool.notes or ""
        pool.notes = f"{existing}\nTermination: {notes}".strip() if existing else f"Termination: {notes}"
    # Soft-release all active assignments as of termination date.
    for assignment in it_software_service.list_assignments(
        db, license_pool_id=pool.id, active_only=True
    ):
        if assignment.released_date is None:
            assignment.released_date = termination_date
    db.commit()
    db.refresh(pool)
    return pool


def renew_subscription_pool(
    db: Session,
    pool: SoftwareLicensePool,
    *,
    actor: User,
    renewal_date: date | None = None,
    period_end: date | None = None,
    amount: Decimal | None = None,
    expense_id: UUID | None = None,
    notes: str | None = None,
) -> SoftwareLicensePool:
    if not pool_is_assignable(pool) and (pool.status or "").lower() == "terminated":
        raise ProTrackValidationError("Cannot renew a terminated license.")
    model = resolve_commercial_model(pool)
    if model != "subscription":
        raise ProTrackValidationError("Only subscription licenses can be renewed this way.")
    start = renewal_date or pool.expiry_date or date.today()
    freq = pool.renewal_frequency or pool.renewal_mode or "yearly"
    end = period_end
    if end is None:
        if freq == "custom":
            raise ProTrackValidationError("Custom frequency requires period_end.")
        end = add_renewal_period(start, freq)
    renew_amount = amount if amount is not None else pool.renewal_amount or pool.cost
    db.add(
        SoftwareLicenseRenewal(
            id=uuid4(),
            license_pool_id=pool.id,
            kind="subscription",
            period_start=start,
            period_end=end,
            amount=renew_amount,
            currency_code=pool.currency_code,
            expense_id=expense_id,
            notes=notes or "Subscription renewal",
            recorded_by_user_id=actor.id,
        )
    )
    pool.expiry_date = end
    pool.renewal_amount = renew_amount
    if pool.status in {"expired", "draft"}:
        pool.status = "active"
    if expense_id is not None:
        expense = db.get(Expense, expense_id)
        if expense is not None:
            expense.license_pool_id = pool.id
            expense.software_id = pool.software_id
            pool.expense_id = pool.expense_id or expense.id
    db.commit()
    db.refresh(pool)
    return pool


def list_migration_candidates(db: Session) -> list[dict]:
    """Active software-centre expenses that are not yet linked to an IT entitlement."""
    centres = {
        c.id: c
        for c in db.scalars(select(CostCentre)).all()
        if (c.code or "").upper() in SOFTWARE_CENTRE_CODES
    }
    if not centres:
        return []
    rows = db.scalars(
        select(Expense)
        .where(
            Expense.is_active.is_(True),
            Expense.cost_centre_id.in_(list(centres.keys())),
            Expense.license_pool_id.is_(None),
        )
        .order_by(Expense.purchase_date.desc().nulls_last())
    ).all()
    out: list[dict] = []
    for row in rows:
        centre = centres.get(row.cost_centre_id)
        matched = find_software_by_name(db, row.name or "")
        out.append(
            {
                "expense_id": str(row.id),
                "expense_name": row.name,
                "cost_centre_code": centre.code if centre else None,
                "cost_centre_name": centre.name if centre else None,
                "amount": row.amount,
                "currency_code": row.currency_code,
                "purchase_date": row.purchase_date.isoformat() if row.purchase_date else None,
                "next_renewal_date": (
                    row.next_renewal_date.isoformat() if row.next_renewal_date else None
                ),
                "vendor_name": row.vendor_name,
                "paid_by": getattr(row.paid_by, "value", row.paid_by),
                "frequency": getattr(row.frequency, "value", row.frequency),
                "matched_software_id": str(matched.id) if matched else None,
                "matched_software_name": matched.name if matched else None,
                "suggested_software_name": matched.name if matched else row.name,
                "commercial_model": None,
                "needs_review": True,
                "review_reason": "Commercial model (perpetual vs subscription) not established.",
            }
        )
    return out


def forecast_future_costs(
    db: Session,
    *,
    as_of: date | None = None,
    horizon_days: int = 365,
) -> list[dict]:
    """Upcoming subscription renewals and AMC dues for active entitlements."""
    today = as_of or date.today()
    until = today + timedelta(days=max(1, horizon_days))
    pools = db.scalars(
        select(SoftwareLicensePool).where(
            SoftwareLicensePool.status.in_(["active", "draft", "suspended"])
        )
    ).all()
    items: list[dict] = []
    for pool in pools:
        if (pool.status or "").lower() == "terminated":
            continue
        soft = it_software_service.get_software(db, pool.software_id)
        model = resolve_commercial_model(pool)
        if model == "subscription" and pool.expiry_date and today <= pool.expiry_date <= until:
            items.append(
                {
                    "license_pool_id": str(pool.id),
                    "software_name": soft.name if soft else None,
                    "kind": "subscription_renewal",
                    "due_date": pool.expiry_date.isoformat(),
                    "amount": pool.renewal_amount or pool.cost,
                    "currency_code": pool.currency_code,
                }
            )
        if model == "perpetual" and pool.amc_required and pool.amc_due_date:
            if today <= pool.amc_due_date <= until:
                items.append(
                    {
                        "license_pool_id": str(pool.id),
                        "software_name": soft.name if soft else None,
                        "kind": "amc",
                        "due_date": pool.amc_due_date.isoformat(),
                        "amount": pool.amc_amount,
                        "currency_code": pool.currency_code,
                    }
                )
    items.sort(key=lambda item: item["due_date"])
    return items
