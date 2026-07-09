"""Shared data gatherers for AI modules."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, MilestoneStatus, TimesheetStatus
from app.models.intelligence import EngineeringChange
from app.models.enums import EngineeringChangeStatus
from app.models.models import Customer, Milestone, Project, Role, Timesheet, TimesheetEntry, User
from datetime import date

from app.models.models import User
from app.services.ai.base import AiContext, round_hours


def build_ai_context(
    db: Session,
    *,
    user: User | None = None,
    today: date | None = None,
) -> AiContext:
    """Build AiContext from a User — avoids invalid ``actor=`` kwargs."""
    actor_id = user.id if user is not None else None
    actor_name: str | None = None
    if user is not None:
        parts = [user.first_name or "", user.last_name or ""]
        actor_name = " ".join(part for part in parts if part).strip() or user.email
    return AiContext(
        db=db,
        today=today or date.today(),
        actor_id=actor_id,
        actor_name=actor_name,
    )

ACTIVE_STATUSES = (
    ExecutionStatus.planning,
    ExecutionStatus.currently_being_worked_on,
    ExecutionStatus.on_hold,
)

from app.services.kpi_participation import engineering_productivity_users


def get_active_projects(ctx: AiContext) -> list[Project]:
    cached = ctx.extras.get("active_projects")
    if cached is not None:
        return cached
    rows = list(
        ctx.db.scalars(
            select(Project).where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(ACTIVE_STATUSES),
            )
        ).all()
    )
    ctx.extras["active_projects"] = rows
    return rows


def get_completed_projects(
    ctx: AiContext,
    *,
    customer_id=None,
    project_type_id=None,
    limit: int = 50,
) -> list[Project]:
    stmt = (
        select(Project)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status == ExecutionStatus.completed,
            Project.actual_hours > 0,
        )
        .order_by(Project.completed_at.desc().nullslast(), Project.updated_at.desc())
        .limit(limit)
    )
    if customer_id is not None:
        stmt = stmt.where(Project.customer_id == customer_id)
    if project_type_id is not None:
        stmt = stmt.where(Project.project_type_id == project_type_id)
    return list(ctx.db.scalars(stmt).all())


def count_overdue_milestones(ctx: AiContext) -> int:
    return int(
        ctx.db.scalar(
            select(func.count())
            .select_from(Milestone)
            .join(Project, Milestone.project_id == Project.id)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(ACTIVE_STATUSES),
                Milestone.status != MilestoneStatus.completed,
                Milestone.due_date.is_not(None),
                Milestone.due_date < ctx.today,
            )
        )
        or 0
    )


def get_designer_utilization(ctx: AiContext) -> list[dict]:
    cached = ctx.extras.get("designer_utilization")
    if cached is not None:
        return cached

    week_end = ctx.week_end or ctx.today
    users = engineering_productivity_users(ctx.db)

    rows: list[dict] = []
    capacity = 40.0
    for person in users:
        hours = float(
            ctx.db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    Timesheet.user_id == person.id,
                    TimesheetEntry.entry_date >= ctx.week_start,
                    TimesheetEntry.entry_date <= week_end,
                    TimesheetEntry.is_deleted.is_(False),
                )
            )
            or 0
        )
        active_count = int(
            ctx.db.scalar(
                select(func.count())
                .select_from(Project)
                .where(
                    Project.is_deleted.is_(False),
                    Project.is_archived.is_(False),
                    Project.execution_status.in_(ACTIVE_STATUSES),
                    (Project.designer_id == person.id)
                    | (Project.surfacer_id == person.id)
                    | (Project.design_leader_id == person.id),
                )
            )
            or 0
        )
        utilization = round_hours(Decimal(str(hours / capacity * 100))) if capacity else 0
        rows.append(
            {
                "user": person,
                "hours": hours,
                "utilization": utilization,
                "available_hours": max(0, capacity - hours),
                "active_projects": active_count,
            }
        )

    ctx.extras["designer_utilization"] = rows
    return rows


def get_customer_workload_share(ctx: AiContext) -> list[dict]:
    month_start = ctx.today.replace(day=1)
    rows = ctx.db.execute(
        select(
            Customer.id,
            Customer.name,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Project, Project.customer_id == Customer.id)
        .join(TimesheetEntry, TimesheetEntry.project_id == Project.id)
        .where(
            TimesheetEntry.entry_date >= month_start,
            TimesheetEntry.is_deleted.is_(False),
            Project.is_deleted.is_(False),
        )
        .group_by(Customer.id, Customer.name)
        .order_by(func.coalesce(func.sum(TimesheetEntry.hours), 0).desc())
    ).all()
    total = sum(float(hours) for _, _, hours in rows) or 1
    return [
        {
            "customer_id": customer_id,
            "customer_name": name,
            "hours": float(hours),
            "share_percent": round(float(hours) / total * 100),
        }
        for customer_id, name, hours in rows
    ]


def get_open_engineering_changes(ctx: AiContext) -> int:
    return int(
        ctx.db.scalar(
            select(func.count())
            .select_from(EngineeringChange)
            .join(Project, EngineeringChange.project_id == Project.id)
            .where(
                Project.is_deleted.is_(False),
                EngineeringChange.status == EngineeringChangeStatus.open,
            )
        )
        or 0
    )


def get_stale_milestones(ctx: AiContext, *, days: int = 7) -> int:
    cutoff = ctx.today - timedelta(days=days)
    return int(
        ctx.db.scalar(
            select(func.count())
            .select_from(Milestone)
            .join(Project, Milestone.project_id == Project.id)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(ACTIVE_STATUSES),
                Milestone.status != MilestoneStatus.completed,
                Milestone.updated_at < cutoff,
            )
        )
        or 0
    )


def get_pending_draft_timesheets(ctx: AiContext) -> int:
    return int(
        ctx.db.scalar(
            select(func.count())
            .select_from(Timesheet)
            .where(Timesheet.status == TimesheetStatus.draft)
        )
        or 0
    )
