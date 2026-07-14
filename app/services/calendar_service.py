"""Engineering calendar aggregation."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.non_productive_categories import leave_entry_clause
from app.crud.foundation import holiday
from app.models.enums import MilestoneStatus
from app.models.models import Customer, Milestone, Project, Team, Timesheet, TimesheetEntry, User
from app.schemas.calendar import CalendarEvent, ProjectTimelineBar


def get_engineering_calendar(
    db: Session,
    *,
    start_date: date,
    end_date: date,
) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []

    milestones = db.execute(
        select(Milestone, Project.tool_number, Project.customer_id)
        .join(Project, Milestone.project_id == Project.id)
        .where(
            Milestone.due_date.is_not(None),
            Milestone.due_date >= start_date,
            Milestone.due_date <= end_date,
            Project.is_deleted.is_(False),
        )
    ).all()
    for milestone, tool_number, _customer_id in milestones:
        category = "milestone_due"
        if milestone.status == MilestoneStatus.completed:
            category = "milestone_completed"
        elif milestone.due_date and milestone.due_date < date.today():
            category = "milestone_overdue"
        events.append(
            CalendarEvent(
                id=str(milestone.id),
                title=f"{tool_number} — {milestone.name}",
                date=milestone.due_date,
                category=category,
                project_id=milestone.project_id,
                milestone_id=milestone.id,
            )
        )

    for row in holiday.list(db):
        if start_date <= row.holiday_date <= end_date:
            events.append(
                CalendarEvent(
                    id=str(row.id),
                    title=row.name,
                    date=row.holiday_date,
                    category="holiday",
                )
            )

    project_due = db.scalars(
        select(Project).where(
            Project.due_date.is_not(None),
            Project.due_date >= start_date,
            Project.due_date <= end_date,
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
        )
    ).all()
    for project in project_due:
        events.append(
            CalendarEvent(
                id=f"project-due-{project.id}",
                title=f"Delivery — {project.tool_number}",
                date=project.due_date,
                category="customer_delivery",
                project_id=project.id,
            )
        )

    leave_rows = db.execute(
        select(
            Timesheet.user_id,
            TimesheetEntry.entry_date,
            func.coalesce(func.sum(TimesheetEntry.leave_count), 0),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            TimesheetEntry.entry_date >= start_date,
            TimesheetEntry.entry_date <= end_date,
            TimesheetEntry.is_deleted.is_(False),
            leave_entry_clause(),
        )
        .group_by(Timesheet.user_id, TimesheetEntry.entry_date)
    ).all()
    for user_id, entry_date, leave_count in leave_rows:
        if float(leave_count or 0) <= 0:
            continue
        events.append(
            CalendarEvent(
                id=f"leave-{user_id}-{entry_date.isoformat()}",
                title="Leave",
                date=entry_date,
                category="leave",
                user_id=user_id,
            )
        )

    month_end = date.today().replace(day=1) + timedelta(days=32)
    month_end = month_end.replace(day=1) - timedelta(days=1)
    if start_date <= month_end <= end_date:
        events.append(
            CalendarEvent(
                id=f"timesheet-deadline-{month_end.isoformat()}",
                title="Timesheet month-end",
                date=month_end,
                category="timesheet_deadline",
            )
        )

    events.sort(key=lambda item: (item.date, item.title))
    return events


def _user_display_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
    return name or None


def get_project_timeline(
    db: Session,
    user: User,
    *,
    start_date: date,
    end_date: date,
    team_id: UUID | None = None,
) -> list[ProjectTimelineBar]:
    """Scoped project Gantt bars: created_at → due_date (or completed_at)."""
    from app.core.team_access import project_visibility_clause
    from app.services.project_calculation_service import batch_calculate_progress

    visibility = project_visibility_clause(db, user)
    filters = [
        Project.is_deleted.is_(False),
        Project.is_archived.is_(False),
    ]
    if visibility is not None:
        filters.append(visibility)
    if team_id is not None:
        filters.append(Project.team_id == team_id)

    projects = list(db.scalars(select(Project).where(*filters)).all())
    if not projects:
        return []

    customer_ids = {p.customer_id for p in projects if p.customer_id}
    team_ids = {p.team_id for p in projects if p.team_id}
    user_ids = {
        uid
        for p in projects
        for uid in (p.designer_id, p.surfacer_id)
        if uid
    }

    customers = {
        c.id: c
        for c in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
    } if customer_ids else {}
    teams = {
        t.id: t for t in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
    } if team_ids else {}
    users = {
        u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    } if user_ids else {}

    progress_map = batch_calculate_progress(db, [p.id for p in projects])

    bars: list[ProjectTimelineBar] = []
    for project in projects:
        created = project.created_at
        if created is None:
            continue
        bar_start = created.date() if hasattr(created, "date") else created
        due_missing = project.due_date is None
        if project.due_date is not None:
            bar_end = project.due_date
        elif project.completed_at is not None:
            completed = project.completed_at
            bar_end = completed.date() if hasattr(completed, "date") else completed
        else:
            bar_end = bar_start

        # Include bar when it overlaps the requested window
        if bar_end < start_date or bar_start > end_date:
            continue

        health = project.health.value if hasattr(project.health, "value") else str(project.health)
        status = (
            project.execution_status.value
            if hasattr(project.execution_status, "value")
            else str(project.execution_status)
        )
        progress = progress_map.get(project.id)
        customer = customers.get(project.customer_id)
        team = teams.get(project.team_id) if project.team_id else None

        bars.append(
            ProjectTimelineBar(
                project_id=project.id,
                tool_number=project.tool_number,
                customer_name=customer.name if customer else None,
                team_id=project.team_id,
                team_name=team.name if team else None,
                health=health,
                execution_status=status,
                designer_name=_user_display_name(users.get(project.designer_id)),
                surfacer_name=_user_display_name(users.get(project.surfacer_id)),
                start_date=bar_start,
                end_date=bar_end,
                progress_percent=float(progress.progress_percent) if progress else 0.0,
                due_date_missing=due_missing and project.completed_at is None,
            )
        )

    bars.sort(
        key=lambda bar: (
            bar.team_name or "zzz",
            bar.start_date,
            bar.tool_number,
        )
    )
    return bars
