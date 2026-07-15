"""Financial dashboard aggregates (base currency INR) — Finance Rebuild 1."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import BudgetApprovalStatus, CostNature, ExpensePaidBy, TeamBillingPeriod
from app.models.finance import (
    AiForecastPlaceholder,
    Budget,
    EmployeeCostProfile,
    Expense,
    ProjectFinancialSnapshot,
    QuoteRevision,
    TeamCommercialTerms,
)
from app.models.models import Project
from app.services.finance.fx_service import get_base_currency
from app.services.finance.renewal_notifier import list_upcoming_renewals


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _normalize_monthly_fee(amount: Decimal, period: TeamBillingPeriod) -> Decimal:
    if period == TeamBillingPeriod.monthly:
        return amount
    if period == TeamBillingPeriod.quarterly:
        return (amount / Decimal("3")).quantize(Decimal("0.01"))
    if period == TeamBillingPeriod.annual:
        return (amount / Decimal("12")).quantize(Decimal("0.01"))
    return amount


def get_finance_dashboard(db: Session) -> dict:
    base = get_base_currency(db)
    today = date.today()
    revenue = _d(
        db.scalar(select(func.coalesce(func.sum(QuoteRevision.base_quoted_revenue_inr), 0)))
    )
    estimated_cost = _d(
        db.scalar(select(func.coalesce(func.sum(QuoteRevision.base_estimated_cost_inr), 0)))
    )

    prosohm_opex = _d(
        db.scalar(
            select(func.coalesce(func.sum(Expense.base_amount_inr), 0)).where(
                Expense.is_active.is_(True),
                Expense.nature == CostNature.opex,
                Expense.paid_by == ExpensePaidBy.prosohm,
            )
        )
    )
    pass_through_opex = _d(
        db.scalar(
            select(func.coalesce(func.sum(Expense.base_amount_inr), 0)).where(
                Expense.is_active.is_(True),
                Expense.nature == CostNature.opex,
                Expense.paid_by == ExpensePaidBy.customer,
            )
        )
    )
    capex = _d(
        db.scalar(
            select(func.coalesce(func.sum(Expense.base_amount_inr), 0)).where(
                Expense.is_active.is_(True),
                Expense.nature == CostNature.capex,
                Expense.paid_by == ExpensePaidBy.prosohm,
            )
        )
    )
    salary_cost = _d(
        db.scalar(
            select(func.coalesce(func.sum(EmployeeCostProfile.base_monthly_salary_inr), 0)).where(
                EmployeeCostProfile.is_active.is_(True)
            )
        )
    )

    team_terms = db.scalars(
        select(TeamCommercialTerms).where(TeamCommercialTerms.is_active.is_(True))
    ).all()
    team_fee_monthly = Decimal("0.00")
    for term in team_terms:
        if term.effective_from and term.effective_from > today:
            continue
        if term.effective_to and term.effective_to < today:
            continue
        team_fee_monthly += _normalize_monthly_fee(_d(term.base_fee_inr), term.billing_period)

    planning_revenue = revenue + team_fee_monthly
    operating_cost = prosohm_opex + salary_cost
    gross_profit = planning_revenue - estimated_cost
    gross_margin = (gross_profit / planning_revenue * 100) if planning_revenue else Decimal("0.00")
    net_profit = gross_profit - operating_cost
    net_margin = (net_profit / planning_revenue * 100) if planning_revenue else Decimal("0.00")

    budget_allocated = _d(
        db.scalar(select(func.coalesce(func.sum(Budget.base_allocated_inr), 0)).where(Budget.is_active.is_(True)))
    )
    budget_spent = _d(
        db.scalar(select(func.coalesce(func.sum(Budget.base_spent_inr), 0)).where(Budget.is_active.is_(True)))
    )
    approved_budgets = int(
        db.scalar(
            select(func.count())
            .select_from(Budget)
            .where(Budget.approval_status == BudgetApprovalStatus.approved)
        )
        or 0
    )

    quoted_hours = _d(
        db.scalar(select(func.coalesce(func.sum(Project.quoted_hours), 0)).where(Project.is_deleted.is_(False)))
    )
    actual_hours = _d(
        db.scalar(select(func.coalesce(func.sum(Project.actual_hours), 0)).where(Project.is_deleted.is_(False)))
    )
    recovery = (actual_hours / quoted_hours * 100) if quoted_hours else Decimal("0.00")

    snapshots = db.scalars(select(ProjectFinancialSnapshot).limit(25)).all()
    placeholders = db.scalars(
        select(AiForecastPlaceholder).where(AiForecastPlaceholder.is_active.is_(True))
    ).all()

    renewals = []
    for expense in list_upcoming_renewals(db, today=today):
        days_until = (expense.next_renewal_date - today).days  # type: ignore[operator]
        renewals.append(
            {
                "expense_id": expense.id,
                "name": expense.name,
                "vendor_name": expense.vendor_name,
                "paid_by": expense.paid_by,
                "next_renewal_date": expense.next_renewal_date,
                "notify_before_days": expense.notify_before_days,
                "amount": expense.amount,
                "currency_code": expense.currency_code,
                "base_amount_inr": expense.base_amount_inr,
                "days_until": days_until,
            }
        )

    return {
        "base_currency": base,
        "revenue": {
            "monthly_revenue": planning_revenue,
            "quarterly_revenue": planning_revenue,
            "yearly_revenue": planning_revenue,
            "revenue_forecast": planning_revenue,
            "customer_revenue": revenue,
            "business_model_revenue": team_fee_monthly,
            "quote_revenue": revenue,
            "team_commercial_fee_monthly": team_fee_monthly,
        },
        "cost": {
            "salary_cost": salary_cost,
            "software_cost": Decimal("0.00"),
            "infrastructure_cost": Decimal("0.00"),
            "travel": Decimal("0.00"),
            "training": Decimal("0.00"),
            "capex": capex,
            "recurring_costs": prosohm_opex,
            "monthly_operating_cost": operating_cost,
            "annual_operating_cost": operating_cost * Decimal("12"),
            "prosohm_opex": prosohm_opex,
            "pass_through_opex": pass_through_opex,
        },
        "profitability": {
            "gross_profit": gross_profit,
            "gross_margin": gross_margin.quantize(Decimal("0.01")),
            "net_margin": net_margin.quantize(Decimal("0.01")),
            "recovery_percent": recovery.quantize(Decimal("0.01")),
            "profit_forecast": net_profit,
            "project_margin": gross_margin.quantize(Decimal("0.01")),
            "customer_margin": gross_margin.quantize(Decimal("0.01")),
            "engineering_margin": gross_margin.quantize(Decimal("0.01")),
        },
        "budget": {
            "budget_allocated": budget_allocated,
            "budget_consumed": budget_spent,
            "remaining_budget": budget_allocated - budget_spent,
            "budget_forecast": budget_allocated,
            "budget_variance": budget_allocated - budget_spent,
            "department_budget": budget_allocated,
            "customer_budget": budget_allocated,
            "approved_budgets": approved_budgets,
        },
        "productivity": {
            "quoted_hours": quoted_hours,
            "actual_hours": actual_hours,
            "billable_hours": actual_hours,
            "non_billable_hours": Decimal("0.00"),
            "recovery_rate": recovery.quantize(Decimal("0.01")),
            "average_hourly_cost": (
                (estimated_cost / quoted_hours).quantize(Decimal("0.01"))
                if quoted_hours
                else Decimal("0.00")
            ),
            "average_hourly_revenue": (
                (planning_revenue / quoted_hours).quantize(Decimal("0.01"))
                if quoted_hours
                else Decimal("0.00")
            ),
            "engineering_productivity": recovery.quantize(Decimal("0.01")),
        },
        "project_snapshots": [
            {
                "project_id": str(row.project_id),
                "quoted_hours": row.quoted_hours,
                "actual_hours": row.actual_hours,
                "revenue": row.revenue,
                "gross_profit": row.gross_profit,
                "recovery_percent": row.recovery_percent,
                "profitability_percent": row.profitability_percent,
                "currency_code": row.currency_code,
                "base_revenue_inr": row.base_revenue_inr,
            }
            for row in snapshots
        ],
        "ai_placeholders": [
            {
                "id": str(row.id),
                "kind": row.kind.value,
                "title": row.title,
                "description": row.description,
            }
            for row in placeholders
        ],
        "upcoming_renewals": renewals,
        "team_commercial_fee_monthly_inr": team_fee_monthly,
        "pass_through_opex_inr": pass_through_opex,
        "salary_cost_inr": salary_cost,
    }
