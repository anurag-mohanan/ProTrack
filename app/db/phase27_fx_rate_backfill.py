"""Phase 27 — Ensure FX rates exist early enough for FY-start effective dates.

Seed rates historically used date.today(), so commercial terms / expenses dated
at FY start (e.g. 1 Apr) failed USD→INR conversion before the seed day.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.models.finance import FxRate

# Anchor before any India FY the product is likely to plan against.
SEED_FX_EFFECTIVE = date(2020, 4, 1)

DEFAULT_RATES_TO_INR: list[tuple[str, Decimal]] = [
    ("USD", Decimal("83.50")),
    ("EUR", Decimal("90.00")),
    ("GBP", Decimal("105.00")),
    ("AED", Decimal("22.75")),
    ("SGD", Decimal("62.00")),
    ("JPY", Decimal("0.55")),
]


def ensure_phase27_fx_rate_backfill(engine: Engine) -> None:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        for code, rate in DEFAULT_RATES_TO_INR:
            usable = session.scalar(
                select(FxRate)
                .where(
                    FxRate.from_currency == code,
                    FxRate.to_currency == "INR",
                    FxRate.effective_date <= SEED_FX_EFFECTIVE,
                )
                .limit(1)
            )
            if usable is not None:
                continue
            exact = session.scalar(
                select(FxRate).where(
                    FxRate.from_currency == code,
                    FxRate.to_currency == "INR",
                    FxRate.effective_date == SEED_FX_EFFECTIVE,
                )
            )
            if exact is None:
                session.add(
                    FxRate(
                        from_currency=code,
                        to_currency="INR",
                        rate=rate,
                        effective_date=SEED_FX_EFFECTIVE,
                        source="seed_backfill",
                    )
                )
        session.commit()
    finally:
        session.close()
