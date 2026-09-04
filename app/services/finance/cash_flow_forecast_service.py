"""
Cash-flow forecast and cash runway.

Cash flow uses payment dates / expected payment timing — NOT invoice dates.
P&L turnover remains invoice-date based (see fy_turnover_service).
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CostNature, ExpensePaidBy, FinanceLoanStatus
from app.models.finance import FinanceInvestmentIncome, FinanceLoanRepayment, FinanceOdInterestCharge
from app.services.finance.fy_calendar_service import fy_month_windows, resolve_fy_context
from app.services.finance.fy_turnover_service import build_fy_turnover_control
from app.services.finance.treasury_service import latest_cash_position, list_loans


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _add_months(start: date, offset: int) -> date:
    """Return the 1st of the month `offset` months after start's month."""
    y = start.year + (start.month - 1 + offset) // 12
    m = (start.month - 1 + offset) % 12 + 1
    return date(y, m, 1)


def _operating_outflow_monthly(db: Session, *, team_id: UUID | None, as_of: date) -> Decimal:
    from app.services.finance.dashboard_service import (
        _expense_sum,
        _salary_for_team,
        _salary_for_users,
    )
    from app.services.finance.fy_calendar_service import company_fy_start_month
    from app.services.finance.annual_plan_service import current_fy_start

    fy_start = current_fy_start(as_of, fy_start_month=company_fy_start_month(db))
    if team_id is not None:
        salary = _salary_for_team(db, team_id, as_of=as_of)
    else:
        salary = _salary_for_users(db, None, as_of=as_of)
    opex = _expense_sum(
        db,
        team_id=team_id,
        paid_by=ExpensePaidBy.prosohm,
        nature=CostNature.opex,
        fy_start=fy_start,
        as_of=as_of,
    )
    return (salary + opex).quantize(Decimal("0.01"))


def _scheduled_loan_outflow(db: Session, month_start: date, month_end: date) -> tuple[Decimal, Decimal, Decimal]:
    """
    Returns (total_cash, principal, interest) expected/recorded in the month.

    Past/current: sum recorded repayments.
    Future: use EMI amount when next_payment_date falls in month (or EMI as estimate).
    """
    cash = Decimal("0.00")
    principal = Decimal("0.00")
    interest = Decimal("0.00")
    today = date.today()

    repayments = db.scalars(
        select(FinanceLoanRepayment).where(
            FinanceLoanRepayment.payment_date >= month_start,
            FinanceLoanRepayment.payment_date <= month_end,
        )
    ).all()
    for row in repayments:
        cash += _d(row.total_amount)
        principal += _d(row.principal_amount)
        interest += _d(row.interest_amount)

    if month_end >= today:
        for loan in list_loans(db):
            if loan.status != FinanceLoanStatus.active:
                continue
            emi = _d(loan.emi_amount)
            if emi <= 0:
                continue
            nxt = loan.next_payment_date
            # Estimate one EMI in future months when no repayment already booked
            if month_start > today or (nxt and month_start <= nxt <= month_end):
                already = any(
                    month_start <= r.payment_date <= month_end and r.loan_id == loan.id
                    for r in repayments
                )
                if not already:
                    # Without a known interest split, treat EMI as cash; interest unknown → 0
                    # (user should record repayments for accurate P&L interest).
                    rate = _d(loan.interest_rate_percent)
                    est_interest = (
                        (_d(loan.outstanding_principal) * rate / Decimal("1200")).quantize(
                            Decimal("0.01")
                        )
                        if rate > 0
                        else Decimal("0.00")
                    )
                    est_principal = max(Decimal("0.00"), emi - est_interest)
                    cash += emi
                    principal += est_principal
                    interest += est_interest

    return cash.quantize(Decimal("0.01")), principal.quantize(Decimal("0.01")), interest.quantize(
        Decimal("0.01")
    )


def _od_interest_in_month(db: Session, month_start: date, month_end: date) -> Decimal:
    rows = db.scalars(
        select(FinanceOdInterestCharge).where(
            FinanceOdInterestCharge.charge_date >= month_start,
            FinanceOdInterestCharge.charge_date <= month_end,
        )
    ).all()
    return sum((_d(r.amount) for r in rows), Decimal("0.00")).quantize(Decimal("0.01"))


def _investment_income_in_month(db: Session, month_start: date, month_end: date) -> Decimal:
    rows = db.scalars(
        select(FinanceInvestmentIncome).where(
            FinanceInvestmentIncome.income_date >= month_start,
            FinanceInvestmentIncome.income_date <= month_end,
        )
    ).all()
    return sum((_d(r.amount) for r in rows), Decimal("0.00")).quantize(Decimal("0.01"))


def build_cash_runway(
    db: Session,
    *,
    team_id: UUID | None = None,
    today: date | None = None,
) -> dict:
    """
    Cash runway = available cash ÷ average monthly net cash burn.

    Net burn = avg monthly operating outflow − avg monthly cash collected (FY elapsed).
    If net burn ≤ 0, business is cash-generative (no misleading runway months).
    """
    today = today or date.today()
    cash = latest_cash_position(db)
    available = (
        _d(cash.bank_balance) + _d(cash.cash_balance) if cash else Decimal("0.00")
    )
    turnover = build_fy_turnover_control(db, team_id=team_id, today=today)
    elapsed = int(turnover.get("elapsed_months") or 0)
    fytd_cash = _d(turnover.get("fytd_cash_collected_inr"))
    avg_collections = (
        (fytd_cash / Decimal(elapsed)).quantize(Decimal("0.01")) if elapsed > 0 else Decimal("0.00")
    )
    monthly_out = _operating_outflow_monthly(db, team_id=team_id, as_of=today)

    # Include average loan EMI as servicing burden when EMIs exist
    emi_total = sum(
        (_d(loan.emi_amount) for loan in list_loans(db) if loan.status == FinanceLoanStatus.active),
        Decimal("0.00"),
    )
    monthly_outflow = (monthly_out + emi_total).quantize(Decimal("0.01"))
    net_burn = (monthly_outflow - avg_collections).quantize(Decimal("0.01"))

    if not cash:
        status = "missing_cash_position"
        runway_months = None
        message = (
            "Set a manual cash/bank position in Treasury before runway can be calculated."
        )
    elif net_burn <= 0:
        status = "cash_generative"
        runway_months = None
        message = (
            "Average monthly cash collected meets or exceeds operating outflow + loan EMI. "
            "Runway months are not applicable while net cash generation is positive."
        )
    else:
        status = "burning"
        runway_months = (available / net_burn).quantize(Decimal("0.1"))
        message = (
            f"At the current average net burn of {net_burn}/month, "
            f"available cash covers approximately {runway_months} months."
        )

    return {
        "as_of": today.isoformat(),
        "available_cash": available,
        "has_manual_cash_position": cash is not None,
        "cash_as_of_date": cash.as_of_date.isoformat() if cash else None,
        "average_monthly_collections": avg_collections,
        "average_monthly_operating_outflow": monthly_out,
        "average_monthly_loan_emi": emi_total.quantize(Decimal("0.01")),
        "average_monthly_total_outflow": monthly_outflow,
        "average_monthly_net_burn": net_burn,
        "runway_months": runway_months,
        "status": status,
        "message": message,
        "method_notes": {
            "available_cash": "Bank balance + cash balance from the latest manual cash position.",
            "collections": "FYTD cash collected (payment dates) ÷ elapsed FY months.",
            "operating_outflow": "Current monthly salary + Prosohm OpEx run-rate.",
            "loan_emi": "Sum of active loan EMI amounts (cash servicing).",
            "net_burn": "Total outflow − average collections. Positive means cash is being consumed.",
            "runway": "available_cash ÷ net_burn when burning; omitted when cash-generative.",
        },
    }


def build_cash_flow_forecast(
    db: Session,
    *,
    team_id: UUID | None = None,
    today: date | None = None,
    fy_start_year: int | None = None,
    months_ahead: int = 6,
) -> dict:
    """
    Month-by-month cash forecast for the remainder of the FY (or months_ahead).

    Opening = latest cash position (or 0 if unset).
    Historical months: actual payment collections and recorded outflows.
    Future months: average collections, operating run-rate, scheduled EMIs.
    """
    today = today or date.today()
    ctx = resolve_fy_context(db, today=today, fy_start_year=fy_start_year)
    fy_start: date = ctx["fy_start"]
    windows = fy_month_windows(fy_start)
    turnover = build_fy_turnover_control(
        db, team_id=team_id, today=today, fy_start_year=fy_start_year
    )
    months_map = {m["index"]: m for m in turnover.get("months") or []}

    cash = latest_cash_position(db)
    opening = (
        _d(cash.bank_balance) + _d(cash.cash_balance) if cash else Decimal("0.00")
    )
    elapsed = int(turnover.get("elapsed_months") or 0)
    avg_collections = (
        (_d(turnover.get("fytd_cash_collected_inr")) / Decimal(elapsed)).quantize(Decimal("0.01"))
        if elapsed > 0
        else Decimal("0.00")
    )
    op_out = _operating_outflow_monthly(db, team_id=team_id, as_of=today)

    # Start forecast from current FY month index
    current_idx = None
    for w in windows:
        if w["calendar_year"] == today.year and w["calendar_month"] == today.month:
            current_idx = w["index"]
            break
    if current_idx is None:
        current_idx = max(0, elapsed - 1)

    end_idx = min(11, current_idx + max(1, months_ahead) - 1)
    rows: list[dict] = []
    running = opening

    for idx in range(current_idx, end_idx + 1):
        window = windows[idx]
        month_start = window["month_start"]
        month_end = window["month_end"]
        is_future = month_start > today.replace(day=1) if today.day > 1 else month_start > today
        # Treat current month as partial: use actuals where present, else averages
        actual = months_map.get(idx) or {}
        actual_cash = _d(actual.get("cash_collected_inr"))

        if idx < elapsed and actual_cash > 0:
            collections = actual_cash
            collections_source = "actual_payment_lines"
        elif idx < elapsed:
            collections = actual_cash
            collections_source = "actual_payment_lines"
        else:
            collections = avg_collections
            collections_source = "avg_fy_collections"

        loan_cash, loan_principal, loan_interest = _scheduled_loan_outflow(
            db, month_start, month_end
        )
        od_interest = _od_interest_in_month(db, month_start, month_end)
        invest_income = _investment_income_in_month(db, month_start, month_end)

        operating = op_out
        total_in = (collections + invest_income).quantize(Decimal("0.01"))
        total_out = (operating + loan_cash + od_interest).quantize(Decimal("0.01"))
        net = (total_in - total_out).quantize(Decimal("0.01"))
        closing = (running + net).quantize(Decimal("0.01"))

        rows.append(
            {
                "index": idx,
                "label": window["label"],
                "short_label": window["short_label"],
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "opening_cash": running,
                "customer_collections": collections,
                "collections_source": collections_source,
                "investment_income": invest_income,
                "operating_expenses": operating,
                "loan_payments_total": loan_cash,
                "loan_principal": loan_principal,
                "loan_interest": loan_interest,
                "od_interest": od_interest,
                "total_inflows": total_in,
                "total_outflows": total_out,
                "net_cash_flow": net,
                "closing_cash": closing,
                "is_future": is_future or idx >= elapsed,
            }
        )
        running = closing

    runway = build_cash_runway(db, team_id=team_id, today=today)

    return {
        "fy_label": ctx["fy_label"],
        "fy_start": fy_start.isoformat(),
        "fy_end": ctx["fy_end"].isoformat(),
        "as_of": today.isoformat(),
        "opening_cash": opening,
        "has_manual_cash_position": cash is not None,
        "months": rows,
        "runway": runway,
        "method_notes": {
            "opening_cash": "Latest manual bank + cash position (Treasury).",
            "collections": (
                "Actual quote payment line dates for elapsed months; "
                "future months use average FY cash collections."
            ),
            "operating_expenses": "Salary + Prosohm OpEx monthly run-rate (not CapEx / loan principal).",
            "loan_payments": (
                "Recorded repayments in-month, or estimated EMI (interest estimated from rate). "
                "Principal is cash + debt reduction, not P&L expense."
            ),
            "od_interest": "Recorded OD interest charges by charge_date (P&L finance cost + cash).",
            "investment_income": "Recorded investment income by income_date.",
            "separation": (
                "This forecast is cash only. Invoice-date turnover belongs on the P&L, "
                "not in closing cash."
            ),
        },
    }
