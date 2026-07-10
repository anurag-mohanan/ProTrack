"""Project-based (fixed fee) KPI strategy."""

from decimal import Decimal, ROUND_HALF_UP

from app.models.enums import ProjectHealth, ProjectRiskType, WorkingModelCode
from app.services.working_model.base import WorkingModelContext, WorkingModelKpiResult, WorkingModelStrategy


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ProjectBasedStrategy(WorkingModelStrategy):
    strategy_key = WorkingModelCode.project_based

    def calculate_kpis(self, ctx: WorkingModelContext) -> WorkingModelKpiResult:
        hours = ctx.hours
        budget_pct = (
            _round((hours.actual / hours.quoted) * Decimal("100"))
            if hours.quoted > 0
            else Decimal("0")
        )
        variance_pct = (
            _round((hours.variance / hours.quoted) * Decimal("100"))
            if hours.quoted > 0
            else Decimal("0")
        )
        profitability_indicator = (
            "on_track"
            if hours.quoted <= 0 or hours.actual <= hours.quoted
            else "over_budget"
        )
        return WorkingModelKpiResult(
            working_model_id=ctx.working_model.id,
            working_model_code=ctx.working_model.code,
            working_model_name=ctx.working_model.name,
            strategy_key=self.strategy_key,
            show_quoted_variance=True,
            show_over_budget_indicators=True,
            quoted_hours=hours.quoted,
            actual_hours=hours.actual,
            remaining_hours=hours.remaining,
            variance=hours.variance,
            variance_percent=variance_pct,
            budget_consumption_percent=budget_pct,
            model_metrics={
                "delivery_performance": profitability_indicator,
                "milestone_adherence": None,
                "profitability_indicator": profitability_indicator,
            },
        )

    def evaluate_health_adjustment(self, ctx: WorkingModelContext) -> ProjectHealth | None:
        hours = ctx.hours
        if hours.quoted > 0 and hours.actual > hours.quoted:
            return ProjectHealth.red
        if hours.quoted > 0 and hours.actual >= hours.quoted * Decimal("0.85"):
            return ProjectHealth.yellow
        return None

    def should_flag_hours_over_quote(self, ctx: WorkingModelContext) -> bool:
        return super().should_flag_hours_over_quote(ctx)

    def applicable_risk_types(self) -> set[ProjectRiskType]:
        return super().applicable_risk_types()
