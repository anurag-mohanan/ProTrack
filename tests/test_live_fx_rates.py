"""Live FX fetch stores dated rates; money rows lock the rate at write time."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from app.models.finance import FxRate
from app.services.finance.fx_live_service import (
    SOURCE_LIVE_OPEN,
    ensure_live_rate,
    refresh_live_fx_rates,
)
from app.services.finance.fx_service import to_base_amount


def test_ensure_live_rate_inserts_dated_row(session, monkeypatch):
    monkeypatch.setenv("PROTRACK_FX_LIVE", "1")
    on_date = date(2026, 7, 24)

    with patch(
        "app.services.finance.fx_live_service.fetch_rate_for_date",
        return_value=(Decimal("86.25000000"), SOURCE_LIVE_OPEN),
    ):
        row = ensure_live_rate(session, from_currency="USD", to_currency="INR", on_date=on_date)
        session.flush()

    assert row is not None
    assert row.rate == Decimal("86.25000000")
    assert row.effective_date == on_date
    assert row.source == SOURCE_LIVE_OPEN


def test_to_base_amount_locks_live_rate_for_posting_date(session, monkeypatch):
    monkeypatch.setenv("PROTRACK_FX_LIVE", "1")
    on_date = date(2026, 7, 20)

    with patch(
        "app.services.finance.fx_live_service.fetch_rate_for_date",
        return_value=(Decimal("85.10000000"), SOURCE_LIVE_OPEN),
    ):
        base, rate, fx_date = to_base_amount(
            session,
            amount=Decimal("1000"),
            currency_code="USD",
            on_date=on_date,
        )
        session.flush()

    assert fx_date == on_date
    assert rate == Decimal("85.10000000")
    assert base == Decimal("85100.00")

    stored = session.scalar(
        select(FxRate).where(
            FxRate.from_currency == "USD",
            FxRate.to_currency == "INR",
            FxRate.effective_date == on_date,
        )
    )
    assert stored is not None
    assert Decimal(str(stored.rate)) == Decimal("85.10000000")


def test_manual_rate_not_overwritten_by_refresh(session, monkeypatch):
    monkeypatch.setenv("PROTRACK_FX_LIVE", "1")
    on_date = date(2026, 7, 24)
    session.add(
        FxRate(
            from_currency="USD",
            to_currency="INR",
            rate=Decimal("99.00000000"),
            effective_date=on_date,
            source="manual",
        )
    )
    session.flush()

    with patch(
        "app.services.finance.fx_live_service.fetch_rate_for_date",
        return_value=(Decimal("86.00000000"), SOURCE_LIVE_OPEN),
    ):
        result = refresh_live_fx_rates(session, on_date=on_date, from_currencies=["USD"])
        session.flush()

    assert result["skipped_manual"] >= 1
    row = session.scalar(
        select(FxRate).where(
            FxRate.from_currency == "USD",
            FxRate.to_currency == "INR",
            FxRate.effective_date == on_date,
        )
    )
    assert Decimal(str(row.rate)) == Decimal("99.00000000")


def test_refresh_fx_rates_api(client, auth_headers, monkeypatch):
    monkeypatch.setenv("PROTRACK_FX_LIVE", "1")
    with patch(
        "app.services.finance.fx_live_service.fetch_rate_for_date",
        return_value=(Decimal("87.50000000"), SOURCE_LIVE_OPEN),
    ):
        resp = client.post(
            "/api/v1/finance/fx-rates/refresh?on_date=2026-07-24",
            headers=auth_headers,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["effective_date"] == "2026-07-24"
    assert body["created"] + body["updated"] >= 1
