"""Forecasting primitives for schedule and capacity prediction."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus, MilestoneStatus
from app.models.models import Milestone, Project
from app.schemas.ai import CapacityForecast, SchedulePrediction
from app.services.ai.base import AiContext, AiProvider, confidence_from_sample_size, round_hours
from app.services.ai.context import get_active_projects, get_designer_utilization


class Forecaster(AiProvider):
    name = "forecasting"

    def predict_completion(self, ctx: AiContext, project: Project) -> SchedulePrediction:
        reasons: list[str] = []
        confidence = 70.0
        predicted = project.due_date

        milestones = list(
            ctx.db.scalars(
                select(Milestone).where(
                    Milestone.project_id == project.id,
                    Milestone.status != MilestoneStatus.completed,
                )
            ).all()
        )
        late = [m for m in milestones if m.due_date and m.due_date < ctx.today]
        if late:
            reasons.append(f"{len(late)} milestone(s) delayed")
            delay_days = max((ctx.today - m.due_date).days for m in late if m.due_date)
            if predicted:
                predicted = predicted + timedelta(days=min(delay_days, 21))
            confidence -= 10

        quoted = float(project.quoted_hours or 0)
        actual = float(project.actual_hours or 0)
        if quoted > 0 and actual > quoted * 0.85:
            reasons.append("Hours burn approaching quote")
            if predicted:
                predicted = predicted + timedelta(days=3)
            confidence -= 8

        designer_id = project.designer_id
        if designer_id:
            util_rows = get_designer_utilization(ctx)
            match = next((r for r in util_rows if r["user"].id == designer_id), None)
            if match and match["utilization"] >= 95:
                reasons.append("Designer overloaded")
                if predicted:
                    predicted = predicted + timedelta(days=2)
                confidence -= 5

        if not reasons:
            reasons.append("On track based on current milestone and hours data")

        return SchedulePrediction(
            project_id=project.id,
            tool_number=project.tool_number,
            predicted_completion=predicted,
            target_completion=project.due_date,
            confidence_percent=confidence_from_sample_size(len(milestones), base=confidence - 10),
            reasons=reasons,
            late_milestones=len(late),
            bottleneck=reasons[0] if reasons else None,
        )

    def capacity_forecast(self, ctx: AiContext, *, horizon_days: int) -> CapacityForecast:
        util_rows = get_designer_utilization(ctx)
        headcount = len(util_rows) or 1
        weekly_capacity = headcount * 40
        weeks = max(horizon_days / 7, 1)
        total_capacity = weekly_capacity * weeks

        active = get_active_projects(ctx)
        remaining_hours = sum(
            max(float(p.quoted_hours or 0) - float(p.actual_hours or 0), 0) for p in active
        )
        projected_util = round_hours(
            Decimal(str(min(remaining_hours / total_capacity * 100, 150) if total_capacity else 0))
        )
        idle = max(0, total_capacity - remaining_hours)

        hiring = None
        if projected_util > 110:
            hiring = f"Consider adding capacity — projected utilization {projected_util}% over {horizon_days} days"
        elif projected_util < 60:
            hiring = f"Idle capacity available — {round_hours(Decimal(str(idle)))} hours free"

        customer_demand = []
        month_start = ctx.today.replace(day=1)
        rows = ctx.db.execute(
            select(
                Project.customer_id,
                func.count(),
                func.coalesce(func.sum(Project.quoted_hours - Project.actual_hours), 0),
            )
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(
                    (ExecutionStatus.planning, ExecutionStatus.currently_being_worked_on)
                ),
                Project.due_date.is_not(None),
                Project.due_date <= ctx.today + timedelta(days=horizon_days),
            )
            .group_by(Project.customer_id)
        ).all()
        for customer_id, count, hours in rows:
            customer_demand.append(
                {"customer_id": str(customer_id), "projects": count, "remaining_hours": float(hours or 0)}
            )

        return CapacityForecast(
            horizon_days=horizon_days,
            total_capacity_hours=float(total_capacity),
            projected_utilization_percent=float(projected_util),
            idle_capacity_hours=float(idle),
            hiring_recommendation=hiring,
            peak_period=f"Next {horizon_days} days" if projected_util > 85 else None,
            customer_demand=customer_demand,
        )


forecaster = Forecaster()
