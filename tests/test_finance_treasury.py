"""Treasury accounting rules — principal ≠ P&L; interest = finance cost."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from tests.conftest import login


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def test_loan_repayment_splits_principal_and_interest(client):
    headers = login(client, "admin@prosohm.com")

    created = client.post(
        "/api/v1/finance/treasury/loans",
        json={
            "lender_name": "Test Bank",
            "name": "Term loan A",
            "original_principal": 1000000,
            "interest_rate_percent": 12,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    loan_id = created.json()["id"]
    assert _money(created.json()["outstanding_principal"]) == Decimal("1000000.00")

    repaid = client.post(
        f"/api/v1/finance/treasury/loans/{loan_id}/repayments",
        json={
            "payment_date": "2026-07-15",
            "total_amount": 50000,
            "interest_amount": 12000,
            "principal_amount": 38000,
        },
        headers=headers,
    )
    assert repaid.status_code == 201, repaid.text
    body = repaid.json()
    assert _money(body["outstanding_principal"]) == Decimal("962000.00")
    assert _money(body["interest_paid_total"]) == Decimal("12000.00")
    assert _money(body["principal_paid_total"]) == Decimal("38000.00")
    assert len(body["repayments"]) == 1
    row = body["repayments"][0]
    assert _money(row["cash_outflow"]) == Decimal("50000.00")
    assert _money(row["pnl_finance_expense"]) == Decimal("12000.00")
    assert _money(row["debt_reduction"]) == Decimal("38000.00")


def test_od_utilization_and_available(client):
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/finance/treasury/od-facilities",
        json={
            "bank_name": "OD Bank",
            "name": "Working capital OD",
            "sanctioned_limit": 1000000,
            "current_utilization": 400000,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert _money(body["available_limit"]) == Decimal("600000.00")
    assert _money(body["utilization_percent"]) == Decimal("40.00")


def test_investment_is_not_opex_flag(client):
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/finance/treasury/investments",
        json={
            "name": "FD-1",
            "investment_type": "fixed_deposit",
            "amount_invested": 500000,
            "investment_date": date.today().isoformat(),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert _money(body["amount_invested"]) == Decimal("500000.00")
    assert _money(body["current_value"]) == Decimal("500000.00")
    assert "not automatic operating expense" in body["accounting_note"].lower()

    summary = client.get("/api/v1/finance/treasury/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert _money(summary.json()["investments"]["current_value"]) >= Decimal("500000")
