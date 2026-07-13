"""Overheads billing model — management and non-designer resources."""

from app.models.enums import ProjectHealth, ProjectRiskType, WorkingModelCode
from app.services.working_model.base import WorkingModelContext, WorkingModelKpiResult, WorkingModelStrategy


class OverheadsStrategy(WorkingModelStrategy):
    """
    Cost / capacity tracking for Engineering Managers, HR, Office Admin,
    and other non-designer resources — not project quote variance billing.
    """

    strategy_key = WorkingModelCode.overheads

    def calculate_kpis(self, ctx: WorkingModelContext) -> WorkingModelKpiResult:
        hours = ctx.hours
        overhead_hours = hours.actual
        return WorkingModelKpiResult(
            working_model_id=ctx.working_model.id,
            working_model_code=ctx.working_model.code,
            working_model_name=ctx.working_model.name,
            strategy_key=self.strategy_key,
            show_quoted_variance=False,
            show_over_budget_indicators=False,
            quoted_hours=None,
            actual_hours=overhead_hours,
            remaining_hours=None,
            variance=None,
            variance_percent=None,
            budget_consumption_percent=None,
            model_metrics={
                "overhead_hours": overhead_hours,
                "resource_class": "management_overhead",
                "billable_delivery": False,
            },
        )

    def evaluate_health_adjustment(self, ctx: WorkingModelContext) -> ProjectHealth | None:
        return None

    def should_flag_hours_over_quote(self, ctx: WorkingModelContext) -> bool:
        return False

    def applicable_risk_types(self) -> set[ProjectRiskType]:
        return {
            ProjectRiskType.missing_approvals,
            ProjectRiskType.designer_overloaded,
        }
