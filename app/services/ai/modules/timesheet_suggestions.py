"""Auto timesheet suggestions based on historical patterns."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.models.models import Project, TaskType, Timesheet, TimesheetEntry, User
from app.schemas.ai import TimesheetSuggestion
from app.services.ai.base import AiContext, AiModule, round_hours


class TimesheetSuggestionsModule(AiModule):
    name = "timesheet_suggestions"

    def run(self, ctx: AiContext, **kwargs: Any) -> list[TimesheetSuggestion]:
        user_id = kwargs.get("user_id")
        if user_id is None:
            return []

        user = ctx.db.get(User, UUID(str(user_id)))
        if user is None:
            return []

        yesterday = ctx.today - timedelta(days=1)
        suggestions: list[TimesheetSuggestion] = []

        yesterday_entries = list(
            ctx.db.scalars(
                select(TimesheetEntry)
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    Timesheet.user_id == user.id,
                    TimesheetEntry.entry_date == yesterday,
                    TimesheetEntry.is_deleted.is_(False),
                )
                .order_by(TimesheetEntry.hours.desc())
            ).all()
        )

        for entry in yesterday_entries[:3]:
            project = ctx.db.get(Project, entry.project_id) if entry.project_id else None
            task = ctx.db.get(TaskType, entry.task_type_id) if entry.task_type_id else None
            suggestions.append(
                TimesheetSuggestion(
                    entry_date=ctx.today,
                    project_id=entry.project_id,
                    tool_number=project.tool_number if project else None,
                    task_type_id=entry.task_type_id,
                    task_name=task.name if task else None,
                    suggested_hours=round_hours(entry.hours),
                    reason="Repeat yesterday's entry",
                    confidence=85,
                )
            )

        # Suggest remaining hours on active assigned project
        active_project = ctx.db.scalar(
            select(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                (Project.designer_id == user.id) | (Project.surfacer_id == user.id),
            )
            .order_by(Project.due_date.asc().nullslast())
        )
        if active_project:
            remaining = max(
                float(active_project.quoted_hours or 0) - float(active_project.actual_hours or 0),
                0,
            )
            if remaining > 0:
                suggestions.append(
                    TimesheetSuggestion(
                        entry_date=ctx.today,
                        project_id=active_project.id,
                        tool_number=active_project.tool_number,
                        suggested_hours=min(8, round_hours(remaining)),
                        reason=f"Continue work on {active_project.tool_number} ({round_hours(remaining)}h remaining)",
                        confidence=75,
                    )
                )

        return suggestions[:5]
