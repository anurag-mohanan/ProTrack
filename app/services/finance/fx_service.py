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


def _lookup_rate(
    db: Session, *, from_currency: str, to_currency: str, on_date: date
) -> FxRate | None:
    return db.scalar(
        select(FxRate)
        .where(
            FxRate.from_currency == from_currency,
            FxRate.to_currency == to_currency,
            FxRate.effective_date <= on_date,
        )
        .order_by(FxRate.effective_date.desc())
        .limit(1)
    )


def resolve_fx_rate(
    db: Session,
    *,
    from_currency: str,
    on_date: date | None = None,
    to_currency: str | None = None,
    fetch_live: bool = True,
) -> Decimal:
    """Resolve currency → base rate for ``on_date``.

    When ``fetch_live`` is True (default), missing/stale seed rates are refreshed from
    the live market feed and stored as a dated ``fx_rates`` row. Callers still lock the
    returned rate onto each money row at write time — later refreshes never rewrite history.
    """
    base = to_currency or get_base_currency(db)
    source = from_currency.upper()
    target = base.upper()
    if source == target:
        return Decimal("1")

    effective = on_date or date.today()
    rate_row = _lookup_rate(db, from_currency=source, to_currency=target, on_date=effective)

    if fetch_live:
        from app.services.finance.fx_live_service import (
            ensure_live_rate,
            live_fx_enabled,
            rate_is_stale_seed_only,
        )

        if live_fx_enabled():
            needs = rate_row is None or rate_is_stale_seed_only(
                db, from_currency=source, to_currency=target, on_date=effective
            )
            if needs:
                try:
                    ensure_live_rate(
                        db, from_currency=source, to_currency=target, on_date=effective
                    )
                    db.flush()
                    rate_row = _lookup_rate(
                        db, from_currency=source, to_currency=target, on_date=effective
                    )
                except Exception:
                    # Keep last known DB rate if live feed is unreachable.
                    pass

    if rate_row is None:
        raise ProTrackValidationError(
            f"No FX rate found for {source} → {target} on or before {effective.isoformat()}"
        )
    return Decimal(str(rate_row.rate))


def to_base_amount(
    db: Session,
    *,
    amount: Decimal,
    currency_code: str,
    on_date: date | None = None,
) -> tuple[Decimal, Decimal, date]:
    """Convert ``amount`` to base currency and return (base_amount, locked_rate, fx_date).

    ``fx_date`` is the posting date used for lookup (quote date, purchase date, etc.).
    The rate is snapshotted by the caller onto the money row and must not be recomputed later.
    """
    fx_date = on_date or date.today()
    rate = resolve_fx_rate(db, from_currency=currency_code, on_date=fx_date)
    base_amount = (Decimal(str(amount)) * rate).quantize(Decimal("0.01"))
    return base_amount, rate, fx_date
