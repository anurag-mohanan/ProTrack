"""Budgets & Reports cockpit rollups + risk insights (Phase D)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import BudgetApprovalStatus, BudgetScopeType, CostNature, ExpensePaidBy
from app.models.finance import Budget
from app.services.finance.annual_plan_service import current_fy_start
from app.services.finance.plan_vs_actual_service import fy_months_elapsed


def _q(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _list_budgets(db: Session, *, team_id: UUID | None) -> list[Budget]:
    stmt = select(Budget).where(Budget.is_active.is_(True))
    if team_id is not None:
        stmt = stmt.where(
            Budget.scope_type == BudgetScopeType.team,
            Budget.scope_id == team_id,
        )
    return list(db.scalars(stmt.order_by(Budget.name)).all())


def _operating_monthly(db: Session, *, team_id: UUID | None) -> Decimal:
    from app.services.finance.dashboard_service import (
        _expense_sum,
        _salary_for_users,
        _user_ids_for_team,
    )

    today = date.today()
    user_ids = _user_ids_for_team(db, team_id) if team_id else None
    salary = _salary_for_users(db, user_ids, as_of=today)
    opex = _expense_sum(
        db, team_id=team_id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.opex, as_of=today
    )
    return _q(salary + opex)


def _enrich_budget(row: Budget) -> dict:
    allocated = _q(row.allocated or 0)
    spent = _q(row.spent or 0)
    forecast = _q(row.forecast or 0)
    util = float(_q(spent / allocated * 100)) if allocated > 0 else 0.0
    at_risk = util >= 85 or (allocated > 0 and forecast > allocated)
    return {
        "id": row.id,
        "name": row.name,
        "scope_type": row.scope_type,
        "scope_id": row.scope_id,
        "currency_code": row.currency_code,
        "allocated": allocated,
        "spent": spent,
        "forecast": forecast,
        "remaining": _q(row.remaining or 0),
        "variance": _q(row.variance or 0),
        "approval_status": row.approval_status,
        "fiscal_year": row.fiscal_year,
        "q1_allocated": _q(row.q1_allocated or 0),
        "q2_allocated": _q(row.q2_allocated or 0),
        "q3_allocated": _q(row.q3_allocated or 0),
        "q4_allocated": _q(row.q4_allocated or 0),
        "q1_forecast": _q(row.q1_forecast or 0),
        "q2_forecast": _q(row.q2_forecast or 0),
        "q3_forecast": _q(row.q3_forecast or 0),
        "q4_forecast": _q(row.q4_forecast or 0),
        "utilization_percent": _q(util),
        "at_risk": at_risk,
        "is_active": row.is_active,
    }


def build_budget_cockpit(db: Session, *, team_id: UUID | None = None) -> dict:
    rows = _list_budgets(db, team_id=team_id)
    enriched = [_enrich_budget(row) for row in rows]
    allocated = _q(sum((r["allocated"] for r in enriched), Decimal("0")))
    spent = _q(sum((r["spent"] for r in enriched), Decimal("0")))
    forecast = _q(sum((r["forecast"] for r in enriched), Decimal("0")))
    remaining = _q(sum((r["remaining"] for r in enriched), Decimal("0")))
    draft_count = sum(1 for r in enriched if r["approval_status"] == BudgetApprovalStatus.draft)
    approved_count = sum(
        1 for r in enriched if r["approval_status"] == BudgetApprovalStatus.approved
    )
    at_risk_count = sum(1 for r in enriched if r["at_risk"])
    util = _q(spent / allocated * 100) if allocated > 0 else Decimal("0.00")

    quarters = {
        "q1_allocated": _q(sum((r["q1_allocated"] for r in enriched), Decimal("0"))),
        "q2_allocated": _q(sum((r["q2_allocated"] for r in enriched), Decimal("0"))),
        "q3_allocated": _q(sum((r["q3_allocated"] for r in enriched), Decimal("0"))),
        "q4_allocated": _q(sum((r["q4_allocated"] for r in enriched), Decimal("0"))),
        "q1_forecast": _q(sum((r["q1_forecast"] for r in enriched), Decimal("0"))),
        "q2_forecast": _q(sum((r["q2_forecast"] for r in enriched), Decimal("0"))),
        "q3_forecast": _q(sum((r["q3_forecast"] for r in enriched), Decimal("0"))),
        "q4_forecast": _q(sum((r["q4_forecast"] for r in enriched), Decimal("0"))),
    }

    insights: list[dict] = []
    if draft_count:
        insights.append(
            {
                "id": "drafts_pending",
                "severity": "medium",
                "title": f"{draft_count} budget(s) awaiting approval",
                "detail": "Approve drafts so the board pack reflects committed envelopes.",
            }
        )
    if at_risk_count:
        insights.append(
            {
                "id": "at_risk",
                "severity": "high",
                "title": f"{at_risk_count} budget(s) at risk",
                "detail": "Utilization ≥ 85% or forecast above allocated — review spend or raise the envelope.",
            }
        )
    zero_spent = [r for r in enriched if r["allocated"] > 0 and r["spent"] <= 0]
    if zero_spent:
        insights.append(
            {
                "id": "zero_spent",
                "severity": "low",
                "title": "Some budgets show zero spent",
                "detail": "Use Sync spent from live OpEx on a budget card to pull YTD operating cost into spent.",
            }
        )
    if forecast > allocated > 0:
        insights.append(
            {
                "id": "portfolio_over_forecast",
                "severity": "medium",
                "title": "Portfolio forecast exceeds allocated",
                "detail": f"Forecast {_q(forecast)} vs allocated {_q(allocated)} — renewals may be inflating quarterly forecasts.",
            }
        )
    if not insights:
        insights.append(
            {
                "id": "healthy",
                "severity": "info",
                "title": "Budget portfolio looks quiet",
                "detail": "No draft pile-up or high utilization flags in this scope.",
            }
        )

    fy_start = current_fy_start()
    # Approximate FY end for months elapsed helper
    fy_end = date(fy_start.year + 1, 3, 31)
    months = fy_months_elapsed(fy_start, fy_end, date.today())
    operating_monthly = _operating_monthly(db, team_id=team_id)

    return {
        "team_id": team_id,
        "currency_code": "INR",
        "planning_fy_start": fy_start.isoformat(),
        "months_elapsed": months,
        "operating_monthly_inr": operating_monthly,
        "operating_ytd_inr": _q(operating_monthly * Decimal(months)),
        "totals": {
            "budget_count": len(enriched),
            "allocated": allocated,
            "spent": spent,
            "forecast": forecast,
            "remaining": remaining,
            "utilization_percent": util,
            "draft_count": draft_count,
            "approved_count": approved_count,
            "at_risk_count": at_risk_count,
        },
        "quarters": quarters,
        "insights": insights,
        "budgets": enriched,
    }


def sync_budget_spent_from_operating(
    db: Session, budget_id: UUID, *, team_id: UUID | None = None
) -> Budget:
    row = db.get(Budget, budget_id)
    if row is None or not row.is_active:
        raise ProTrackValidationError("Budget not found")
    scope_team = (
        row.scope_id if row.scope_type == BudgetScopeType.team else team_id
    )
    fy_start = current_fy_start()
    fy_end = date(fy_start.year + 1, 3, 31)
    months = fy_months_elapsed(fy_start, fy_end, date.today())
    monthly = _operating_monthly(db, team_id=scope_team)
    ytd = _q(monthly * Decimal(max(months, 1)))
    allocated = _q(row.allocated or 0)
    spent = min(ytd, allocated) if allocated > 0 else ytd
    row.spent = spent
    row.base_spent_inr = spent
    row.remaining = _q(allocated - spent)
    # Keep variance as allocated - forecast (existing semantics)
    row.variance = _q(allocated - _q(row.forecast or 0))
    db.flush()
    return row
