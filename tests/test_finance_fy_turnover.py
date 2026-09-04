"""FY turnover / average monthly billing unit tests."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.finance import Quote, QuoteInvoiceLine, QuotePaymentLine, QuoteRevision
from app.models.models import Customer, Team
from app.services.finance.fy_calendar_service import elapsed_fy_months, month_index_for_date
from app.services.finance.fy_turnover_service import build_fy_turnover_control


def test_elapsed_fy_months_includes_current_month():
    fy_start = date(2026, 4, 1)
    fy_end = date(2027, 3, 31)
    assert elapsed_fy_months(fy_start, date(2026, 4, 15), fy_end) == 1
    assert elapsed_fy_months(fy_start, date(2026, 7, 15), fy_end) == 4
    assert elapsed_fy_months(fy_start, date(2027, 3, 31), fy_end) == 12
    assert elapsed_fy_months(fy_start, date(2027, 4, 1), fy_end) == 12


def test_month_index_for_date_april_fy():
    fy_start = date(2026, 4, 1)
    assert month_index_for_date(fy_start, date(2026, 4, 1)) == 0
    assert month_index_for_date(fy_start, date(2026, 7, 15)) == 3
    assert month_index_for_date(fy_start, date(2027, 3, 31)) == 11
    assert month_index_for_date(fy_start, date(2026, 3, 31)) is None


def test_average_monthly_billing_includes_zero_months(session):
    """
    April=100k, May=200k, June=0, July=300k → FYTD 600k / 4 = 150k.
    Payment in August affects cash only, not July turnover.
    """
    team = Team(id=uuid.uuid4(), name="FY Turnover Team", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="FY Turnover Customer",
        code=f"FY{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()

    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"FY-AVG-{uuid.uuid4().hex[:6]}",
        currency_code="INR",
        is_active=True,
        is_invoiced=True,
        invoiced_date=date(2026, 4, 10),
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
            quoted_revenue=Decimal("600000"),
            margin=Decimal("600000"),
            margin_percent=Decimal("100"),
            base_estimated_cost_inr=Decimal("0"),
            base_quoted_revenue_inr=Decimal("600000"),
            fx_rate=Decimal("1"),
            fx_date=date(2026, 4, 1),
        )
    )
    for amount, line_date in (
        (Decimal("100000"), date(2026, 4, 15)),
        (Decimal("200000"), date(2026, 5, 15)),
        (Decimal("300000"), date(2026, 7, 15)),
    ):
        session.add(
            QuoteInvoiceLine(
                quote_id=quote.id,
                amount=amount,
                line_date=line_date,
            )
        )
    session.add(
        QuotePaymentLine(
            quote_id=quote.id,
            amount=Decimal("250000"),
            line_date=date(2026, 8, 10),
        )
    )
    session.commit()

    result = build_fy_turnover_control(
        session,
        team_id=team.id,
        today=date(2026, 7, 20),
        fy_start_year=2026,
    )
    assert result["elapsed_months"] == 4
    assert result["fytd_turnover_inr"] == Decimal("600000.00")
    assert result["average_monthly_billing_inr"] == Decimal("150000.00")
    assert result["zero_billing_months"] == 1
    assert result["months"][0]["turnover_inr"] == Decimal("100000.00")
    assert result["months"][1]["turnover_inr"] == Decimal("200000.00")
    assert result["months"][2]["turnover_inr"] == Decimal("0.00")
    assert result["months"][3]["turnover_inr"] == Decimal("300000.00")
    assert result["months"][4]["cash_collected_inr"] == Decimal("250000.00")
    assert result["fytd_cash_collected_inr"] == Decimal("0.00")

    session.add(
        QuoteInvoiceLine(
            quote_id=quote.id,
            amount=Decimal("400000"),
            line_date=date(2026, 8, 5),
        )
    )
    session.commit()

    result2 = build_fy_turnover_control(
        session,
        team_id=team.id,
        today=date(2026, 8, 20),
        fy_start_year=2026,
    )
    assert result2["elapsed_months"] == 5
    assert result2["fytd_turnover_inr"] == Decimal("1000000.00")
    assert result2["average_monthly_billing_inr"] == Decimal("200000.00")
    assert result2["fytd_cash_collected_inr"] == Decimal("250000.00")
