"""Deterministic AI Assist for annual finance plans (Phase C — no external LLM)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import FinancePlanSection
from app.models.finance import FinancePlan, FinancePlanLine
from app.services.finance import annual_plan_service
from app.services.finance.annual_plan_service import QUARTER_FIELDS, apply_quarter_amount, line_quarter_totals
from app.services.finance.plan_vs_actual_service import compute_plan_vs_actual, seed_plan_from_live

APPLY_ACTIONS = frozenset(
    {
        "seed_from_live",
        "fill_empty_quarters_from_q1",
        "project_remaining_from_run_rate",
        "uplift_remaining_sales",
    }
)


def _q(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _line_by_code(plan: FinancePlan, code: str) -> FinancePlanLine | None:
    return next((row for row in plan.lines if row.code == code and not row.is_total_row), None)


def _quarter_empty(line: FinancePlanLine, quarter: str) -> bool:
    return line_quarter_totals(line).get(quarter, Decimal("0")) == 0


def _filled_cell_ratio(plan: FinancePlan) -> float:
    cells = 0
    filled = 0
    for line in plan.lines:
        if line.is_total_row or line.section not in {
            FinancePlanSection.sales,
            FinancePlanSection.expenses,
        }:
            continue
        totals = line_quarter_totals(line)
        for q in QUARTER_FIELDS:
            cells += 1
            if totals.get(q, Decimal("0")) > 0:
                filled += 1
    return (filled / cells) if cells else 0.0


def build_ai_insights(db: Session, plan_id: UUID) -> dict:
    plan = annual_plan_service.get_plan(db, plan_id)
    pva = compute_plan_vs_actual(db, plan)
    summary = annual_plan_service.compute_plan_summary(plan)
    fill_ratio = _filled_cell_ratio(plan)
    months_elapsed = int(pva["months_elapsed"])
    confidence = min(
        95,
        max(
            35,
            int(40 + fill_ratio * 40 + (10 if months_elapsed >= 3 else 0) + (5 if months_elapsed >= 6 else 0)),
        ),
    )

    insights: list[dict] = []
    wages = _line_by_code(plan, "wages")
    overhead = _line_by_code(plan, "overhead")
    wages_fy = sum(line_quarter_totals(wages).values()) if wages else Decimal("0")
    overhead_fy = sum(line_quarter_totals(overhead).values()) if overhead else Decimal("0")

    if wages is not None and wages_fy <= 0:
        insights.append(
            {
                "id": "wages_unseeded",
                "severity": "high",
                "title": "Wages line is empty",
                "detail": "Live salary roster can seed the Wages row across Q1–Q4 so the plan reflects headcount cost.",
                "action_code": "seed_from_live",
                "action_label": "Seed wages & overhead",
            }
        )
    if overhead is not None and overhead_fy <= 0:
        insights.append(
            {
                "id": "overhead_unseeded",
                "severity": "medium",
                "title": "Overhead planning line is empty",
                "detail": "Management + Corporate overhead pool can be projected into the Overhead expense line.",
                "action_code": "seed_from_live",
                "action_label": "Seed wages & overhead",
            }
        )

    needs_fill = False
    for line in plan.lines:
        if line.is_total_row:
            continue
        q1 = line_quarter_totals(line).get("q1", Decimal("0"))
        if q1 <= 0:
            continue
        if any(_quarter_empty(line, q) for q in ("q2", "q3", "q4")):
            needs_fill = True
            break
    if needs_fill:
        insights.append(
            {
                "id": "sparse_quarters",
                "severity": "medium",
                "title": "Later quarters are blank where Q1 has values",
                "detail": "Copy Q1 into empty Q2–Q4 as a baseline (common Adaptive / Abacum quick-fill).",
                "action_code": "fill_empty_quarters_from_q1",
                "action_label": "Fill empty quarters from Q1",
            }
        )

    sales_var = Decimal(str(pva["sales_variance_ytd"]))
    plan_sales_ytd = Decimal(str(pva["plan_sales_ytd"]))
    if months_elapsed >= 2 and plan_sales_ytd > 0 and sales_var < 0:
        lag_pct = _q(abs(sales_var) / plan_sales_ytd * 100)
        insights.append(
            {
                "id": "sales_behind_plan",
                "severity": "high" if lag_pct >= 15 else "medium",
                "title": f"Sales trailing plan by ~{lag_pct}% YTD",
                "detail": "Project remaining plan quarters from the live monthly revenue run-rate, or uplift remaining sales cells.",
                "action_code": "project_remaining_from_run_rate",
                "action_label": "Project remaining from run-rate",
            }
        )
        insights.append(
            {
                "id": "sales_uplift_option",
                "severity": "low",
                "title": "Optional 10% uplift on remaining sales quarters",
                "detail": "Stretch scenario helper — increases only future/remaining sales quarters by 10%.",
                "action_code": "uplift_remaining_sales",
                "action_label": "Uplift remaining sales +10%",
            }
        )

    gain_after = Decimal(str(summary["gain_loss_after_provision"]))
    if gain_after < 0:
        insights.append(
            {
                "id": "negative_after_provision",
                "severity": "high",
                "title": "Plan is loss-making after tax & provision",
                "detail": f"GAIN/LOSS after provision is {_q(gain_after)}. Review sales targets or expense seed before board pack.",
                "action_code": None,
                "action_label": None,
            }
        )

    exp_var = Decimal(str(pva["expenses_variance_ytd"]))
    if months_elapsed >= 2 and exp_var < 0:
        insights.append(
            {
                "id": "expenses_over_plan",
                "severity": "medium",
                "title": "Expenses running ahead of plan YTD",
                "detail": "Actual operating run-rate exceeds planned expense YTD. Consider re-seeding wages/overhead or raising plan expenses.",
                "action_code": "seed_from_live",
                "action_label": "Re-seed wages & overhead",
            }
        )

    if not insights:
        insights.append(
            {
                "id": "healthy",
                "severity": "info",
                "title": "No critical plan gaps detected",
                "detail": "Quarters look populated and variance signals are within a quiet band. Keep syncing renewals as they change.",
                "action_code": None,
                "action_label": None,
            }
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    insights.sort(key=lambda row: severity_rank.get(str(row["severity"]), 9))

    return {
        "plan_id": plan.id,
        "fiscal_year_label": plan.fiscal_year_label,
        "engine": "deterministic_rules_v1",
        "disclaimer": "AI Assist is data-driven (no external LLM). Recommendations use plan cells and live finance run-rates.",
        "confidence_percent": confidence,
        "fill_ratio_percent": int(round(fill_ratio * 100)),
        "months_elapsed": months_elapsed,
        "insights": insights,
        "headline": insights[0]["title"] if insights else "Plan review",
    }


def _remaining_quarters(months_elapsed: int) -> list[str]:
    """FY months 1–3=Q1 … 10–12=Q4. Remaining = quarters not fully elapsed."""
    if months_elapsed <= 0:
        return list(QUARTER_FIELDS)
    if months_elapsed >= 12:
        return []
    current_q_index = (months_elapsed - 1) // 3  # 0..3
    # Remaining includes current quarter (still open) and later
    return list(QUARTER_FIELDS[current_q_index:])


def apply_ai_action(db: Session, plan_id: UUID, *, action_code: str) -> FinancePlan:
    code = (action_code or "").strip()
    if code not in APPLY_ACTIONS:
        raise ProTrackValidationError(f"Unknown AI action: {action_code}")

    if code == "seed_from_live":
        return seed_plan_from_live(db, plan_id)

    plan = annual_plan_service.get_plan(db, plan_id)
    pva = compute_plan_vs_actual(db, plan)
    months_elapsed = int(pva["months_elapsed"])
    remaining = _remaining_quarters(months_elapsed)

    if code == "fill_empty_quarters_from_q1":
        for line in plan.lines:
            if line.is_total_row:
                continue
            q1 = line_quarter_totals(line).get("q1", Decimal("0"))
            if q1 <= 0:
                continue
            for q in ("q2", "q3", "q4"):
                if _quarter_empty(line, q):
                    apply_quarter_amount(line, q, q1)
        db.flush()
        return plan

    if code == "project_remaining_from_run_rate":
        sales_monthly = Decimal(str(pva["sales_monthly_run_rate"]))
        expenses_monthly = Decimal(str(pva["expenses_monthly_run_rate"]))
        sales_q = _q(sales_monthly * 3)
        expenses_q = _q(expenses_monthly * 3)
        sales_lines = [
            row
            for row in plan.lines
            if row.section == FinancePlanSection.sales and not row.is_total_row
        ]
        expense_lines = [
            row
            for row in plan.lines
            if row.section == FinancePlanSection.expenses and not row.is_total_row
        ]

        def _shares(weights: list[Decimal], count: int) -> list[Decimal]:
            total = sum(weights)
            if count <= 0:
                return []
            if total <= 0:
                even = _q(Decimal("1") / Decimal(count))
                return [even] * count
            return [_q(weight / total) for weight in weights]

        sales_weights = [sum(line_quarter_totals(row).values()) for row in sales_lines]
        expense_weights = [sum(line_quarter_totals(row).values()) for row in expense_lines]
        for row, share in zip(sales_lines, _shares(sales_weights, len(sales_lines))):
            amount = _q(sales_q * share)
            for q in remaining:
                apply_quarter_amount(row, q, amount)
        for row, share in zip(expense_lines, _shares(expense_weights, len(expense_lines))):
            amount = _q(expenses_q * share)
            for q in remaining:
                apply_quarter_amount(row, q, amount)
        db.flush()
        return plan

    if code == "uplift_remaining_sales":
        factor = Decimal("1.10")
        for row in plan.lines:
            if row.section != FinancePlanSection.sales or row.is_total_row:
                continue
            totals = line_quarter_totals(row)
            for q in remaining:
                current = totals.get(q, Decimal("0"))
                if current > 0:
                    apply_quarter_amount(row, q, _q(current * factor))
        db.flush()
        return plan

    raise ProTrackValidationError(f"Unhandled AI action: {action_code}")
