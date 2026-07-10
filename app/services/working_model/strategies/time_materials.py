"""Time & materials (hourly) KPI strategy."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select

from app.models.enums import ProjectHealth, ProjectRiskType, TimesheetStatus, WorkingModelCode
from app.models.models import Timesheet, TimesheetEntry
from app.services.working_model.base import WorkingModelContext, WorkingModelKpiResult, WorkingModelStrategy


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _hours_for_statuses(ctx: WorkingModelContext, statuses: set[TimesheetStatus]) -> Decimal:
    total = ctx.db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .where(
            TimesheetEntry.project_id == ctx.project.id,
            TimesheetEntry.is_deleted.is_(False),
            Timesheet.status.in_(statuses),
        )
    )
    return _round(Decimal(str(total or 0)))


class TimeMaterialsStrategy(WorkingModelStrategy):
    strategy_key = WorkingModelCode.time_materials

    def calculate_kpis(self, ctx: WorkingModelContext) -> WorkingModelKpiResult:
        hours = ctx.hours
        approved = _hours_for_statuses(ctx, {TimesheetStatus.approved})
        submitted = _hours_for_statuses(
            ctx, {TimesheetStatus.submitted, TimesheetStatus.approved}
        )
        billable = hours.actual
        utilization = (
            _round((billable / hours.quoted) * Decimal("100"))
            if hours.quoted > 0
            else Decimal("0")
        )
        invoicing_ready = approved
        pending_approval = submitted - approved
        revenue_hours = approved
        return WorkingModelKpiResult(
            working_model_id=ctx.working_model.id,
            working_model_code=ctx.working_model.code,
            working_model_name=ctx.working_model.name,
            strategy_key=self.strategy_key,
            show_quoted_variance=False,
            show_over_budget_indicators=False,
            quoted_hours=None,
            actual_hours=billable,
            remaining_hours=None,
            variance=None,
            variance_percent=None,
            budget_consumption_percent=None,
            model_metrics={
                "billable_hours": billable,
                "approved_hours": approved,
                "pending_approval_hours": pending_approval,
                "utilization_percent": utilization,
                "invoicing_ready_hours": invoicing_ready,
                "revenue_hours": revenue_hours,
            },
        )

    def evaluate_health_adjustment(self, ctx: WorkingModelContext) -> ProjectHealth | None:
        approved = _hours_for_statuses(ctx, {TimesheetStatus.approved})
        submitted = _hours_for_statuses(
            ctx, {TimesheetStatus.submitted, TimesheetStatus.approved}
        )
        if submitted > 0 and approved / submitted < Decimal("0.5"):
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
