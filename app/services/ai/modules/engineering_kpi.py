"""Engineering KPI engine — aggregates operational KPIs for AI surfaces."""

from __future__ import annotations

from typing import Any

from app.services.ai.base import AiContext, AiModule
from app.services.ai.context import (
    count_overdue_milestones,
    get_active_projects,
    get_customer_workload_share,
    get_designer_utilization,
    get_pending_draft_timesheets,
)
from app.services.ai.forecasting import forecaster
from app.services.ai.risk_analysis import risk_analyzer
from app.services.project_calculation_service import count_projects_by_health


class EngineeringKpiModule(AiModule):
    name = "engineering_kpi"

    def run(self, ctx: AiContext, **kwargs: Any) -> dict:
        active = get_active_projects(ctx)
        util = get_designer_utilization(ctx)
        avg_util = sum(r["utilization"] for r in util) / len(util) if util else 0
        health_counts = count_projects_by_health(ctx.db)
        health = {"green": health_counts[0], "yellow": health_counts[1], "red": health_counts[2]}

        return {
            "active_projects": len(active),
            "due_this_week": len(risk_analyzer.projects_due_soon(ctx)),
            "over_budget": len(risk_analyzer.projects_over_quoted(ctx, threshold=1.0)),
            "at_risk": len(risk_analyzer.projects_at_risk(ctx)),
            "late_milestones": count_overdue_milestones(ctx),
            "utilization_percent": round(avg_util, 1),
            "health": health,
            "customer_workload": get_customer_workload_share(ctx)[:5],
            "pending_timesheets": get_pending_draft_timesheets(ctx),
            "capacity_30": forecaster.capacity_forecast(ctx, horizon_days=30).model_dump(),
            "capacity_60": forecaster.capacity_forecast(ctx, horizon_days=60).model_dump(),
            "capacity_90": forecaster.capacity_forecast(ctx, horizon_days=90).model_dump(),
        }
