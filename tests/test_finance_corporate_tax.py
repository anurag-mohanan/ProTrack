"""Corporate tax on finance Overview / Team P&L."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.models.finance import CompanyFinanceSettings
from app.services.finance.dashboard_service import _after_tax_net


def test_after_tax_net_helper_default_30_percent():
    after_tax, margin = _after_tax_net(
        Decimal("100000.00"), Decimal("200000.00"), Decimal("30.00")
    )
    assert after_tax == Decimal("70000.00")
    assert margin == Decimal("35.00")


def test_after_tax_net_helper_zero_tax_equals_pre_tax():
    after_tax, margin = _after_tax_net(
        Decimal("100000.00"), Decimal("200000.00"), Decimal("0.00")
    )
    assert after_tax == Decimal("100000.00")
    assert margin == Decimal("50.00")


def test_dashboard_default_corporate_tax_30(client, auth_headers):
    settings = client.get("/api/v1/finance/settings", headers=auth_headers)
    assert settings.status_code == 200
    assert Decimal(str(settings.json()["corporate_tax_percent"])) == Decimal("30")

    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert dash.status_code == 200
    body = dash.json()
    profit = body["profitability"]
    assert Decimal(str(profit["corporate_tax_percent"])) == Decimal("30")

    pre_tax = Decimal(str(profit["profit_forecast"]))
    after_tax = Decimal(str(profit["after_tax_net_profit"]))
    expected = (pre_tax * Decimal("0.70")).quantize(Decimal("0.01"))
    assert after_tax == expected

    for row in body.get("by_team") or []:
        net = Decimal(str(row["net_profit_inr"]))
        row_after = Decimal(str(row["after_tax_net_profit_inr"]))
        assert row_after == (net * Decimal("0.70")).quantize(Decimal("0.01"))


def test_dashboard_zero_tax_equals_pre_tax(client, auth_headers, session):
    patch = client.patch(
        "/api/v1/finance/settings",
        headers=auth_headers,
        json={"corporate_tax_percent": 0},
    )
    assert patch.status_code == 200
    assert Decimal(str(patch.json()["corporate_tax_percent"])) == Decimal("0")

    persisted = session.scalar(
        select(CompanyFinanceSettings).where(CompanyFinanceSettings.is_active.is_(True))
    )
    assert persisted is not None
    assert Decimal(str(persisted.corporate_tax_percent)) == Decimal("0")

    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    profit = dash["profitability"]
    assert Decimal(str(profit["corporate_tax_percent"])) == Decimal("0")
    assert Decimal(str(profit["after_tax_net_profit"])) == Decimal(
        str(profit["profit_forecast"])
    )
    assert Decimal(str(profit["after_tax_net_margin_percent"])) == Decimal(
        str(profit["net_margin"])
    )


def test_corporate_tax_settings_patch_persists(client, auth_headers):
    patched = client.patch(
        "/api/v1/finance/settings",
        headers=auth_headers,
        json={"corporate_tax_percent": 25},
    )
    assert patched.status_code == 200
    assert Decimal(str(patched.json()["corporate_tax_percent"])) == Decimal("25")

    again = client.get("/api/v1/finance/settings", headers=auth_headers)
    assert again.status_code == 200
    assert Decimal(str(again.json()["corporate_tax_percent"])) == Decimal("25")

    dash = client.get("/api/v1/finance/dashboard", headers=auth_headers).json()
    profit = dash["profitability"]
    assert Decimal(str(profit["corporate_tax_percent"])) == Decimal("25")
    pre_tax = Decimal(str(profit["profit_forecast"]))
    after_tax = Decimal(str(profit["after_tax_net_profit"]))
    assert after_tax == (pre_tax * Decimal("0.75")).quantize(Decimal("0.01"))
