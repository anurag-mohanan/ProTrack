"""Phase 5 — what-if cash/financing + financial health composition."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

from app.models.finance import Quote, QuoteInvoiceLine, QuotePaymentLine, QuoteRevision
from app.models.models import Customer, Team
from app.services.finance.financial_health_service import build_financial_health
from app.services.finance.what_if_calculator import compute_what_if
from app.services.finance.treasury_service import create_loan, upsert_cash_position


def test_what_if_cash_ending_and_runway():
    result = compute_what_if(
        {
            "expected_projects": 2,
            "average_project_value": 500000,
            "win_rate_percent": 100,
            "pipeline_value": 0,
            "use_pipeline": False,
            "headcount": 2,
            "planned_hires": 0,
            "expected_attrition": 0,
            "working_days": 20,
            "hours_per_day": 8,
            "utilization_percent": 50,
            "average_cost_per_hour": 100,
            "other_costs": 10000,
            "cost_increase_percent": 0,
            "average_hours_per_project": 10,
            "margin_target_percent": 10,
            "opening_cash": 100000,
            "collections_realization_percent": 80,
            "extra_loan_emi_monthly": 5000,
            "od_interest_monthly": 1000,
            "investment_income_monthly": 2000,
            "one_time_capex_cash": 10000,
            "minimum_cash_reserve": 20000,
        }
    )
    # available 320; productive 160; labor 16000; other 10000; total_cost 26000
    assert result["expected_revenue"] == 1000000.0
    assert result["expected_collections"] == 800000.0
    assert result["cash_inflows"] == 802000.0
    assert result["total_cost"] == 26000.0
    assert result["cash_outflows"] == 42000.0
    assert result["net_cash_flow"] == 760000.0
    assert result["ending_cash"] == 860000.0
    assert result["cash_status"] == "cash_generative"
    assert result["scenario_runway_months"] is None


def test_what_if_burning_runway_warning():
    result = compute_what_if(
        {
            "expected_projects": 0,
            "average_project_value": 100000,
            "win_rate_percent": 50,
            "pipeline_value": 0,
            "use_pipeline": False,
            "headcount": 5,
            "planned_hires": 0,
            "expected_attrition": 0,
            "working_days": 20,
            "hours_per_day": 8,
            "utilization_percent": 80,
            "average_cost_per_hour": 1000,
            "other_costs": 50000,
            "cost_increase_percent": 0,
            "average_hours_per_project": 40,
            "margin_target_percent": 0,
            "opening_cash": 100000,
            "collections_realization_percent": 100,
            "extra_loan_emi_monthly": 20000,
            "od_interest_monthly": 5000,
            "investment_income_monthly": 0,
            "one_time_capex_cash": 0,
            "minimum_cash_reserve": 50000,
        }
    )
    assert result["cash_status"] == "burning"
    assert result["scenario_runway_months"] is not None
    assert result["scenario_runway_months"] < 3
    assert any("runway" in w.lower() for w in result["warnings"])
    assert any("reserve" in w.lower() for w in result["warnings"])


def test_financial_health_composes_indicators(session):
    upsert_cash_position(
        session,
        {"as_of_date": date(2026, 7, 1), "bank_balance": 800000, "cash_balance": 0},
    )
    create_loan(
        session,
        {
            "lender_name": "Health Bank",
            "name": "P5 Term Loan",
            "original_principal": 200000,
            "outstanding_principal": 150000,
            "emi_amount": 15000,
            "interest_rate_percent": 10,
            "start_date": date(2026, 1, 1),
        },
    )
    team = Team(id=uuid.uuid4(), name="Health Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Health Customer",
        code=f"H{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"H-{uuid.uuid4().hex[:6]}",
        currency_code="INR",
        is_active=True,
        is_invoiced=True,
        invoiced_date=date(2026, 5, 10),
    )
    session.add(quote)
    session.flush()
    session.add(
        QuoteRevision(
            id=uuid.uuid4(),
            quote_id=quote.id,
            version=1,
            revision="A",
            quoted_hours=Decimal("10"),
            estimated_cost=Decimal("0"),
            quoted_revenue=Decimal("200000"),
            margin=Decimal("200000"),
            margin_percent=Decimal("100"),
            base_estimated_cost_inr=Decimal("0"),
            base_quoted_revenue_inr=Decimal("200000"),
            fx_rate=Decimal("1"),
            fx_date=date(2026, 5, 1),
        )
    )
    session.add(
        QuoteInvoiceLine(
            quote_id=quote.id,
            amount=Decimal("200000"),
            line_date=date(2026, 5, 10),
            notes="P5 invoice",
        )
    )
    session.add(
        QuotePaymentLine(
            quote_id=quote.id,
            amount=Decimal("120000"),
            line_date=date(2026, 6, 15),
            notes="P5 payment",
        )
    )
    session.commit()

    health = build_financial_health(session, today=date(2026, 7, 20))
    assert health["overall_status"] in {"healthy", "watch", "critical"}
    keys = {i["key"] for i in health["indicators"]}
    assert keys == {
        "cash_runway",
        "collections_vs_turnover",
        "receivables",
        "debt_od",
        "liquidity_buffer",
    }
    assert health["treasury_snapshot"]["active_loan_emi_monthly"] == Decimal("15000.00")
    assert health["what_if_seed"]["opening_cash"] == 800000.0
    assert health["what_if_seed"]["extra_loan_emi_monthly"] == 15000.0
    assert any("invoice date" in n.lower() for n in health["accounting_notes"])


def test_finance_health_api(client, auth_headers, session):
    upsert_cash_position(
        session,
        {"as_of_date": date(2026, 7, 1), "bank_balance": 250000, "cash_balance": 0},
    )
    session.commit()
    res = client.get("/api/v1/finance/health", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "indicators" in body
    assert body["overall_status"] in {"healthy", "watch", "critical"}
    assert "what_if_seed" in body
