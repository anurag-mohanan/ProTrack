"""Day-prorated retainer / subscription customer billing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.salary_eligibility import user_requires_salary
from app.models.enums import TeamBillingPeriod, WorkingModelCode
from app.models.finance import TeamCommercialTerms
from app.models.models import TeamMember, TeamMembershipPeriod, User, WorkingModel
from app.services.finance.commercial_fee_rules import uses_flat_customer_fee
from app.services.finance.employment_cost import (
    _intersect_days,
    _month_bounds,
    user_counts_for_headcount,
)


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def normalize_monthly_fee(amount: Decimal, period: TeamBillingPeriod) -> Decimal:
    if period == TeamBillingPeriod.monthly:
        return amount
    if period == TeamBillingPeriod.quarterly:
        return (amount / Decimal("3")).quantize(Decimal("0.01"))
    if period == TeamBillingPeriod.annual:
        return (amount / Decimal("12")).quantize(Decimal("0.01"))
    return amount


def retainer_fx_date_for_month(as_of: date) -> date:
    """Retainer / subscription fees lock FX on the first calendar day of the month."""
    return as_of.replace(day=1)


def _amount_to_inr_at(
    db: Session,
    *,
    amount: Decimal,
    currency_code: str,
    on_date: date,
) -> Decimal:
    """Convert a native fee amount to INR using FX as of ``on_date`` (month start for retainers)."""
    from app.services.finance.fx_service import get_base_currency, to_base_amount

    native = _d(amount)
    code = (currency_code or "INR").upper()
    if native <= 0:
        return Decimal("0.00")
    if code == get_base_currency(db).upper():
        return native
    base, _, _ = to_base_amount(db, amount=native, currency_code=code, on_date=on_date)
    return _d(base)


def _rate_for_user_inr(
    db: Session,
    user: User,
    *,
    term: TeamCommercialTerms,
    bands: list,
    fx_date: date,
) -> Decimal:
    """Per-resource monthly INR rate using month-start FX on native fee amounts."""
    term_currency = getattr(term, "currency_code", None) or "INR"
    default_native = _d(term.customer_fee_amount)
    if not bands:
        return _amount_to_inr_at(
            db, amount=default_native, currency_code=term_currency, on_date=fx_date
        )

    band_map: dict[str, Decimal] = {}
    for band in bands:
        skill = (getattr(band, "skill_level", None) or "").strip().lower()
        currency = getattr(band, "currency_code", None) or term_currency
        native = _d(getattr(band, "fee_amount", None))
        band_map[skill] = _amount_to_inr_at(
            db, amount=native, currency_code=currency, on_date=fx_date
        )
    default_rate = band_map.get("") or _amount_to_inr_at(
        db, amount=default_native, currency_code=term_currency, on_date=fx_date
    )
    skill = getattr(user, "skill_level", None)
    key = (
        skill.value
        if skill is not None and hasattr(skill, "value")
        else (str(skill) if skill else "")
    )
    key = (key or "").strip().lower()
    return band_map.get(key, default_rate)


def billable_team_month_factor(
    db: Session,
    *,
    user_id: UUID,
    team_id: UUID,
    as_of: date,
    window_start: date | None = None,
    window_end: date | None = None,
) -> Decimal:
    """Fraction of the calendar month the user was billable on the team.

    Days before ``TeamMember.effective_from`` / membership period start (e.g. joined
    mid-month on the 23rd) do not count. Optional ``window_start`` / ``window_end``
    further clip to commercial-term effective dates within the month.
    """
    month_start, month_end, days_in_month = _month_bounds(as_of)
    clip_start = max(month_start, window_start) if window_start else month_start
    clip_end = min(month_end, window_end) if window_end else month_end
    if clip_end < clip_start:
        return Decimal("0")

    user = db.get(User, user_id)
    if user is None:
        return Decimal("0")

    employment_start = clip_start
    if user.joining_date is not None and user.joining_date > employment_start:
        employment_start = user.joining_date
    employment_end = clip_end
    leaving = getattr(user, "leaving_date", None)
    if leaving is not None and leaving < employment_end:
        employment_end = leaving
    if employment_end < employment_start:
        return Decimal("0")

    periods = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id == user_id,
            TeamMembershipPeriod.team_id == team_id,
            TeamMembershipPeriod.effective_from <= clip_end,
        )
    ).all()

    team_days = 0
    for period in periods:
        if not bool(period.is_billable_headcount):
            continue
        p_end = period.effective_to if period.effective_to is not None else clip_end
        if p_end < clip_start or period.effective_from > clip_end:
            continue
        w_start = max(period.effective_from, employment_start)
        w_end = min(p_end, employment_end)
        team_days += _intersect_days(w_start, w_end, clip_start, clip_end)

    if team_days <= 0:
        member = db.scalar(
            select(TeamMember).where(
                TeamMember.user_id == user_id,
                TeamMember.team_id == team_id,
            )
        )
        if member is not None and bool(getattr(member, "is_billable_headcount", True)):
            m_start = getattr(member, "effective_from", None) or employment_start
            if m_start <= clip_end:
                w_start = max(m_start, employment_start)
                team_days = _intersect_days(w_start, employment_end, clip_start, clip_end)

    if team_days <= 0:
        return Decimal("0")
    if (
        team_days >= days_in_month
        and employment_start <= month_start
        and employment_end >= month_end
        and clip_start <= month_start
        and clip_end >= month_end
    ):
        return Decimal("1")
    return (Decimal(team_days) / Decimal(days_in_month)).quantize(Decimal("0.0001"))


def _rate_for_user(
    user: User,
    *,
    bands: list,
    base_fee_inr: Decimal,
) -> Decimal:
    """Legacy helper kept for tests — prefer ``_rate_for_user_inr`` for retainers."""
    if not bands:
        return _d(base_fee_inr)
    band_map = {(band.skill_level or ""): _d(band.base_fee_inr) for band in bands}
    default_rate = band_map.get("") or _d(base_fee_inr)
    skill = getattr(user, "skill_level", None)
    key = (
        skill.value
        if skill is not None and hasattr(skill, "value")
        else (str(skill) if skill else "")
    )
    return band_map.get(key, default_rate)


def _billable_users_for_month(
    db: Session, team_id: UUID, *, as_of: date
) -> list[User]:
    """Users who should contribute to retainer fee in the month of ``as_of``.

    Includes current billable salary-required people, plus anyone with a billable
    membership overlapping the month (so mid-month leavers still bill for days served).
    """
    from app.services.finance.billable_headcount import billable_salary_users

    month_start, month_end, _ = _month_bounds(as_of)
    seen: set[UUID] = set()
    users: list[User] = []

    for user in billable_salary_users(db, team_id, as_of=as_of):
        seen.add(user.id)
        users.append(user)

    periods = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.team_id == team_id,
            TeamMembershipPeriod.is_billable_headcount.is_(True),
            TeamMembershipPeriod.effective_from <= month_end,
        )
    ).all()
    candidate_ids: set[UUID] = set()
    for period in periods:
        p_end = period.effective_to if period.effective_to is not None else month_end
        if p_end < month_start:
            continue
        candidate_ids.add(period.user_id)

    members = db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)).all()
    for member in members:
        if not bool(getattr(member, "is_billable_headcount", True)):
            continue
        m_start = getattr(member, "effective_from", None) or month_start
        if m_start > month_end:
            continue
        candidate_ids.add(member.user_id)

    for user_id in candidate_ids - seen:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            continue
        if not user_requires_salary(user):
            continue
        # Leavers still bill for days they were active in the month.
        if not user_counts_for_headcount(user, as_of=month_end) and (
            getattr(user, "leaving_date", None) is None
            or user.leaving_date < month_start
        ):
            continue
        users.append(user)
        seen.add(user.id)

    return users


def _native_fee_for_user(
    user: User,
    *,
    term: TeamCommercialTerms,
    bands: list,
) -> tuple[Decimal, str, str]:
    """Return (native_amount, currency_code, skill_key) for the user's skill band."""
    term_currency = (getattr(term, "currency_code", None) or "INR").upper()
    default_native = _d(term.customer_fee_amount)
    skill = getattr(user, "skill_level", None)
    key = (
        skill.value
        if skill is not None and hasattr(skill, "value")
        else (str(skill) if skill else "")
    )
    key = (key or "").strip().lower()
    if not bands:
        return default_native, term_currency, key
    band_map: dict[str, tuple[Decimal, str]] = {}
    for band in bands:
        skill_key = (getattr(band, "skill_level", None) or "").strip().lower()
        currency = (getattr(band, "currency_code", None) or term_currency).upper()
        native = _d(getattr(band, "fee_amount", None))
        band_map[skill_key] = (native, currency)
    if key in band_map:
        native, currency = band_map[key]
        return native, currency, key
    if "" in band_map:
        native, currency = band_map[""]
        return native, currency, key or ""
    return default_native, term_currency, key


def retainer_fee_lines_for_term(
    db: Session,
    term: TeamCommercialTerms,
    *,
    as_of: date,
) -> list[dict]:
    """Per-person accounts trail for one commercial term (INR amounts for the as_of month)."""
    from app.services.finance.fx_service import get_base_currency, resolve_fx_rate

    if term.effective_from and term.effective_from > as_of:
        return []
    month_start, _, _ = _month_bounds(as_of)
    if term.effective_to is not None and term.effective_to < month_start:
        return []

    model = db.get(WorkingModel, term.working_model_id)
    strategy = model.strategy_key if model is not None else None
    if not uses_flat_customer_fee(strategy):
        return []

    is_retainer = strategy == WorkingModelCode.retainer or (
        hasattr(strategy, "value") and strategy.value == WorkingModelCode.retainer.value
    )
    fx_date = retainer_fx_date_for_month(as_of)
    window_start = max(month_start, term.effective_from) if term.effective_from else month_start
    window_end = _month_bounds(as_of)[1]
    if term.effective_to is not None:
        window_end = min(window_end, term.effective_to)
    if window_start > window_end:
        return []

    bands = list(getattr(term, "fee_bands", None) or [])
    base = get_base_currency(db).upper()
    lines: list[dict] = []

    if is_retainer:
        for user in _billable_users_for_month(db, term.team_id, as_of=as_of):
            attendance = billable_team_month_factor(
                db,
                user_id=user.id,
                team_id=term.team_id,
                as_of=as_of,
                window_start=window_start,
                window_end=window_end,
            )
            if attendance <= 0:
                continue
            # Accounts lock: full monthly seat when billable any day this month.
            billing_factor = Decimal("1")
            native, currency, skill_key = _native_fee_for_user(user, term=term, bands=bands)
            rate_inr = _amount_to_inr_at(
                db, amount=native, currency_code=currency, on_date=fx_date
            )
            try:
                fx_rate = (
                    Decimal("1")
                    if currency.upper() == base
                    else resolve_fx_rate(
                        db, from_currency=currency, on_date=fx_date, fetch_live=False
                    )
                )
            except Exception:
                fx_rate = (
                    (rate_inr / native).quantize(Decimal("0.00000001"))
                    if native > 0
                    else Decimal("1")
                )
            amount = (rate_inr * billing_factor).quantize(Decimal("0.01"))
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or (
                user.email or str(user.id)
            )
            lines.append(
                {
                    "user_id": str(user.id),
                    "user_name": name,
                    "skill_level": skill_key or None,
                    "native_fee": native,
                    "currency_code": currency,
                    "fx_date": fx_date.isoformat(),
                    "fx_rate": fx_rate,
                    "attendance_factor": attendance,
                    "billing_factor": billing_factor,
                    "amount_inr": amount,
                }
            )
        return lines

    # Flat subscription: one line for the term.
    month_start, month_end, days_in_month = _month_bounds(as_of)
    active_days = (window_end - window_start).days + 1
    attendance = (
        Decimal("1")
        if active_days >= days_in_month and window_start <= month_start and window_end >= month_end
        else (Decimal(active_days) / Decimal(days_in_month)).quantize(Decimal("0.0001"))
    )
    currency = (getattr(term, "currency_code", None) or "INR").upper()
    native = _d(term.customer_fee_amount)
    rate_inr = _amount_to_inr_at(db, amount=native, currency_code=currency, on_date=fx_date)
    try:
        fx_rate = (
            Decimal("1")
            if currency == base
            else resolve_fx_rate(db, from_currency=currency, on_date=fx_date, fetch_live=False)
        )
    except Exception:
        fx_rate = (
            (rate_inr / native).quantize(Decimal("0.00000001")) if native > 0 else Decimal("1")
        )
    amount = (rate_inr * attendance).quantize(Decimal("0.01"))
    from app.models.models import Team as TeamModel

    team_row = db.get(TeamModel, term.team_id)
    lines.append(
        {
            "user_id": None,
            "user_name": team_row.name if team_row else "Flat subscription",
            "skill_level": None,
            "native_fee": native,
            "currency_code": currency,
            "fx_date": fx_date.isoformat(),
            "fx_rate": fx_rate,
            "attendance_factor": attendance,
            "billing_factor": attendance,
            "amount_inr": amount,
        }
    )
    return lines


def prorated_retainer_amount_for_term(
    db: Session,
    term: TeamCommercialTerms,
    *,
    as_of: date,
) -> Decimal:
    """Monthly-INR customer fee for one commercial term.

    Retainer: full monthly skill-band rate per billable seat (month-start FX).
    Non-retainer flat fee: still day-prorates term active days; month-start FX.
    """
    if term.effective_from and term.effective_from > as_of:
        return Decimal("0.00")
    if term.effective_to and term.effective_to < as_of.replace(day=1):
        month_start, _, _ = _month_bounds(as_of)
        if term.effective_to < month_start:
            return Decimal("0.00")

    model = db.get(WorkingModel, term.working_model_id)
    strategy = model.strategy_key if model is not None else None
    if not uses_flat_customer_fee(strategy):
        return Decimal("0.00")

    month_start, month_end, days_in_month = _month_bounds(as_of)
    fx_date = retainer_fx_date_for_month(as_of)
    window_start = max(month_start, term.effective_from) if term.effective_from else month_start
    window_end = month_end
    if term.effective_to is not None:
        window_end = min(window_end, term.effective_to)
    if window_start > window_end:
        return Decimal("0.00")

    is_retainer = strategy == WorkingModelCode.retainer or (
        hasattr(strategy, "value") and strategy.value == WorkingModelCode.retainer.value
    )
    bands = list(getattr(term, "fee_bands", None) or [])

    if is_retainer:
        period_amount = Decimal("0.00")
        for user in _billable_users_for_month(db, term.team_id, as_of=as_of):
            attendance = billable_team_month_factor(
                db,
                user_id=user.id,
                team_id=term.team_id,
                as_of=as_of,
                window_start=window_start,
                window_end=window_end,
            )
            if attendance <= 0:
                continue
            # Full seat when billable any day this month (accounts lock).
            rate = _rate_for_user_inr(
                db, user, term=term, bands=bands, fx_date=fx_date
            )
            period_amount += rate
        return normalize_monthly_fee(period_amount.quantize(Decimal("0.01")), term.billing_period)

    active_days = (window_end - window_start).days + 1
    factor = (
        Decimal("1")
        if active_days >= days_in_month and window_start <= month_start and window_end >= month_end
        else (Decimal(active_days) / Decimal(days_in_month)).quantize(Decimal("0.0001"))
    )
    monthly_inr = _amount_to_inr_at(
        db,
        amount=_d(term.customer_fee_amount),
        currency_code=getattr(term, "currency_code", None) or "INR",
        on_date=fx_date,
    )
    period_amount = (monthly_inr * factor).quantize(Decimal("0.01"))
    return normalize_monthly_fee(period_amount, term.billing_period)


def team_retainer_fee_monthly(
    db: Session, *, team_id: UUID | None, as_of: date
) -> Decimal:
    """Sum of retainer/subscription fees for active terms (month-start FX)."""
    stmt = select(TeamCommercialTerms).where(TeamCommercialTerms.is_active.is_(True))
    if team_id is not None:
        stmt = stmt.where(TeamCommercialTerms.team_id == team_id)
    total = Decimal("0.00")
    for term in db.scalars(stmt).all():
        total += prorated_retainer_amount_for_term(db, term, as_of=as_of)
    return total.quantize(Decimal("0.01"))
