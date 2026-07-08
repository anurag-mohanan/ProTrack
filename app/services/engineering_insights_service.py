"""Rule-based engineering insights from live project and timesheet data."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import project_assignment_filter
from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth, ProjectStage
from app.models.models import Customer, Milestone, Project, Timesheet, TimesheetEntry, User
from app.schemas.dashboard import EngineeringInsight


def _round_hours(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1")))


def _similar_completed_projects(
    db: Session,
    *,
    customer_id: UUID | None,
    project_type_id: UUID | None,
    limit: int = 3,
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
        .limit(limit * 4)
    )
    if customer_id is not None:
        stmt = stmt.where(Project.customer_id == customer_id)
    if project_type_id is not None:
        stmt = stmt.where(Project.project_type_id == project_type_id)
    rows = list(db.scalars(stmt).all())
    return rows[:limit]


def generate_engineering_insights(db: Session, *, limit: int = 8) -> list[EngineeringInsight]:
    today = date.today()
    insights: list[EngineeringInsight] = []

    active_projects = list(
        db.scalars(
            select(Project).where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(
                    (
                        ExecutionStatus.planning,
                        ExecutionStatus.currently_being_worked_on,
                        ExecutionStatus.on_hold,
                    )
                ),
            )
        ).all()
    )

    overdue_risk = [
        project
        for project in active_projects
        if project.due_date is not None
        and project.due_date < today + timedelta(days=7)
        and project.execution_status != ExecutionStatus.completed
    ]
    if overdue_risk:
        insights.append(
            EngineeringInsight(
                category="planning",
                severity="warning",
                title=f"{len(overdue_risk)} project{'s' if len(overdue_risk) != 1 else ''} likely to become overdue",
                detail="Review due dates and reallocate resources before milestones slip.",
                href="/projects?due=week",
            )
        )

    behind_milestones = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .join(Project, Milestone.project_id == Project.id)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(
                    (
                        ExecutionStatus.planning,
                        ExecutionStatus.currently_being_worked_on,
                        ExecutionStatus.on_hold,
                    )
                ),
                Milestone.status != MilestoneStatus.completed,
                Milestone.due_date.is_not(None),
                Milestone.due_date < today,
            )
        )
        or 0
    )
    if behind_milestones:
        insights.append(
            EngineeringInsight(
                category="planning",
                severity="error",
                title=f"{behind_milestones} milestone{'s' if behind_milestones != 1 else ''} behind schedule",
                detail="Prioritize overdue milestones to protect customer delivery dates.",
                href="/projects",
            )
        )

    over_planned = [
        project
        for project in active_projects
        if float(project.quoted_hours or 0) > 0
        and float(project.actual_hours or 0) > float(project.quoted_hours or 0) * 0.9
    ]
    if over_planned:
        insights.append(
            EngineeringInsight(
                category="planning",
                severity="warning",
                title=f"{len(over_planned)} project{'s' if len(over_planned) != 1 else ''} trending over planned hours",
                detail="Quoted hours are nearly or fully consumed on active tools.",
                href="/reports?tab=project-hours",
            )
        )

    gt3_at_risk = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .join(Project, Milestone.project_id == Project.id)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(
                    (
                        ExecutionStatus.planning,
                        ExecutionStatus.currently_being_worked_on,
                    )
                ),
                Milestone.name.ilike("%GT3%"),
                Milestone.status != MilestoneStatus.completed,
                Milestone.due_date.is_not(None),
                Milestone.due_date <= today + timedelta(days=14),
            )
        )
        or 0
    )
    if gt3_at_risk:
        insights.append(
            EngineeringInsight(
                category="planning",
                severity="error",
                title=f"{gt3_at_risk} project{'s' if gt3_at_risk != 1 else ''} at risk of missing GT3",
                detail="GT3 milestones are due within two weeks and still open.",
                href="/projects",
            )
        )

    week_end = today + timedelta(days=7)
    workload_rows = db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .where(
            TimesheetEntry.entry_date >= today,
            TimesheetEntry.entry_date <= week_end,
            TimesheetEntry.is_deleted.is_(False),
            User.is_active.is_(True),
        )
        .group_by(User.id, User.first_name, User.last_name)
        .order_by(func.coalesce(func.sum(TimesheetEntry.hours), 0).desc())
        .limit(1)
    ).first()
    if workload_rows:
        user_id, first, last, hours = workload_rows
        capacity = 40
        if float(hours) >= capacity * 0.95:
            name = f"{first} {last}".strip()
            insights.append(
                EngineeringInsight(
                    category="resource",
                    severity="warning",
                    title=f"{name} will exceed capacity next week",
                    detail=f"Already { _round_hours(Decimal(str(hours))) } hours scheduled in the next 7 days.",
                    href="/workload",
                )
            )

    customer_hours = db.execute(
        select(
            Customer.name,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Project, Project.customer_id == Customer.id)
        .join(TimesheetEntry, TimesheetEntry.project_id == Project.id)
        .where(
            TimesheetEntry.entry_date >= today.replace(day=1),
            TimesheetEntry.is_deleted.is_(False),
            Project.is_deleted.is_(False),
        )
        .group_by(Customer.id, Customer.name)
        .order_by(func.coalesce(func.sum(TimesheetEntry.hours), 0).desc())
        .limit(1)
    ).first()
    total_month_hours = float(
        db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                TimesheetEntry.entry_date >= today.replace(day=1),
                TimesheetEntry.is_deleted.is_(False),
            )
        )
        or 0
    )
    if customer_hours and total_month_hours > 0:
        customer_name, hours = customer_hours
        share = round(float(hours) / total_month_hours * 100)
        if share >= 35:
            insights.append(
                EngineeringInsight(
                    category="resource",
                    severity="info",
                    title=f"{customer_name} currently consumes {share}% of engineering capacity",
                    detail="Consider balancing workload across customers for delivery resilience.",
                    href="/reports?tab=customer-summary",
                )
            )

    # Quoting insight from most recent active project without quote
    quote_candidate = next(
        (
            project
            for project in sorted(
                active_projects,
                key=lambda row: row.created_at or today,
                reverse=True,
            )
            if float(project.quoted_hours or 0) <= 0
        ),
        None,
    )
    if quote_candidate:
        similar = _similar_completed_projects(
            db,
            customer_id=quote_candidate.customer_id,
            project_type_id=quote_candidate.project_type_id,
            limit=1,
        )
        if similar:
            reference = similar[0]
            avg_hours = float(reference.actual_hours or 0)
            low = max(1, round(avg_hours * 0.95))
            high = max(low + 5, round(avg_hours * 1.08))
            insights.append(
                EngineeringInsight(
                    category="quoting",
                    severity="info",
                    title=(
                        f"Tool {quote_candidate.tool_number} is similar to {reference.tool_number}"
                    ),
                    detail=(
                        f"Historical average was {round(avg_hours)} hours. "
                        f"Recommended quote: {low}–{high} hours."
                    ),
                    href=f"/projects/{quote_candidate.id}",
                )
            )

    red_count = sum(1 for project in active_projects if project.health == ProjectHealth.red)
    if red_count:
        insights.append(
            EngineeringInsight(
                category="planning",
                severity="error",
                title=f"{red_count} active project{'s' if red_count != 1 else ''} in critical health",
                detail="Review overdue tools and hours burn immediately.",
                href="/projects",
            )
        )

    return insights[:limit]
