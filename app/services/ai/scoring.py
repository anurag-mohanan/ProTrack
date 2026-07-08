"""Scoring primitives for health, customers, and resource fit."""

from __future__ import annotations

from datetime import timedelta

from app.models.enums import ProjectHealth
from app.models.models import Project
from app.schemas.ai import CustomerIntelligence, ProjectHealthAnalysis
from app.services.ai.base import AiContext, AiProvider, round_percent
from app.services.project_calculation_service import calculate_project_health


class Scorer(AiProvider):
    name = "scoring"

    def project_health_score(self, ctx: AiContext, project: Project) -> ProjectHealthAnalysis:
        health = calculate_project_health(project, ctx.today, ctx.db)
        factors: list[str] = []
        score = 100.0

        quoted = float(project.quoted_hours or 0)
        actual = float(project.actual_hours or 0)
        if quoted > 0 and actual > quoted:
            factors.append("Actual hours exceed quoted hours")
            score -= 30
        elif quoted > 0 and actual >= quoted * 0.85:
            factors.append("Approaching quoted hour limit")
            score -= 15

        if project.due_date and project.due_date < ctx.today:
            factors.append("Past due date")
            score -= 25
        elif project.due_date and project.due_date <= ctx.today + timedelta(days=5):
            factors.append("Due within 5 days")
            score -= 10

        from app.services.ai.context import count_overdue_milestones
        from sqlalchemy import func, select
        from app.models.models import Milestone
        from app.models.enums import MilestoneStatus

        overdue = int(
            ctx.db.scalar(
                select(func.count())
                .select_from(Milestone)
                .where(
                    Milestone.project_id == project.id,
                    Milestone.status != MilestoneStatus.completed,
                    Milestone.due_date.is_not(None),
                    Milestone.due_date < ctx.today,
                )
            )
            or 0
        )
        if overdue:
            factors.append(f"{overdue} overdue milestone(s)")
            score -= min(20, overdue * 5)

        if not factors:
            factors.append("On track")

        return ProjectHealthAnalysis(
            project_id=project.id,
            tool_number=project.tool_number,
            health=health.value if hasattr(health, "value") else str(health),
            score=round_percent(score),
            factors=factors,
        )

    def customer_score(
        self,
        *,
        on_time_percent: float,
        change_count: int,
        schedule_variance: float,
        workload_hours: float,
    ) -> float:
        score = 70.0
        score += (on_time_percent - 80) * 0.2
        score -= min(change_count * 2, 15)
        score -= min(abs(schedule_variance) * 0.5, 10)
        if workload_hours > 200:
            score += 5
        return round_percent(score)


scorer = Scorer()
