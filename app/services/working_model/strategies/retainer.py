"""Retainer / subscription KPI strategy."""

from decimal import Decimal, ROUND_HALF_UP

from app.models.enums import ProjectHealth, ProjectRiskType, WorkingModelCode
from app.services.working_model.base import WorkingModelContext, WorkingModelKpiResult, WorkingModelStrategy


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class RetainerStrategy(WorkingModelStrategy):
    strategy_key = WorkingModelCode.retainer

    def calculate_kpis(self, ctx: WorkingModelContext) -> WorkingModelKpiResult:
        hours = ctx.hours
        monthly_capacity = hours.quoted
        consumed = hours.actual
        remaining = _round(max(monthly_capacity - consumed, Decimal("0")))
        utilization = (
            _round((consumed / monthly_capacity) * Decimal("100"))
            if monthly_capacity > 0
            else Decimal("0")
        )
        return WorkingModelKpiResult(
            working_model_id=ctx.working_model.id,
            working_model_code=ctx.working_model.code,
            working_model_name=ctx.working_model.name,
            strategy_key=self.strategy_key,
            show_quoted_variance=False,
            show_over_budget_indicators=False,
            quoted_hours=monthly_capacity,
            actual_hours=consumed,
            remaining_hours=remaining,
            variance=None,
            variance_percent=None,
            budget_consumption_percent=utilization,
            model_metrics={
                "monthly_capacity_hours": monthly_capacity,
                "consumed_hours": consumed,
                "remaining_capacity_hours": remaining,
                "capacity_utilization_percent": utilization,
                "customer_responsiveness": None,
            },
        )

    def evaluate_health_adjustment(self, ctx: WorkingModelContext) -> ProjectHealth | None:
        hours = ctx.hours
        if hours.quoted > 0 and hours.actual > hours.quoted:
            return ProjectHealth.yellow
        if hours.quoted > 0 and hours.actual >= hours.quoted * Decimal("0.9"):
            return ProjectHealth.yellow
        return None

    def should_flag_hours_over_quote(self, ctx: WorkingModelContext) -> bool:
        return False

    def applicable_risk_types(self) -> set[ProjectRiskType]:
        return {
            ProjectRiskType.overdue,
            ProjectRiskType.milestone_delay,
            ProjectRiskType.missing_approvals,
            ProjectRiskType.designer_overloaded,
        }
