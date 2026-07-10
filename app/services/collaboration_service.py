"""Collaboration metrics for dashboard and AI insights."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ContributionReason
from app.models.models import Customer, Project, Timesheet, TimesheetEntry, User
from app.schemas.dashboard import (
    CollaborationActivityDashboard,
    CollaborationDesignerRow,
    CollaborationProjectRow,
)
from app.services.project_contributor_service import SUPPORT_REASONS

SUPPORT_REASON_VALUES = {reason.value for reason in SUPPORT_REASONS}


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _month_start(today: date) -> date:
    return today.replace(day=1)


def get_collaboration_dashboard(
    db: Session,
    *,
    month_start: date | None = None,
    limit: int = 5,
) -> CollaborationActivityDashboard:
    today = date.today()
    period_start = month_start or _month_start(today)

    entry_rows = db.execute(
        select(
            TimesheetEntry.project_id,
            Timesheet.user_id,
            TimesheetEntry.contribution_reason,
            TimesheetEntry.hours,
            Project.tool_number,
            Customer.name,
            Project.designer_id,
            Project.surfacer_id,
            Project.team_id,
            User.first_name,
            User.last_name,
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .join(Project, TimesheetEntry.project_id == Project.id)
        .join(Customer, Project.customer_id == Customer.id)
        .where(
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.project_id.is_not(None),
            TimesheetEntry.entry_date >= period_start,
        )
    ).all()

    project_contributors: dict[UUID, set[UUID]] = defaultdict(set)
    project_support_hours: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    project_meta: dict[UUID, tuple[str, str | None]] = {}
    support_received: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    support_provided: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    peer_review_by_user: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    user_names: dict[UUID, str] = {}
    cross_team_pairs: set[tuple[UUID, UUID]] = set()
    peer_review_total = Decimal("0")

    for (
        project_id,
        user_id,
        reason,
        hours,
        tool_number,
        customer_name,
        designer_id,
        surfacer_id,
        team_id,
        first_name,
        last_name,
    ) in entry_rows:
        if project_id is None or user_id is None:
            continue
        hour_value = _decimal(hours)
        if hour_value <= 0:
            continue

        project_contributors[project_id].add(user_id)
        project_meta[project_id] = (tool_number, customer_name)
        user_names[user_id] = f"{first_name} {last_name}".strip()

        owner_ids = {uid for uid in (designer_id, surfacer_id) if uid is not None}
        is_owner = user_id in owner_ids
        reason_value = reason.value if reason is not None else None

        if reason == ContributionReason.peer_review:
            peer_review_by_user[user_id] += hour_value
            peer_review_total += hour_value

        if reason_value in SUPPORT_REASON_VALUES and not is_owner:
            project_support_hours[project_id] += hour_value
            support_provided[user_id] += hour_value
            for owner_id in owner_ids:
                support_received[owner_id] += hour_value

        if not is_owner and team_id is not None:
            owner_team_ids = {
                db.scalar(select(User.team_id).where(User.id == owner_id))
                for owner_id in owner_ids
            }
            contributor_team = db.scalar(select(User.team_id).where(User.id == user_id))
            for owner_team in owner_team_ids:
                if owner_team and contributor_team and owner_team != contributor_team:
                    cross_team_pairs.add((project_id, user_id))

    multi_contributor_projects = sum(
        1 for contributors in project_contributors.values() if len(contributors) > 1
    )

    most_assisted = sorted(
        (
            CollaborationProjectRow(
                project_id=project_id,
                tool_number=project_meta[project_id][0],
                customer_name=project_meta[project_id][1],
                contributor_count=len(project_contributors[project_id]),
                support_hours=_decimal(project_support_hours[project_id]),
            )
            for project_id in project_support_hours
            if project_support_hours[project_id] > 0
        ),
        key=lambda row: row.support_hours,
        reverse=True,
    )[:limit]

    designers_receiving = sorted(
        (
            CollaborationDesignerRow(
                user_id=user_id,
                user_name=user_names.get(user_id, "Unknown"),
                hours_received=_decimal(support_received[user_id]),
            )
            for user_id in support_received
            if support_received[user_id] > 0
        ),
        key=lambda row: row.hours_received or Decimal("0"),
        reverse=True,
    )[:limit]

    designers_providing = sorted(
        (
            CollaborationDesignerRow(
                user_id=user_id,
                user_name=user_names.get(user_id, "Unknown"),
                hours_provided=_decimal(support_provided[user_id]),
                peer_review_hours=_decimal(peer_review_by_user.get(user_id, 0)),
            )
            for user_id in support_provided
            if support_provided[user_id] > 0
        ),
        key=lambda row: row.hours_provided or Decimal("0"),
        reverse=True,
    )[:limit]

    return CollaborationActivityDashboard(
        most_assisted_projects=most_assisted,
        designers_receiving_support=designers_receiving,
        designers_providing_support=designers_providing,
        cross_team_collaboration_count=len(cross_team_pairs),
        peer_review_hours_this_month=_decimal(peer_review_total),
        multi_contributor_projects=multi_contributor_projects,
    )


def build_collaboration_ai_insights(ctx) -> list:
    """Contributor-pattern insights for the AI assistant."""
    from app.schemas.ai import AiInsight
    from app.services.project_contributor_service import get_project_contributors

    insights: list[AiInsight] = []
    dashboard = get_collaboration_dashboard(ctx.db)

    if dashboard.multi_contributor_projects:
        insights.append(
            AiInsight(
                id="multi-contributor-projects",
                module="dashboard_insights",
                category="collaboration",
                severity="info",
                title=(
                    f"{dashboard.multi_contributor_projects} active project"
                    f"{'s' if dashboard.multi_contributor_projects != 1 else ''} "
                    "have multiple contributors"
                ),
                detail="Review quoted hours on tools receiving cross-team support.",
                href="/reports",
                confidence=88,
            )
        )

    if dashboard.peer_review_hours_this_month > 0:
        insights.append(
            AiInsight(
                id="peer-review-hours",
                module="dashboard_insights",
                category="collaboration",
                severity="info",
                title=f"{dashboard.peer_review_hours_this_month} peer review hours logged this month",
                detail="Peer review time is tracked separately from primary design work.",
                href="/timesheets",
                confidence=92,
            )
        )

    if dashboard.designers_providing_support:
        top = dashboard.designers_providing_support[0]
        insights.append(
            AiInsight(
                id=f"top-supporter-{top.user_id}",
                module="dashboard_insights",
                category="collaboration",
                severity="info",
                title=f"{top.user_name} provided the most support hours this month",
                detail=f"Logged {top.hours_provided} hours assisting on other projects.",
                href="/dashboard",
                confidence=85,
            )
        )

    if dashboard.designers_receiving_support:
        recipient = dashboard.designers_receiving_support[0]
        insights.append(
            AiInsight(
                id=f"top-support-recipient-{recipient.user_id}",
                module="dashboard_insights",
                category="collaboration",
                severity="info",
                title=f"{recipient.user_name} received {recipient.hours_received} support hours this month",
                detail="Assistance from contributors is reflected in project actual hours.",
                href="/dashboard",
                confidence=85,
            )
        )

    if dashboard.most_assisted_projects:
        assisted = dashboard.most_assisted_projects[0]
        contributors = get_project_contributors(ctx.db, assisted.project_id)
        if len(contributors) >= 2:
            insights.append(
                AiInsight(
                    id=f"assisted-project-{assisted.project_id}",
                    module="dashboard_insights",
                    category="collaboration",
                    severity="warning",
                    title=(
                        f"Tool {assisted.tool_number} required assistance from "
                        f"{len(contributors)} engineers"
                    ),
                    detail=f"{assisted.support_hours} support hours logged across contributors.",
                    href=f"/projects/{assisted.project_id}",
                    confidence=90,
                    entity_type="project",
                    entity_id=assisted.project_id,
                )
            )

    return insights
