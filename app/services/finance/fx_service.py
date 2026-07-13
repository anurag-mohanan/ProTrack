"""FX conversion helpers — amounts convert to company base INR at write time."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import CompanyFinanceSettings, FxRate


BASE_CURRENCY = "INR"


def get_base_currency(db: Session) -> str:
    settings = db.scalar(
        select(CompanyFinanceSettings).where(CompanyFinanceSettings.is_active.is_(True))
    )
    return settings.base_currency if settings is not None else BASE_CURRENCY


def resolve_fx_rate(
    db: Session,
    *,
    from_currency: str,
    on_date: date | None = None,
    to_currency: str | None = None,
) -> Decimal:
    base = to_currency or get_base_currency(db)
    source = from_currency.upper()
    target = base.upper()
    if source == target:
        return Decimal("1")

    effective = on_date or date.today()
    rate = db.scalar(
        select(FxRate)
        .where(
            FxRate.from_currency == source,
            FxRate.to_currency == target,
            FxRate.effective_date <= effective,
        )
        .order_by(FxRate.effective_date.desc())
        .limit(1)
    )
    if rate is None:
        raise ProTrackValidationError(
            f"No FX rate found for {source} → {target} on or before {effective.isoformat()}"
        )
    return Decimal(str(rate.rate))


def to_base_amount(
    db: Session,
    *,
    amount: Decimal,
    currency_code: str,
    on_date: date | None = None,
) -> tuple[Decimal, Decimal, date]:
    fx_date = on_date or date.today()
    rate = resolve_fx_rate(db, from_currency=currency_code, on_date=fx_date)
    base_amount = (Decimal(str(amount)) * rate).quantize(Decimal("0.01"))
    return base_amount, rate, fx_date
