"""Engineering data-quality checks: records that make schedules and KPIs unreliable.

Checks only flag records; nothing is changed. Project checks respect the
viewer's project visibility so a team lead only sees their own teams' gaps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, ProjectClassification, UserType
from app.models.models import Customer, Project, ProjectStageEstimate, Team, User

MAX_ITEMS = 50

_CLOSED = (ExecutionStatus.completed, ExecutionStatus.cancelled)


@dataclass
class _Check:
    code: str
    label: str
    severity: str
    description: str
    items: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "severity": self.severity,
            "description": self.description,
            "count": len(self.items),
            "items": self.items[:MAX_ITEMS],
        }


def _project_item(project: Project, detail: str | None = None) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "kind": "project",
        "label": project.code or project.tool_number,
        "description": project.part_description,
        "detail": detail,
    }


def _normalise_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def build_engineering_data_quality(db: Session, *, visibility_clause=None) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    stmt = select(Project).where(Project.is_deleted.is_(False))
    if visibility_clause is not None:
        stmt = stmt.where(visibility_clause)
    projects = list(db.scalars(stmt).all())
    live = [p for p in projects if p.execution_status not in _CLOSED and not p.is_archived]

    configured = set(
        db.scalars(
            select(ProjectStageEstimate.project_id)
            .where(ProjectStageEstimate.project_id.in_([p.id for p in live] or [UUID(int=0)]))
            .distinct()
        ).all()
    )
    disabled_teams = {
        row.id: row.name
        for row in db.scalars(select(Team).where(Team.projects_enabled.is_(False))).all()
    }
    virtual_users = {
        row.id: (f"{row.first_name or ''} {row.last_name or ''}".strip() or row.email)
        for row in db.scalars(select(User).where(User.user_type == UserType.virtual)).all()
    }

    completed_no_date = _Check(
        "completed_without_date",
        "Completed without a completion date",
        "high",
        "Excluded from Engineering Performance because the completion period is unknown. "
        "Set the actual completion date on the project.",
    )
    future_completion = _Check(
        "completion_in_future",
        "Completion date in the future",
        "high",
        "Completed projects cannot finish after today; correct the actual completion date.",
    )
    no_start = _Check(
        "live_without_start_date",
        "Active project without a start date",
        "medium",
        "No baseline or forecast can be calculated until a start date is set.",
    )
    no_stage = _Check(
        "full_design_without_stage_estimates",
        "Full design without stage hours",
        "medium",
        "Blockout, Intermediate and Final Design hours are missing, so stage variance and "
        "scheduling use quoted hours only.",
    )
    no_team = _Check(
        "live_without_team",
        "Active project without a team",
        "medium",
        "The project does not appear under any team on the Projects page or in team reports.",
    )
    disabled_team = _Check(
        "team_not_enabled_for_projects",
        "Project owned by a team not enabled for projects",
        "low",
        "The team was switched off for projects after this project was assigned. Move the project "
        "or re-enable the team.",
    )
    due_before_start = _Check(
        "due_before_start",
        "Due date before start date",
        "high",
        "The schedule cannot be valid; correct the start or due date.",
    )
    virtual_assignee = _Check(
        "virtual_user_assigned",
        "Virtual account assigned to active work",
        "medium",
        "Virtual/system accounts are excluded from capacity; assign a real employee.",
    )

    for project in projects:
        if project.execution_status == ExecutionStatus.completed:
            if project.completed_at is None:
                completed_no_date.items.append(_project_item(project))
            elif project.completed_at.date() > today:
                future_completion.items.append(
                    _project_item(project, f"Completed {project.completed_at.date().isoformat()}")
                )
        if project.start_date and project.due_date and project.due_date < project.start_date:
            due_before_start.items.append(
                _project_item(
                    project,
                    f"Start {project.start_date.isoformat()}, due {project.due_date.isoformat()}",
                )
            )

    for project in live:
        if project.start_date is None:
            no_start.items.append(_project_item(project))
        if (
            project.project_classification == ProjectClassification.full_design
            and project.id not in configured
        ):
            no_stage.items.append(_project_item(project))
        if project.team_id is None:
            no_team.items.append(_project_item(project))
        elif project.team_id in disabled_teams:
            disabled_team.items.append(_project_item(project, disabled_teams[project.team_id]))
        assigned = [
            virtual_users[user_id]
            for user_id in (project.design_leader_id, project.designer_id, project.surfacer_id)
            if user_id in virtual_users
        ]
        if assigned:
            virtual_assignee.items.append(_project_item(project, ", ".join(assigned)))

    duplicate_customers = _Check(
        "possible_duplicate_customers",
        "Possible duplicate customers",
        "low",
        "Active customers whose names differ only by case, spacing or punctuation. Merge or "
        "rename them so reports do not split one customer in two.",
    )
    groups: dict[str, list[Customer]] = {}
    for customer in db.scalars(select(Customer).where(Customer.is_active.is_(True))).all():
        key = _normalise_name(customer.name)
        if key:
            groups.setdefault(key, []).append(customer)
    for rows in groups.values():
        if len(rows) > 1:
            names = sorted(row.name for row in rows)
            duplicate_customers.items.append(
                {
                    "id": str(rows[0].id),
                    "kind": "customer",
                    "label": " / ".join(names),
                    "description": None,
                    "detail": f"{len(rows)} records",
                }
            )

    checks = [
        completed_no_date,
        future_completion,
        due_before_start,
        no_start,
        no_stage,
        no_team,
        virtual_assignee,
        disabled_team,
        duplicate_customers,
    ]
    payload = [check.as_dict() for check in checks]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "projects_checked": len(projects),
        "total_issues": sum(item["count"] for item in payload),
        "checks": payload,
    }
