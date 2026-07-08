"""Executive KPI wall — full-screen operational display."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus, MilestoneStatus
from app.models.models import Customer, Milestone, Project, TimesheetEntry
from app.schemas.ai import ExecutiveWallData
from app.services.ai.base import AiContext, AiModule, round_hours
from app.services.ai.context import (
    count_overdue_milestones,
    get_active_projects,
    get_customer_workload_share,
    get_designer_utilization,
)
from app.services.dashboard_service import get_attention_projects
from app.services.project_calculation_service import count_projects_by_health


class ExecutiveWallModule(AiModule):
    name = "executive_wall"

    def run(self, ctx: AiContext, **kwargs: Any) -> ExecutiveWallData:
        active = get_active_projects(ctx)
        util = get_designer_utilization(ctx)
        avg_util = sum(r["utilization"] for r in util) / len(util) if util else 0
        health_counts = count_projects_by_health(ctx.db)
        health = {"green": health_counts[0], "yellow": health_counts[1], "red": health_counts[2]}
        month_start = ctx.today.replace(day=1)

        hours_month = float(
            ctx.db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                    TimesheetEntry.entry_date >= month_start,
                    TimesheetEntry.is_deleted.is_(False),
                )
            )
            or 0
        )

        attention = get_attention_projects(ctx.db, limit=10)
        deliveries = [
            {
                "tool_number": row.tool_number,
                "customer_name": row.customer_name,
                "due_date": str(row.due_date) if row.due_date else None,
                "reason": row.attention_reason,
            }
            for row in attention
            if row.attention_reason in ("due_soon", "overdue")
        ]

        recent_releases = [
            {
                "tool_number": p.tool_number,
                "completed_at": str(p.completed_at.date()) if p.completed_at else None,
            }
            for p in ctx.db.scalars(
                select(Project)
                .where(
                    Project.execution_status == ExecutionStatus.completed,
                    Project.completed_at.is_not(None),
                    Project.completed_at >= ctx.today - timedelta(days=30),
                )
                .order_by(Project.completed_at.desc())
                .limit(8)
            ).all()
        ]

        customer_dist = get_customer_workload_share(ctx)
        capacity = len(util) * 40 * 4  # rough monthly team capacity

        return ExecutiveWallData(
            active_projects=len(active),
            utilization_percent=round(avg_util, 1),
            late_milestones=count_overdue_milestones(ctx),
            current_deliveries=deliveries,
            recent_releases=recent_releases,
            capacity_hours=float(capacity),
            hours_logged_month=round_hours(hours_month),
            customer_distribution=customer_dist[:6],
            health_summary=health,
        )
