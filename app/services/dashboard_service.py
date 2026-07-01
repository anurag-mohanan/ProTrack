"""Optimized, fault-tolerant dashboard data assembly."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import (
    READ_ALL_PROJECT_ROLES,
    can_approve_timesheet,
    get_role_name,
    project_assignment_filter,
)
from app.models.enums import ActivityAction, MilestoneStatus, ProjectHealth, ProjectStatus, TimesheetStatus, WorkCategory
from app.models.models import Activity, Customer, Milestone, Project, Timesheet, TimesheetEntry, User
from app.schemas.dashboard import (
    DashboardKpis,
    DashboardMyTasks,
    DashboardTaskItem,
    ProjectAttentionRow,
)
from app.schemas.timesheet import ActivityRead

logger = logging.getLogger(__name__)

_ATTENTION_PRIORITY = {"overdue": 0, "blocked": 1, "due_soon": 2, "on_hold": 3}

_DASHBOARD_ACTIVITY_ACTIONS = (
    ActivityAction.project_created,
    ActivityAction.project_updated,
    ActivityAction.milestone_completed,
    ActivityAction.timesheet_submitted,
    ActivityAction.project_archived,
    ActivityAction.project_restored,
    ActivityAction.user_archived,
    ActivityAction.user_restored,
    ActivityAction.user_restored_from_deleted,
    ActivityAction.project_restored_from_deleted,
)


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _visible_projects_clause():
    return (Project.is_deleted.is_(False), Project.is_archived.is_(False))


def _active_project_clause():
    return (
        *_visible_projects_clause(),
        Project.status != ProjectStatus.completed,
    )


def _current_week_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    return week_start, week_start + timedelta(days=6)


def _attention_reason(project: Project, today: date) -> str | None:
    if project.status == ProjectStatus.completed:
        return None
    if project.due_date is not None and project.due_date < today:
        return "overdue"
    if project.health == ProjectHealth.red:
        return "blocked"
    if project.due_date is not None and project.due_date <= today + timedelta(days=5):
        return "due_soon"
    if project.status == ProjectStatus.waiting_for_customer:
        return "on_hold"
    return None


def _activity_to_read(db: Session, activity: Activity) -> ActivityRead:
    user_name = None
    if activity.user_id is not None:
        user = db.get(User, activity.user_id)
        if user is not None:
            user_name = f"{user.first_name} {user.last_name}"
    return ActivityRead(
        id=activity.id,
        user_id=activity.user_id,
        user_name=user_name,
        entity_type=activity.entity_type,
        entity_id=activity.entity_id,
        action=activity.action,
        old_value=activity.old_value,
        new_value=activity.new_value,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


def get_dashboard_kpis(db: Session) -> DashboardKpis:
    """Reliable engineering KPIs from aggregate SQL — no user-specific estimates."""
    today = date.today()
    week_start, week_end = _current_week_bounds(today)
    month_start = today.replace(day=1)
    visible = _visible_projects_clause()
    active = _active_project_clause()
    not_completed = Project.status != ProjectStatus.completed
    in_progress = and_(Project.status == ProjectStatus.in_progress, *visible)
    on_hold = and_(Project.status == ProjectStatus.waiting_for_customer, *visible)
    completed_month = and_(
        Project.status == ProjectStatus.completed,
        *visible,
        Project.completed_at.is_not(None),
        func.date(Project.completed_at) >= month_start,
        func.date(Project.completed_at) <= today,
    )
    due_this_week = and_(
        *visible,
        not_completed,
        Project.due_date >= week_start,
        Project.due_date <= week_end,
    )
    overdue = and_(*visible, not_completed, Project.due_date < today)
    archived = and_(Project.is_deleted.is_(False), Project.is_archived.is_(True))

    project_row = db.execute(
        select(
            func.count().filter(in_progress),
            func.count().filter(on_hold),
            func.count().filter(completed_month),
            func.count().filter(due_this_week),
            func.count().filter(overdue),
            func.count().filter(archived),
            func.coalesce(func.sum(Project.quoted_hours).filter(and_(*active)), 0),
        ).select_from(Project)
    ).one()

    total_actual_hours = _round_hours(
        _decimal(
            db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    Timesheet.status == TimesheetStatus.approved,
                    TimesheetEntry.work_category == WorkCategory.productive,
                )
            )
        )
    )

    return DashboardKpis(
        in_progress_projects=int(project_row[0] or 0),
        on_hold_projects=int(project_row[1] or 0),
        completed_this_month=int(project_row[2] or 0),
        projects_due_this_week=int(project_row[3] or 0),
        overdue_projects=int(project_row[4] or 0),
        archived_projects=int(project_row[5] or 0),
        total_quoted_hours_active=_round_hours(_decimal(project_row[6])),
        total_actual_hours_productive=total_actual_hours,
    )


def _batch_current_milestones(db: Session, project_ids: list[UUID]) -> dict[UUID, str | None]:
    if not project_ids:
        return {}
    milestones = db.scalars(
        select(Milestone)
        .where(
            Milestone.project_id.in_(project_ids),
            Milestone.status != MilestoneStatus.completed,
        )
        .order_by(Milestone.project_id, Milestone.sort_order)
    ).all()
    result: dict[UUID, str | None] = {}
    in_progress: dict[UUID, str] = {}
    first_open: dict[UUID, str] = {}
    for milestone in milestones:
        if milestone.status == MilestoneStatus.in_progress and milestone.project_id not in in_progress:
            in_progress[milestone.project_id] = milestone.name
        if milestone.project_id not in first_open:
            first_open[milestone.project_id] = milestone.name
    for project_id in project_ids:
        result[project_id] = in_progress.get(project_id) or first_open.get(project_id)
    return result


def _batch_designer_names(db: Session, projects: list[Project]) -> dict[UUID, str | None]:
    user_ids = {
        project.designer_id or project.design_leader_id
        for project in projects
        if project.designer_id or project.design_leader_id
    }
    if not user_ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    user_map = {user.id: f"{user.first_name} {user.last_name}" for user in users}
    return {
        project.id: user_map.get(project.designer_id or project.design_leader_id)
        for project in projects
        if project.designer_id or project.design_leader_id
    }


def get_attention_projects(db: Session, *, limit: int = 25) -> list[ProjectAttentionRow]:
    today = date.today()
    due_soon_cutoff = today + timedelta(days=5)
    visibility = _visible_projects_clause()

    candidates = db.scalars(
        select(Project)
        .where(
            *visibility,
            Project.status != ProjectStatus.completed,
            or_(
                Project.due_date < today,
                Project.health == ProjectHealth.red,
                and_(Project.due_date >= today, Project.due_date <= due_soon_cutoff),
                Project.status == ProjectStatus.waiting_for_customer,
            ),
        )
        .limit(max(limit * 5, 50))
    ).all()

    scored: list[tuple[int, date, Project, str]] = []
    for project in candidates:
        reason = _attention_reason(project, today)
        if reason is None:
            continue
        scored.append(
            (
                _ATTENTION_PRIORITY.get(reason, 99),
                project.due_date or today,
                project,
                reason,
            )
        )
    scored.sort(key=lambda item: (item[0], item[1], item[2].tool_number))
    top = scored[:limit]
    if not top:
        return []

    projects = [item[2] for item in top]
    project_ids = [project.id for project in projects]
    customer_ids = {project.customer_id for project in projects}
    customer_names = {
        row.id: row.name
        for row in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
    }
    milestone_names = _batch_current_milestones(db, project_ids)
    designer_names = _batch_designer_names(db, projects)

    return [
        ProjectAttentionRow(
            project_id=project.id,
            tool_number=project.tool_number or "—",
            customer_name=customer_names.get(project.customer_id, "Unknown"),
            current_milestone=milestone_names.get(project.id),
            designer_name=designer_names.get(project.id),
            due_date=project.due_date or today,
            health=project.health or ProjectHealth.green,
            status=project.status,
            attention_reason=reason,
        )
        for _, _, project, reason in top
    ]


def get_dashboard_recent_activity(db: Session, *, limit: int = 20) -> list[ActivityRead]:
    rows = db.scalars(
        select(Activity)
        .where(Activity.action.in_(_DASHBOARD_ACTIVITY_ACTIONS))
        .order_by(Activity.created_at.desc())
        .limit(limit)
    ).all()
    return [_activity_to_read(db, row) for row in rows]


def get_dashboard_my_tasks(db: Session, user: User) -> DashboardMyTasks:
    today = date.today()
    visibility = _visible_projects_clause()
    role_name = get_role_name(db, user)

    assignment_filter = project_assignment_filter(user, role_name)
    if role_name in READ_ALL_PROJECT_ROLES:
        user_projects = db.scalars(select(Project).where(*visibility)).all()
    elif assignment_filter is not None:
        user_projects = db.scalars(
            select(Project).where(assignment_filter, *visibility)
        ).all()
    else:
        user_projects = []

    submitted_timesheets = db.scalars(
        select(Timesheet).where(Timesheet.status == TimesheetStatus.submitted)
    ).all()
    pending_approvals = [
        DashboardTaskItem(
            id=ts.id,
            title="Timesheet approval",
            task_type="approval",
            subtitle=f"Week of {ts.week_start.isoformat()}",
            due_date=ts.week_start,
            href="/timesheets",
        )
        for ts in submitted_timesheets
        if can_approve_timesheet(db, user, ts)
    ][:10]

    user_project_ids = {project.id for project in user_projects}
    upcoming_milestones: list[DashboardTaskItem] = []
    if user_project_ids:
        milestone_rows = db.scalars(
            select(Milestone)
            .where(
                Milestone.project_id.in_(user_project_ids),
                Milestone.status != MilestoneStatus.completed,
                Milestone.due_date.is_not(None),
                Milestone.due_date >= today,
                Milestone.due_date <= today + timedelta(days=14),
            )
            .order_by(Milestone.due_date.asc())
            .limit(10)
        ).all()
        project_map = {project.id: project for project in user_projects}
        for row in milestone_rows:
            project = project_map.get(row.project_id)
            upcoming_milestones.append(
                DashboardTaskItem(
                    id=row.id,
                    title=row.name,
                    task_type="milestone",
                    subtitle=project.tool_number if project else None,
                    due_date=row.due_date,
                    project_code=project.code if project else None,
                    project_id=row.project_id,
                    href=f"/projects/{row.project_id}" if project else None,
                )
            )

    return DashboardMyTasks(
        pending_approvals=pending_approvals,
        upcoming_milestones=upcoming_milestones,
    )


def safe_dashboard_call(name: str, fn, default):
    try:
        return fn()
    except Exception:
        logger.exception("Dashboard section failed: %s", name)
        return default
