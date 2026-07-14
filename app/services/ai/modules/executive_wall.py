"""Executive KPI wall — full-screen operational display for Program / Eng Managers."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus, ProjectHealth
from app.models.models import Customer, Project, Team, TimesheetEntry
from app.schemas.ai import ExecutiveWallData, WallProjectCard, WallTeamLiveBlock
from app.services.ai.base import AiContext, AiModule, round_hours
from app.services.ai.context import (
    count_overdue_milestones,
    get_active_projects,
    get_customer_workload_share,
    get_designer_utilization,
)
from app.services.dashboard_service import (
    _batch_current_milestones,
    _batch_designer_names,
    get_attention_projects,
)
from app.services.project_calculation_service import count_projects_by_health


def _health_value(project: Project) -> str:
    health = project.health or ProjectHealth.green
    return health.value if hasattr(health, "value") else str(health)


def _status_value(project: Project) -> str:
    status = project.execution_status
    return status.value if hasattr(status, "value") else str(status)


def _stage_value(project: Project) -> str | None:
    stage = getattr(project, "project_stage", None)
    if stage is None:
        return None
    return stage.value if hasattr(stage, "value") else str(stage)


def _card_from_project(
    project: Project,
    *,
    customer_name: str | None,
    designer_name: str | None,
    team_name: str | None,
    milestone: str | None = None,
    attention_reason: str | None = None,
) -> WallProjectCard:
    return WallProjectCard(
        project_id=project.id,
        tool_number=project.tool_number or "—",
        customer_name=customer_name,
        designer_name=designer_name,
        team_name=team_name,
        due_date=project.due_date,
        health=_health_value(project),
        execution_status=_status_value(project),
        project_stage=_stage_value(project),
        current_milestone=milestone,
        attention_reason=attention_reason,
    )


def _build_teams_live(ctx: AiContext, active: list[Project]) -> list[WallTeamLiveBlock]:
    if not active:
        return []

    team_ids = {project.team_id for project in active if project.team_id}
    team_names: dict[UUID, str] = {}
    if team_ids:
        team_names = {
            row.id: row.name
            for row in ctx.db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
        }

    customer_ids = {project.customer_id for project in active if project.customer_id}
    customer_names: dict[UUID, str] = {}
    if customer_ids:
        customer_names = {
            row.id: row.name
            for row in ctx.db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
        }

    designer_names = _batch_designer_names(ctx.db, active)
    milestone_names = _batch_current_milestones(ctx.db, [project.id for project in active])

    grouped: dict[tuple[str, UUID | None], list[WallProjectCard]] = defaultdict(list)
    for project in active:
        team_id = project.team_id
        team_name = team_names.get(team_id, "Unassigned") if team_id else "Unassigned"
        grouped[(team_name, team_id)].append(
            _card_from_project(
                project,
                customer_name=customer_names.get(project.customer_id),
                designer_name=designer_names.get(project.id),
                team_name=team_name,
                milestone=milestone_names.get(project.id),
            )
        )

    blocks: list[WallTeamLiveBlock] = []
    for (team_name, team_id), projects in sorted(
        grouped.items(),
        key=lambda item: (item[0][0] == "Unassigned", item[0][0].lower()),
    ):
        projects_sorted = sorted(
            projects,
            key=lambda card: (
                0 if card.health == "red" else 1 if card.health == "yellow" else 2,
                card.due_date or ctx.today,
                card.tool_number,
            ),
        )
        blocks.append(
            WallTeamLiveBlock(
                team_id=team_id,
                team_name=team_name,
                active_count=len(projects_sorted),
                red_count=sum(1 for card in projects_sorted if card.health == "red"),
                yellow_count=sum(1 for card in projects_sorted if card.health == "yellow"),
                projects=projects_sorted[:12],
            )
        )
    return blocks


def _attention_cards(ctx: AiContext, *, reason: str, limit: int = 12) -> list[WallProjectCard]:
    rows = get_attention_projects(ctx.db, limit=40)
    filtered = [row for row in rows if row.attention_reason == reason][:limit]
    if not filtered:
        return []

    project_ids = [row.project_id for row in filtered]
    projects = {
        project.id: project
        for project in ctx.db.scalars(select(Project).where(Project.id.in_(project_ids))).all()
    }
    team_ids = {project.team_id for project in projects.values() if project.team_id}
    team_names: dict[UUID, str] = {}
    if team_ids:
        team_names = {
            row.id: row.name
            for row in ctx.db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
        }

    cards: list[WallProjectCard] = []
    for row in filtered:
        project = projects.get(row.project_id)
        team_name = None
        if project and project.team_id:
            team_name = team_names.get(project.team_id)
        cards.append(
            WallProjectCard(
                project_id=row.project_id,
                tool_number=row.tool_number,
                customer_name=row.customer_name,
                designer_name=row.designer_name,
                team_name=team_name,
                due_date=row.due_date,
                health=row.health.value if hasattr(row.health, "value") else str(row.health),
                execution_status=(
                    row.execution_status.value
                    if hasattr(row.execution_status, "value")
                    else str(row.execution_status)
                ),
                project_stage=_stage_value(project) if project else None,
                current_milestone=row.current_milestone,
                attention_reason=row.attention_reason,
            )
        )
    return cards


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

        upcoming = _attention_cards(ctx, reason="due_soon", limit=12)
        late = _attention_cards(ctx, reason="overdue", limit=12)
        # Keep legacy current_deliveries for ExecutiveWallPage compatibility.
        deliveries = [
            {
                "tool_number": card.tool_number,
                "customer_name": card.customer_name,
                "due_date": str(card.due_date) if card.due_date else None,
                "reason": card.attention_reason,
                "team_name": card.team_name,
                "designer_name": card.designer_name,
            }
            for card in [*late, *upcoming][:10]
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
            teams_live=_build_teams_live(ctx, active),
            upcoming_deliveries=upcoming,
            late_deliveries=late,
        )
