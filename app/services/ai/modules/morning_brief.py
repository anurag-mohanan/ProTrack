"""Morning engineering brief for managers."""

from __future__ import annotations

from typing import Any

from app.schemas.ai import MorningBrief
from app.services.ai.base import AiContext, AiModule
from app.services.ai.context import (
    count_overdue_milestones,
    get_active_projects,
    get_designer_utilization,
    get_pending_draft_timesheets,
)
from app.services.ai.modules.dashboard_insights import DashboardInsightsModule
from app.services.ai.risk_analysis import risk_analyzer
from app.services.timesheet_compliance_service import get_missing_timesheet_rows


class MorningBriefModule(AiModule):
    name = "morning_brief"

    def run(self, ctx: AiContext, **kwargs: Any) -> MorningBrief:
        actor_name = kwargs.get("actor_name") or ctx.actor_name or "Manager"
        first_name = actor_name.split()[0] if actor_name else "Manager"

        active = get_active_projects(ctx)
        due_this_week = risk_analyzer.projects_due_soon(ctx)
        at_risk = risk_analyzer.projects_at_risk(ctx)
        util_rows = get_designer_utilization(ctx)
        available = sum(1 for r in util_rows if r["utilization"] < 75)
        avg_util = (
            sum(r["utilization"] for r in util_rows) / len(util_rows) if util_rows else 0
        )
        missing = get_missing_timesheet_rows(ctx.db, limit=50)
        over_budget = risk_analyzer.projects_over_quoted(ctx, threshold=1.0)
        late_ms = count_overdue_milestones(ctx)

        insights_module = DashboardInsightsModule()
        insights = insights_module.run(ctx, limit=6)

        return MorningBrief(
            greeting=f"Good Morning, {first_name}",
            active_projects=len(active),
            due_this_week=len(due_this_week),
            high_risk_projects=len(at_risk),
            engineers_available=available,
            utilization_percent=round(avg_util, 1),
            missing_timesheets=len(missing),
            over_budget_projects=len(over_budget),
            late_milestones=late_ms,
            insights=insights,
        )
