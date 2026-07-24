"""Live market FX fetch — stores dated rows in fx_rates; postings still snapshot at write time."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.finance import Currency, FxRate
from app.services.finance.fx_service import get_base_currency

logger = logging.getLogger(__name__)

# Currencies we keep fresh against company base (INR). Matches seed set + common quote currencies.
DEFAULT_LIVE_FROM = ("USD", "EUR", "GBP", "AED", "SGD", "JPY")

OPEN_ER_API_LATEST = "https://open.er-api.com/v6/latest/{base}"
FRANKFURTER_HISTORICAL = "https://api.frankfurter.app/{on_date}"

SOURCE_LIVE_OPEN = "live:open.er-api"
SOURCE_LIVE_FRANKFURTER = "live:frankfurter"


def live_fx_enabled() -> bool:
    """Live HTTP fetch on by default; disable in tests with PROTRACK_FX_LIVE=0."""
    return os.getenv("PROTRACK_FX_LIVE", "1").strip().lower() not in {"0", "false", "no", "off"}


def _q_rate(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.00000001"))


def _catalog_from_currencies(db: Session, base: str) -> list[str]:
    codes = [
        c.code.upper()
        for c in db.scalars(select(Currency).where(Currency.is_active.is_(True))).all()
        if c.code and c.code.upper() != base.upper()
    ]
    if codes:
        return sorted(set(codes))
    return list(DEFAULT_LIVE_FROM)


def _existing_rate(
    db: Session, *, from_currency: str, to_currency: str, on_date: date
) -> FxRate | None:
    return db.scalar(
        select(FxRate).where(
            FxRate.from_currency == from_currency.upper(),
            FxRate.to_currency == to_currency.upper(),
            FxRate.effective_date == on_date,
        )
    )


def _upsert_rate(
    db: Session,
    *,
    from_currency: str,
    to_currency: str,
    rate: Decimal,
    on_date: date,
    source: str,
) -> FxRate | None:
    """Insert or refresh a live rate for the pair+date. Never overwrites a manual row."""
    existing = _existing_rate(
        db, from_currency=from_currency, to_currency=to_currency, on_date=on_date
    )
    if existing is not None:
        src = (existing.source or "").lower()
        if src == "manual" or src.startswith("manual"):
            return existing
        existing.rate = rate
        existing.source = source
        return existing
    row = FxRate(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        rate=rate,
        effective_date=on_date,
        source=source,
    )
    db.add(row)
    return row


def _fetch_open_er_rate(from_currency: str, to_currency: str) -> Decimal | None:
    """Latest market rate (updates ~daily). to_currency must appear in the response rates map."""
    url = OPEN_ER_API_LATEST.format(base=from_currency.upper())
    with httpx.Client(timeout=12.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    if str(payload.get("result") or "").lower() != "success":
        return None
    rates = payload.get("rates") or {}
    raw = rates.get(to_currency.upper())
    if raw is None:
        return None
    return _q_rate(raw)


def _fetch_frankfurter_rate(
    from_currency: str, to_currency: str, on_date: date
) -> Decimal | None:
    """Historical ECB cross rates for a calendar date (good for past quote / billing dates)."""
    url = FRANKFURTER_HISTORICAL.format(on_date=on_date.isoformat())
    params = {"from": from_currency.upper(), "to": to_currency.upper()}
    with httpx.Client(timeout=12.0) as client:
        resp = client.get(url, params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        payload = resp.json()
    rates = payload.get("rates") or {}
    raw = rates.get(to_currency.upper())
    if raw is None:
        return None
    return _q_rate(raw)


def fetch_rate_for_date(
    from_currency: str, to_currency: str, on_date: date
) -> tuple[Decimal, str] | None:
    """Return (rate, source_tag) for the pair on on_date, or None if unavailable."""
    src = from_currency.upper()
    tgt = to_currency.upper()
    if src == tgt:
        return Decimal("1"), "identity"

    today = date.today()
    # Prefer historical provider for past dates; latest feed for today / near future.
    if on_date < today:
        try:
            rate = _fetch_frankfurter_rate(src, tgt, on_date)
            if rate is not None:
                return rate, SOURCE_LIVE_FRANKFURTER
        except Exception as exc:  # noqa: BLE001 — fall through to open feed
            logger.info("Frankfurter FX fetch failed for %s→%s on %s: %s", src, tgt, on_date, exc)

    try:
        rate = _fetch_open_er_rate(src, tgt)
        if rate is not None:
            # Latest feed is "as of today"; still store under the requested posting date
            # so resolve(effective_date <= on_date) finds a dated row for that write.
            return rate, SOURCE_LIVE_OPEN
    except Exception as exc:  # noqa: BLE001
        logger.warning("Open ER-API FX fetch failed for %s→%s: %s", src, tgt, exc)
    return None


def ensure_live_rate(
    db: Session,
    *,
    from_currency: str,
    to_currency: str | None = None,
    on_date: date | None = None,
) -> FxRate | None:
    """Ensure a dated fx_rates row exists for the posting date; fetch live if missing."""
    if not live_fx_enabled():
        return None
    base = (to_currency or get_base_currency(db)).upper()
    src = from_currency.upper()
    effective = on_date or date.today()
    if src == base:
        return None

    existing = _existing_rate(db, from_currency=src, to_currency=base, on_date=effective)
    if existing is not None:
        return existing

    fetched = fetch_rate_for_date(src, base, effective)
    if fetched is None:
        return None
    rate, source = fetched
    return _upsert_rate(
        db,
        from_currency=src,
        to_currency=base,
        rate=rate,
        on_date=effective,
        source=source,
    )


def refresh_live_fx_rates(
    db: Session,
    *,
    on_date: date | None = None,
    from_currencies: Iterable[str] | None = None,
) -> dict:
    """Pull live rates into fx_rates for the given date (default: today).

    Existing postings keep their locked fx_rate / base_*_inr. New writes pick up
    the refreshed table via resolve_fx_rate → to_base_amount.
    """
    effective = on_date or date.today()
    base = get_base_currency(db).upper()
    if not live_fx_enabled():
        return {
            "effective_date": effective.isoformat(),
            "base_currency": base,
            "created": 0,
            "updated": 0,
            "skipped_manual": 0,
            "failed": [],
        }

    sources = list(from_currencies) if from_currencies else _catalog_from_currencies(db, base)
    created = 0
    updated = 0
    skipped = 0
    failed: list[str] = []

    for code in sources:
        src = str(code).upper()
        if src == base:
            continue
        before = _existing_rate(db, from_currency=src, to_currency=base, on_date=effective)
        fetched = fetch_rate_for_date(src, base, effective)
        if fetched is None:
            failed.append(src)
            continue
        rate, source = fetched
        if before is not None and (before.source or "").lower().startswith("manual"):
            skipped += 1
            continue
        row = _upsert_rate(
            db,
            from_currency=src,
            to_currency=base,
            rate=rate,
            on_date=effective,
            source=source,
        )
        if before is None:
            created += 1
        elif row is not None:
            updated += 1

    db.flush()
    return {
        "effective_date": effective.isoformat(),
        "base_currency": base,
        "created": created,
        "updated": updated,
        "skipped_manual": skipped,
        "failed": failed,
    }


def rate_is_stale_seed_only(
    db: Session, *, from_currency: str, to_currency: str, on_date: date
) -> bool:
    """True when the best rate on/before on_date is only an old seed (no live/manual for that day)."""
    row = db.scalar(
        select(FxRate)
        .where(
            FxRate.from_currency == from_currency.upper(),
            FxRate.to_currency == to_currency.upper(),
            FxRate.effective_date <= on_date,
        )
        .order_by(FxRate.effective_date.desc())
        .limit(1)
    )
    if row is None:
        return True
    if row.effective_date == on_date:
        return False
    src = (row.source or "").lower()
    if src.startswith("live") or src == "manual" or src.startswith("manual"):
        if on_date - row.effective_date <= timedelta(days=3):
            return False
        return True
    return True
