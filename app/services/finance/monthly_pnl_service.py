"""
Monthly P&L for the company financial year.

Turnover: invoice dates (fy_turnover).
Costs: salary + OpEx run-rate at month-end; finance interest by payment/charge date.
Does NOT treat loan principal, OD drawdown, or investment purchases as P&L expense.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import CostNature, ExpensePaidBy
from app.models.finance import (
    Expense,
    FinanceInvestmentIncome,
    FinanceLoanRepayment,
    FinanceOdInterestCharge,
    Quote,
    QuoteInvoiceLine,
)
from app.services.finance.cash_flow_forecast_service import (
    _investment_income_in_month,
    _od_interest_in_month,
    _scheduled_loan_outflow,
)
from app.services.finance.fy_calendar_service import (
    fy_month_windows,
    resolve_fy_context,
)
from app.services.finance.fy_turnover_service import build_fy_turnover_control
from app.services.finance.dashboard_service import (
    _expense_sum,
    _salary_for_team,
    _salary_for_users,
)


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _capex_in_month(
    db: Session,
    *,
    team_id: UUID | None,
    month_start: date,
    month_end: date,
    fy_start: date,
) -> Decimal:
    """CapEx expense run-rate attributed to the month (cash/asset — shown separately on P&L)."""
    from app.services.finance.dashboard_service import _expense_sum

    return _expense_sum(
        db,
        team_id=team_id,
        paid_by=ExpensePaidBy.prosohm,
        nature=CostNature.capex,
        fy_start=fy_start,
        as_of=month_end,
    )


def build_monthly_pnl(
    db: Session,
    *,
    team_id: UUID | None = None,
    today: date | None = None,
    fy_start_year: int | None = None,
) -> dict:
    today = today or date.today()
    ctx = resolve_fy_context(db, today=today, fy_start_year=fy_start_year)
    fy_start: date = ctx["fy_start"]
    windows = fy_month_windows(fy_start)
    turnover = build_fy_turnover_control(
        db, team_id=team_id, today=today, fy_start_year=fy_start_year
    )
    months_t = {m["index"]: m for m in turnover.get("months") or []}

    rows: list[dict] = []
    for window in windows:
        idx = window["index"]
        month_end = window["month_end"]
        month_start = window["month_start"]
        trow = months_t.get(idx) or {}
        rev = _d(trow.get("turnover_inr"))

        if team_id is not None:
            salary = _salary_for_team(db, team_id, as_of=month_end)
        else:
            salary = _salary_for_users(db, None, as_of=month_end)
        opex = _expense_sum(
            db,
            team_id=team_id,
            paid_by=ExpensePaidBy.prosohm,
            nature=CostNature.opex,
            fy_start=fy_start,
            as_of=month_end,
        )
        capex = _capex_in_month(
            db, team_id=team_id, month_start=month_start, month_end=month_end, fy_start=fy_start
        )
        _, _, loan_interest = _scheduled_loan_outflow(db, month_start, month_end)
        # For P&L past months, only use recorded interest (not EMI estimates).
        if month_end < today.replace(day=1):
            recorded = db.scalars(
                select(FinanceLoanRepayment).where(
                    FinanceLoanRepayment.payment_date >= month_start,
                    FinanceLoanRepayment.payment_date <= month_end,
                )
            ).all()
            loan_interest = sum((_d(r.interest_amount) for r in recorded), Decimal("0.00"))

        od_interest = _od_interest_in_month(db, month_start, month_end)
        finance_cost = (loan_interest + od_interest).quantize(Decimal("0.01"))
        other_income = _investment_income_in_month(db, month_start, month_end)

        direct_cost = (salary + opex).quantize(Decimal("0.01"))
        gross = (rev - direct_cost).quantize(Decimal("0.01"))
        margin = (
            (gross / rev * Decimal("100")).quantize(Decimal("0.01")) if rev > 0 else Decimal("0.00")
        )
        # CapEx shown separately; not auto-expensed into gross. Net includes finance − income.
        # CapEx cash/asset: listed but only one-time/run-rate as "capex_expense" below net ops.
        operating_profit = (gross - finance_cost + other_income).quantize(Decimal("0.01"))
        net = (operating_profit - capex).quantize(Decimal("0.01"))

        rows.append(
            {
                "index": idx,
                "label": window["label"],
                "short_label": window["short_label"],
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "is_elapsed": bool(trow.get("is_elapsed")),
                "is_current_month": bool(trow.get("is_current_month")),
                "turnover_inr": rev,
                "salary_cost_inr": salary.quantize(Decimal("0.01")),
                "operating_opex_inr": opex,
                "direct_cost_inr": direct_cost,
                "gross_profit_inr": gross,
                "gross_margin_percent": margin,
                "finance_cost_inr": finance_cost,
                "loan_interest_inr": _d(loan_interest),
                "od_interest_inr": od_interest,
                "other_income_inr": other_income,
                "capex_inr": capex,
                "operating_profit_inr": operating_profit,
                "net_profit_inr": net,
            }
        )

    fytd = [r for r in rows if r["is_elapsed"]]
    fytd_turnover = sum((_d(r["turnover_inr"]) for r in fytd), Decimal("0.00"))
    fytd_gross = sum((_d(r["gross_profit_inr"]) for r in fytd), Decimal("0.00"))
    fytd_net = sum((_d(r["net_profit_inr"]) for r in fytd), Decimal("0.00"))

    return {
        "fy_label": ctx["fy_label"],
        "fy_start": fy_start.isoformat(),
        "fy_end": ctx["fy_end"].isoformat(),
        "as_of": today.isoformat(),
        "months": rows,
        "fytd": {
            "turnover_inr": fytd_turnover.quantize(Decimal("0.01")),
            "gross_profit_inr": fytd_gross.quantize(Decimal("0.01")),
            "net_profit_inr": fytd_net.quantize(Decimal("0.01")),
            "gross_margin_percent": (
                (fytd_gross / fytd_turnover * Decimal("100")).quantize(Decimal("0.01"))
                if fytd_turnover > 0
                else Decimal("0.00")
            ),
        },
        "method_notes": {
            "turnover": "Invoice line dates (P&L recognition). Not payment dates.",
            "direct_cost": "Salary + Prosohm OpEx monthly run-rate at month-end.",
            "finance_cost": "Loan interest + OD interest by payment/charge date. Principal excluded.",
            "other_income": "Investment income by income_date.",
            "capex": (
                "CapEx expense run-rate (nature=capex). Purchase is primarily cash + asset; "
                "shown separately so it is not confused with operating OpEx."
            ),
            "net_profit": "Gross − finance + other income − CapEx run-rate.",
        },
    }


def drilldown_monthly_pnl_line(
    db: Session,
    *,
    month_index: int,
    line: str,
    team_id: UUID | None = None,
    fy_start_year: int | None = None,
    today: date | None = None,
) -> dict:
    """Return contributing rows for a monthly P&L line (click-through)."""
    today = today or date.today()
    ctx = resolve_fy_context(db, today=today, fy_start_year=fy_start_year)
    fy_start: date = ctx["fy_start"]
    windows = fy_month_windows(fy_start)
    if month_index < 0 or month_index > 11:
        return {"error": "month_index must be 0–11", "items": []}
    window = windows[month_index]
    month_start = window["month_start"]
    month_end = window["month_end"]
    line_key = (line or "").strip().lower()

    items: list[dict] = []
    total = Decimal("0.00")

    if line_key in {"turnover", "revenue"}:
        stmt = (
            select(QuoteInvoiceLine, Quote)
            .join(Quote, Quote.id == QuoteInvoiceLine.quote_id)
            .where(
                Quote.is_active.is_(True),
                QuoteInvoiceLine.line_date >= month_start,
                QuoteInvoiceLine.line_date <= month_end,
            )
        )
        if team_id is not None:
            stmt = stmt.where(Quote.team_id == team_id)
        for inv, quote in db.execute(stmt).all():
            amt = _d(inv.amount)
            total += amt
            items.append(
                {
                    "id": str(inv.id),
                    "label": f"{quote.tool_number} · invoice {inv.line_date.isoformat()}",
                    "amount_inr": amt,
                    "date": inv.line_date.isoformat(),
                    "quote_id": str(quote.id),
                    "project_id": str(quote.project_id) if quote.project_id else None,
                }
            )
        title = "Turnover — invoice lines"
        explanation = "Each invoice line dated in this month contributes to turnover."

    elif line_key in {"finance", "finance_cost", "interest"}:
        for row in db.scalars(
            select(FinanceLoanRepayment)
            .where(
                FinanceLoanRepayment.payment_date >= month_start,
                FinanceLoanRepayment.payment_date <= month_end,
            )
            .options(selectinload(FinanceLoanRepayment.loan))
        ).all():
            amt = _d(row.interest_amount)
            if amt <= 0:
                continue
            total += amt
            items.append(
                {
                    "id": str(row.id),
                    "label": f"Loan interest · {row.loan.name if row.loan else row.loan_id}",
                    "amount_inr": amt,
                    "date": row.payment_date.isoformat(),
                    "principal_amount": _d(row.principal_amount),
                    "note": "Principal reduces debt; only interest is P&L expense.",
                }
            )
        for row in db.scalars(
            select(FinanceOdInterestCharge)
            .where(
                FinanceOdInterestCharge.charge_date >= month_start,
                FinanceOdInterestCharge.charge_date <= month_end,
            )
            .options(selectinload(FinanceOdInterestCharge.facility))
        ).all():
            amt = _d(row.amount)
            total += amt
            items.append(
                {
                    "id": str(row.id),
                    "label": f"OD interest · {row.facility.name if row.facility else row.facility_id}",
                    "amount_inr": amt,
                    "date": row.charge_date.isoformat(),
                }
            )
        title = "Finance cost — interest"
        explanation = "Loan/OD interest only. Principal and OD utilization are not P&L expenses."

    elif line_key in {"opex", "operating_opex", "salary", "direct_cost"}:
        from app.services.finance.dashboard_service import _expense_monthly_amount
        from app.services.finance.employment_cost import expense_month_factor

        stmt = select(Expense).where(
            Expense.is_active.is_(True),
            Expense.purchase_date.is_not(None),
            Expense.paid_by == ExpensePaidBy.prosohm,
            Expense.nature == CostNature.opex,
        )
        if team_id is not None:
            stmt = stmt.where(Expense.team_id == team_id)
        for expense in db.scalars(stmt).all():
            factor = expense_month_factor(expense, as_of=month_end)
            if factor <= 0:
                continue
            if expense.purchase_date and expense.purchase_date < fy_start:
                from app.models.enums import CostFrequency

                if expense.frequency == CostFrequency.one_time:
                    continue
            amt = (_expense_monthly_amount(expense) * factor).quantize(Decimal("0.01"))
            total += amt
            items.append(
                {
                    "id": str(expense.id),
                    "label": expense.name,
                    "amount_inr": amt,
                    "date": (expense.purchase_date or month_end).isoformat(),
                    "nature": expense.nature.value,
                    "asset_id": str(expense.asset_id) if getattr(expense, "asset_id", None) else None,
                }
            )
        if line_key == "salary":
            salary_amt = (
                _salary_for_team(db, team_id, as_of=month_end)
                if team_id is not None
                else _salary_for_users(db, None, as_of=month_end)
            )
            items = [
                {
                    "id": "salary-run-rate",
                    "label": "Salary run-rate (People costs)",
                    "amount_inr": salary_amt,
                    "date": month_end.isoformat(),
                }
            ]
            total = _d(salary_amt)
            title = "Salary cost"
            explanation = "Monthly salary run-rate from employee cost profiles."
        else:
            title = "Operating OpEx"
            explanation = "Active Prosohm OpEx lines contributing to this month's run-rate."

    elif line_key in {"other_income", "income"}:
        for row in db.scalars(
            select(FinanceInvestmentIncome)
            .where(
                FinanceInvestmentIncome.income_date >= month_start,
                FinanceInvestmentIncome.income_date <= month_end,
            )
            .options(selectinload(FinanceInvestmentIncome.investment))
        ).all():
            amt = _d(row.amount)
            total += amt
            items.append(
                {
                    "id": str(row.id),
                    "label": f"Investment income · {row.investment.name if row.investment else row.investment_id}",
                    "amount_inr": amt,
                    "date": row.income_date.isoformat(),
                }
            )
        title = "Other income"
        explanation = "Investment income received in this month."

    elif line_key == "capex":
        from app.services.finance.dashboard_service import _expense_monthly_amount
        from app.services.finance.employment_cost import expense_month_factor
        from app.models.enums import CostFrequency

        stmt = select(Expense).where(
            Expense.is_active.is_(True),
            Expense.purchase_date.is_not(None),
            Expense.paid_by == ExpensePaidBy.prosohm,
            Expense.nature == CostNature.capex,
        )
        if team_id is not None:
            stmt = stmt.where(Expense.team_id == team_id)
        for expense in db.scalars(stmt).all():
            factor = expense_month_factor(expense, as_of=month_end)
            if factor <= 0:
                continue
            if expense.purchase_date and expense.purchase_date < fy_start:
                if expense.frequency == CostFrequency.one_time:
                    continue
            amt = (_expense_monthly_amount(expense) * factor).quantize(Decimal("0.01"))
            total += amt
            items.append(
                {
                    "id": str(expense.id),
                    "label": expense.name,
                    "amount_inr": amt,
                    "date": (expense.purchase_date or month_end).isoformat(),
                    "asset_id": str(expense.asset_id) if getattr(expense, "asset_id", None) else None,
                    "note": "CapEx is cash + asset; not automatic operating OpEx.",
                }
            )
        title = "CapEx"
        explanation = "CapEx expense lines (optionally linked to IT assets)."

    else:
        return {
            "month_index": month_index,
            "label": window["label"],
            "line": line_key,
            "title": "Unknown line",
            "explanation": "Supported: turnover, salary, opex, finance, other_income, capex.",
            "total_inr": Decimal("0.00"),
            "items": [],
        }

    return {
        "month_index": month_index,
        "label": window["label"],
        "line": line_key,
        "title": title,
        "explanation": explanation,
        "total_inr": total.quantize(Decimal("0.01")),
        "items": items,
    }


def list_capex_asset_links(db: Session, *, team_id: UUID | None = None) -> dict:
    """CapEx expenses with optional IT asset links + unmatched org assets with purchase cost."""
    from app.models.it_operations import Asset

    stmt = select(Expense).where(
        Expense.is_active.is_(True),
        Expense.nature == CostNature.capex,
    )
    if team_id is not None:
        stmt = stmt.where(Expense.team_id == team_id)
    expenses = list(db.scalars(stmt.order_by(Expense.purchase_date.desc())).all())

    linked = []
    unlinked = []
    for exp in expenses:
        row = {
            "expense_id": str(exp.id),
            "name": exp.name,
            "amount_inr": _d(exp.base_amount_inr or exp.amount),
            "purchase_date": exp.purchase_date.isoformat() if exp.purchase_date else None,
            "asset_id": str(exp.asset_id) if getattr(exp, "asset_id", None) else None,
        }
        if row["asset_id"]:
            asset = db.get(Asset, exp.asset_id)
            row["asset_number"] = asset.asset_number if asset else None
            row["asset_description"] = asset.description if asset else None
            linked.append(row)
        else:
            unlinked.append(row)

    assets = list(
        db.scalars(
            select(Asset)
            .where(
                Asset.is_deleted.is_(False),
                Asset.purchased_by == "organization",
                Asset.purchase_cost.is_not(None),
            )
            .order_by(Asset.purchase_date.desc())
            .limit(100)
        ).all()
    )
    return {
        "linked_capex": linked,
        "unlinked_capex": unlinked,
        "organization_assets": [
            {
                "asset_id": str(a.id),
                "asset_number": a.asset_number,
                "description": a.description,
                "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
                "purchase_cost": _d(a.purchase_cost),
            }
            for a in assets
        ],
        "note": (
            "Link CapEx expenses to IT assets via asset_id. "
            "Do not duplicate asset purchase records."
        ),
    }
