"""Productivity analytics module."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus, MilestoneStatus
from app.models.intelligence import EngineeringChange
from app.models.models import Milestone, Project, Role, Timesheet, TimesheetEntry, User
from app.schemas.ai import ProductivityMetrics
from app.services.ai.base import AiContext, AiModule, round_hours
from app.services.ai.context import DESIGN_ROLES


class ProductivityAnalyticsModule(AiModule):
    name = "productivity_analytics"

    def run(self, ctx: AiContext, **kwargs: Any) -> list[ProductivityMetrics]:
        user_id = kwargs.get("user_id")
        team_id = kwargs.get("team_id")
        month_start = ctx.today.replace(day=1)

        users_stmt = (
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(
                Role.name.in_(DESIGN_ROLES),
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )
        if user_id:
            users_stmt = users_stmt.where(User.id == UUID(str(user_id)))
        if team_id:
            users_stmt = users_stmt.where(User.team_id == UUID(str(team_id)))

        users = list(ctx.db.scalars(users_stmt).all())
        results: list[ProductivityMetrics] = []

        for person in users:
            hours = float(
                ctx.db.scalar(
                    select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                    .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                    .where(
                        Timesheet.user_id == person.id,
                        TimesheetEntry.entry_date >= month_start,
                        TimesheetEntry.is_deleted.is_(False),
                    )
                )
                or 0
            )
            billable = float(
                ctx.db.scalar(
                    select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                    .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                    .where(
                        Timesheet.user_id == person.id,
                        TimesheetEntry.entry_date >= month_start,
                        TimesheetEntry.is_billable.is_(True),
                        TimesheetEntry.is_deleted.is_(False),
                    )
                )
                or 0
            )
            completed = int(
                ctx.db.scalar(
                    select(func.count())
                    .select_from(Project)
                    .where(
                        Project.is_deleted.is_(False),
                        Project.execution_status == ExecutionStatus.completed,
                        (Project.designer_id == person.id)
                        | (Project.surfacer_id == person.id),
                        Project.completed_at.is_not(None),
                        Project.completed_at >= month_start,
                    )
                )
                or 0
            )
            milestones_done = int(
                ctx.db.scalar(
                    select(func.count())
                    .select_from(Milestone)
                    .join(Project, Milestone.project_id == Project.id)
                    .where(
                        Milestone.status == MilestoneStatus.completed,
                        Milestone.completed_at.is_not(None),
                        Milestone.completed_at >= month_start,
                        (Project.designer_id == person.id) | (Project.surfacer_id == person.id),
                    )
                )
                or 0
            )
            ec_count = int(
                ctx.db.scalar(
                    select(func.count())
                    .select_from(EngineeringChange)
                    .join(Project, EngineeringChange.project_id == Project.id)
                    .where(
                        (Project.designer_id == person.id) | (Project.surfacer_id == person.id)
                    )
                )
                or 0
            )

            achievements: list[str] = []
            if completed >= 2:
                achievements.append(f"Completed {completed} projects this month")
            if milestones_done >= 5:
                achievements.append(f"Closed {milestones_done} milestones")
            billable_pct = (billable / hours * 100) if hours else 0
            if billable_pct >= 85:
                achievements.append(f"Strong billable ratio ({billable_pct:.0f}%)")

            results.append(
                ProductivityMetrics(
                    user_id=person.id,
                    user_name=f"{person.first_name} {person.last_name}".strip(),
                    projects_completed=completed,
                    billable_percent=round(billable_pct, 1),
                    hours_logged=round_hours(hours),
                    milestones_completed=milestones_done,
                    engineering_changes=ec_count,
                    trend="up" if completed >= 1 else "stable",
                    achievements=achievements,
                )
            )

        return sorted(results, key=lambda r: r.hours_logged, reverse=True)
