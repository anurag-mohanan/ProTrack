"""Risk analysis primitives."""

from __future__ import annotations

from datetime import timedelta

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth
from app.schemas.ai import AiInsight
from app.services.ai.base import AiContext, AiProvider, round_hours
from app.services.ai.context import get_active_projects, count_overdue_milestones


class RiskAnalyzer(AiProvider):
    name = "risk_analysis"

    def projects_over_quoted(self, ctx: AiContext, *, threshold: float = 0.9) -> list:
        return [
            p
            for p in get_active_projects(ctx)
            if float(p.quoted_hours or 0) > 0
            and float(p.actual_hours or 0) >= float(p.quoted_hours) * threshold
        ]

    def projects_due_soon(self, ctx: AiContext, *, days: int = 7) -> list:
        cutoff = ctx.today + timedelta(days=days)
        return [
            p
            for p in get_active_projects(ctx)
            if p.due_date is not None
            and ctx.today <= p.due_date <= cutoff
            and p.execution_status != ExecutionStatus.completed
        ]

    def projects_at_risk(self, ctx: AiContext) -> list:
        return [p for p in get_active_projects(ctx) if p.health == ProjectHealth.red]

    def gt3_at_risk(self, ctx: AiContext, *, days: int = 14) -> int:
        from sqlalchemy import func, select
        from app.models.models import Milestone, Project

        return int(
            ctx.db.scalar(
                select(func.count())
                .select_from(Milestone)
                .join(Project, Milestone.project_id == Project.id)
                .where(
                    Project.is_deleted.is_(False),
                    Project.is_archived.is_(False),
                    Project.execution_status.in_(
                        (ExecutionStatus.planning, ExecutionStatus.currently_being_worked_on)
                    ),
                    Milestone.name.ilike("%GT3%"),
                    Milestone.status != MilestoneStatus.completed,
                    Milestone.due_date.is_not(None),
                    Milestone.due_date <= ctx.today + timedelta(days=days),
                )
            )
            or 0
        )

    def build_insights(self, ctx: AiContext) -> list[AiInsight]:
        insights: list[AiInsight] = []
        over_quoted = self.projects_over_quoted(ctx)
        if over_quoted:
            insights.append(
                AiInsight(
                    id="risk-over-quoted",
                    module="dashboard_insights",
                    category="planning",
                    severity="warning",
                    title=f"{len(over_quoted)} project{'s' if len(over_quoted) != 1 else ''} likely to exceed quoted hours",
                    detail="Quoted hours are nearly or fully consumed on active tools.",
                    href="/reports?tab=project-hours",
                    confidence=88,
                )
            )

        due_soon = self.projects_due_soon(ctx)
        if due_soon:
            insights.append(
                AiInsight(
                    id="risk-due-soon",
                    module="dashboard_insights",
                    category="planning",
                    severity="warning",
                    title=f"{len(due_soon)} project{'s' if len(due_soon) != 1 else ''} due this week",
                    detail="Review delivery dates and reallocate resources before milestones slip.",
                    href="/projects?due=week",
                    confidence=92,
                )
            )

        at_risk = self.projects_at_risk(ctx)
        if at_risk:
            insights.append(
                AiInsight(
                    id="risk-critical-health",
                    module="dashboard_insights",
                    category="planning",
                    severity="error",
                    title=f"{len(at_risk)} active project{'s' if len(at_risk) != 1 else ''} in critical health",
                    detail="Review overdue tools and hours burn immediately.",
                    href="/projects",
                    confidence=95,
                )
            )

        overdue_ms = count_overdue_milestones(ctx)
        if overdue_ms:
            insights.append(
                AiInsight(
                    id="risk-overdue-milestones",
                    module="dashboard_insights",
                    category="planning",
                    severity="error",
                    title=f"{overdue_ms} milestone{'s' if overdue_ms != 1 else ''} behind schedule",
                    detail="Prioritize overdue milestones to protect customer delivery dates.",
                    href="/projects",
                    confidence=94,
                )
            )

        gt3 = self.gt3_at_risk(ctx)
        if gt3:
            insights.append(
                AiInsight(
                    id="risk-gt3",
                    module="dashboard_insights",
                    category="planning",
                    severity="error",
                    title=f"{gt3} project{'s' if gt3 != 1 else ''} at risk of missing GT3",
                    detail="GT3 milestones are due within two weeks and still open.",
                    href="/projects",
                    confidence=90,
                )
            )

        return insights


risk_analyzer = RiskAnalyzer()
