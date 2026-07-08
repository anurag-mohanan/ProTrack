"""Engineering calendar aggregation."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.non_productive_categories import leave_entry_clause
from app.crud.foundation import holiday
from app.models.enums import MilestoneStatus
from app.models.models import Milestone, Project, Timesheet, TimesheetEntry
from app.schemas.calendar import CalendarEvent


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
