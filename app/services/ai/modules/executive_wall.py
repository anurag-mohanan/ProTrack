"""Executive KPI wall — full-screen operational display for Program / Eng Managers."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus, ProjectHealth, TeamRelationshipType
from app.models.models import Customer, Project, Team, TeamMember, TimesheetEntry, User
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
    get_attention_projects,
)
from app.services.project_calculation_service import (
    batch_calculate_progress,
    count_projects_by_health,
)


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


def _user_display(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _batch_worker_names(db, projects: list[Project]) -> dict[UUID, tuple[str | None, str | None]]:
    """Designer + surfacer only (not design leader / EM)."""
    user_ids: set[UUID] = set()
    for project in projects:
        for uid in (project.designer_id, project.surfacer_id):
            if uid is not None:
                user_ids.add(uid)
    if not user_ids:
        return {project.id: (None, None) for project in projects}
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    user_map = {user.id: _user_display(user) for user in users}
    return {
        project.id: (
            user_map.get(project.designer_id) if project.designer_id else None,
            user_map.get(project.surfacer_id) if project.surfacer_id else None,
        )
        for project in projects
    }


def _team_leadership(
    db,
    teams: list[Team],
    projects_by_team: dict[UUID | None, list[Project]],
) -> dict[UUID, tuple[str | None, str | None]]:
    """Resolve EM + Design Leader names per team."""
    if not teams:
        return {}

    team_ids = [team.id for team in teams]
    members = db.scalars(select(TeamMember).where(TeamMember.team_id.in_(team_ids))).all()
    member_user_ids = {m.user_id for m in members}
    lead_ids = {team.team_lead_id for team in teams if team.team_lead_id}
    project_dl_ids = {
        project.design_leader_id
        for project_list in projects_by_team.values()
        for project in project_list
        if project.design_leader_id
    }
    user_ids = member_user_ids | lead_ids | project_dl_ids
    users = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )

    em_by_team: dict[UUID, UUID] = {}
    dl_by_team: dict[UUID, UUID] = {}
    for member in members:
        if member.relationship_type == TeamRelationshipType.engineering_manager:
            em_by_team.setdefault(member.team_id, member.user_id)
        elif member.relationship_type == TeamRelationshipType.team_leader:
            dl_by_team.setdefault(member.team_id, member.user_id)

    result: dict[UUID, tuple[str | None, str | None]] = {}
    for team in teams:
        em_id = em_by_team.get(team.id) or team.team_lead_id
        dl_id = dl_by_team.get(team.id)
        if dl_id is None:
            # Fall back to most common project design leader on the team.
            counts: dict[UUID, int] = defaultdict(int)
            for project in projects_by_team.get(team.id, []):
                if project.design_leader_id:
                    counts[project.design_leader_id] += 1
            if counts:
                dl_id = max(counts.items(), key=lambda item: item[1])[0]
        result[team.id] = (
            _user_display(users.get(em_id)) if em_id else None,
            _user_display(users.get(dl_id)) if dl_id else None,
        )
    return result


def _card_from_project(
    project: Project,
    *,
    customer_name: str | None,
    designer_name: str | None,
    surfacer_name: str | None,
    team_name: str | None,
    milestone: str | None = None,
    attention_reason: str | None = None,
    progress_percent: float = 0,
) -> WallProjectCard:
    contributors = [name for name in (designer_name, surfacer_name) if name]
    return WallProjectCard(
        project_id=project.id,
        tool_number=project.tool_number or "—",
        customer_name=customer_name,
        designer_name=designer_name,
        surfacer_name=surfacer_name,
        contributor_names=contributors,
        team_name=team_name,
        due_date=project.due_date,
        health=_health_value(project),
        execution_status=_status_value(project),
        project_stage=_stage_value(project),
        current_milestone=milestone,
        progress_percent=progress_percent,
        attention_reason=attention_reason,
    )


def _build_teams_live(
    ctx: AiContext,
    active: list[Project],
    *,
    team_ids: list[UUID] | None = None,
) -> list[WallTeamLiveBlock]:
    """Build team columns for the wall.

    Always includes selected (or all active) company teams — even when a team has
    zero live projects — so room displays can show placeholders.
    """
    team_query = select(Team).where(Team.is_active.is_(True))
    if team_ids:
        team_query = team_query.where(Team.id.in_(team_ids))
    teams = list(ctx.db.scalars(team_query.order_by(Team.name)).all())
    team_by_id = {team.id: team for team in teams}

    # When a room filter is set, do not invent an "Unassigned" column.
    include_unassigned = not team_ids

    customer_ids = {project.customer_id for project in active if project.customer_id}
    customer_names: dict[UUID, str] = {}
    if customer_ids:
        customer_names = {
            row.id: row.name
            for row in ctx.db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
        }

    projects_by_team: dict[UUID | None, list[Project]] = defaultdict(list)
    for project in active:
        if team_ids and (project.team_id is None or project.team_id not in team_by_id):
            continue
        projects_by_team[project.team_id].append(project)

    leadership = _team_leadership(ctx.db, teams, projects_by_team)
    workers = _batch_worker_names(ctx.db, active) if active else {}
    project_ids = [project.id for project in active]
    milestone_names = _batch_current_milestones(ctx.db, project_ids) if project_ids else {}
    progress_by_project = batch_calculate_progress(ctx.db, project_ids) if project_ids else {}

    def _cards_for(project_list: list[Project], team_name: str) -> list[WallProjectCard]:
        cards: list[WallProjectCard] = []
        for project in project_list:
            progress = progress_by_project.get(project.id)
            percent = float(progress.progress_percent) if progress else 0.0
            designer_name, surfacer_name = workers.get(project.id, (None, None))
            cards.append(
                _card_from_project(
                    project,
                    customer_name=customer_names.get(project.customer_id),
                    designer_name=designer_name,
                    surfacer_name=surfacer_name,
                    team_name=team_name,
                    milestone=milestone_names.get(project.id),
                    progress_percent=percent,
                )
            )
        return sorted(
            cards,
            key=lambda card: (
                0 if card.health == "red" else 1 if card.health == "yellow" else 2,
                card.due_date or ctx.today,
                card.tool_number,
            ),
        )

    blocks: list[WallTeamLiveBlock] = []
    for team in teams:
        projects_sorted = _cards_for(projects_by_team.get(team.id, []), team.name)
        em_name, dl_name = leadership.get(team.id, (None, None))
        blocks.append(
            WallTeamLiveBlock(
                team_id=team.id,
                team_name=team.name,
                engineering_manager_name=em_name,
                design_leader_name=dl_name,
                active_count=len(projects_sorted),
                red_count=sum(1 for card in projects_sorted if card.health == "red"),
                yellow_count=sum(1 for card in projects_sorted if card.health == "yellow"),
                projects=projects_sorted,
            )
        )

    if include_unassigned and projects_by_team.get(None):
        projects_sorted = _cards_for(projects_by_team[None], "Unassigned")
        blocks.append(
            WallTeamLiveBlock(
                team_id=None,
                team_name="Unassigned",
                active_count=len(projects_sorted),
                red_count=sum(1 for card in projects_sorted if card.health == "red"),
                yellow_count=sum(1 for card in projects_sorted if card.health == "yellow"),
                projects=projects_sorted,
            )
        )

    return blocks


def _parse_team_ids(raw: Any) -> list[UUID] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        raw = parts
    if not isinstance(raw, (list, tuple, set)):
        return None
    parsed: list[UUID] = []
    for item in raw:
        try:
            parsed.append(item if isinstance(item, UUID) else UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return parsed or None


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

    workers = _batch_worker_names(ctx.db, list(projects.values()))
    cards: list[WallProjectCard] = []
    for row in filtered:
        project = projects.get(row.project_id)
        team_name = None
        if project and project.team_id:
            team_name = team_names.get(project.team_id)
        designer_name, surfacer_name = (None, None)
        if project is not None:
            designer_name, surfacer_name = workers.get(project.id, (None, None))
        cards.append(
            WallProjectCard(
                project_id=row.project_id,
                tool_number=row.tool_number,
                customer_name=row.customer_name,
                designer_name=designer_name or row.designer_name,
                surfacer_name=surfacer_name,
                contributor_names=[
                    name for name in (designer_name or row.designer_name, surfacer_name) if name
                ],
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
        team_ids = _parse_team_ids(kwargs.get("team_ids"))
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
        if team_ids:
            team_id_set = set(team_ids)
            upcoming = _filter_cards_by_team_ids(ctx, upcoming, team_id_set)
            late = _filter_cards_by_team_ids(ctx, late, team_id_set)

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
        scoped_active = (
            [p for p in active if p.team_id in set(team_ids)] if team_ids else active
        )

        return ExecutiveWallData(
            active_projects=len(scoped_active),
            utilization_percent=round(avg_util, 1),
            late_milestones=count_overdue_milestones(ctx),
            current_deliveries=deliveries,
            recent_releases=recent_releases,
            capacity_hours=float(capacity),
            hours_logged_month=round_hours(hours_month),
            customer_distribution=customer_dist[:6],
            health_summary=health,
            teams_live=_build_teams_live(ctx, active, team_ids=team_ids),
            upcoming_deliveries=upcoming,
            late_deliveries=late,
        )


def _filter_cards_by_team_ids(
    ctx: AiContext,
    cards: list[WallProjectCard],
    team_ids: set[UUID],
) -> list[WallProjectCard]:
    if not cards:
        return cards
    project_ids = [card.project_id for card in cards if card.project_id]
    if not project_ids:
        return []
    projects = {
        project.id: project
        for project in ctx.db.scalars(select(Project).where(Project.id.in_(project_ids))).all()
    }
    filtered: list[WallProjectCard] = []
    for card in cards:
        project = projects.get(card.project_id) if card.project_id else None
        if project is not None and project.team_id in team_ids:
            filtered.append(card)
    return filtered
