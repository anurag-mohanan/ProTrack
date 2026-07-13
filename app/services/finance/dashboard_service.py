"""Financial dashboard aggregates (base currency INR)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import BudgetApprovalStatus, CostNature
from app.models.finance import (
    AiForecastPlaceholder,
    Budget,
    Expense,
    ProjectFinancialSnapshot,
    QuoteRevision,
)
from app.models.models import Project
from app.services.finance.fx_service import get_base_currency


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def get_finance_dashboard(db: Session) -> dict:
    base = get_base_currency(db)
    revenue = _d(
        db.scalar(select(func.coalesce(func.sum(QuoteRevision.base_quoted_revenue_inr), 0)))
    )
    estimated_cost = _d(
        db.scalar(select(func.coalesce(func.sum(QuoteRevision.base_estimated_cost_inr), 0)))
    )
    opex = _d(
        db.scalar(
            select(func.coalesce(func.sum(Expense.base_amount_inr), 0)).where(
                Expense.is_active.is_(True),
                Expense.nature == CostNature.opex,
            )
        )
    )
    capex = _d(
        db.scalar(
            select(func.coalesce(func.sum(Expense.base_amount_inr), 0)).where(
                Expense.is_active.is_(True),
                Expense.nature == CostNature.capex,
            )
        )
    )
    gross_profit = revenue - estimated_cost
    gross_margin = (gross_profit / revenue * 100) if revenue else Decimal("0.00")
    net_profit = gross_profit - opex
    net_margin = (net_profit / revenue * 100) if revenue else Decimal("0.00")

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

    return {
        "base_currency": base,
        "revenue": {
            "monthly_revenue": revenue,
            "quarterly_revenue": revenue,
            "yearly_revenue": revenue,
            "revenue_forecast": revenue,
            "customer_revenue": revenue,
            "business_model_revenue": revenue,
        },
        "cost": {
            "salary_cost": Decimal("0.00"),
            "software_cost": Decimal("0.00"),
            "infrastructure_cost": Decimal("0.00"),
            "travel": Decimal("0.00"),
            "training": Decimal("0.00"),
            "capex": capex,
            "recurring_costs": opex,
            "monthly_operating_cost": opex,
            "annual_operating_cost": opex * Decimal("12"),
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
                (revenue / quoted_hours).quantize(Decimal("0.01")) if quoted_hours else Decimal("0.00")
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
    }
