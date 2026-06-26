from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select

from app.crud.base import Session
from app.crud.project_metrics import build_project_read
from app.core.permissions import (
    FULL_ACCESS_ROLES,
    READ_ALL_PROJECT_ROLES,
    can_approve_timesheet,
    project_assignment_filter,
    get_role_name,
)
from app.models.enums import MilestoneStatus, ProjectStatus, TimesheetStatus
from app.models.models import Activity, Milestone, Project, Role, Timesheet, TimesheetEntry, User
from app.schemas.dashboard import (
    DashboardSummary,
    DesignerWorkload,
    MilestoneSummary,
    MyTaskItem,
    ProjectDashboard,
    ProjectHoursSummary,
    WorkflowDashboard,
)
from app.schemas.timesheet import ActivityRead, TimesheetEntryRead
from app.services.notification_service import count_unread_notifications
from app.services.project_calculation_service import (
    aggregate_portfolio_hours,
    calculate_hours,
    count_projects_by_health,
    get_milestone_summary,
)

WORKLOAD_ROLES = (
    "Design Leader",
    "Senior Designer",
    "Designer",
    "Junior Designer",
    "Surfacer",
)


def _round_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _current_week_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _visible_projects_clause():
    return (Project.is_deleted.is_(False), Project.is_archived.is_(False))


def get_dashboard_summary(db: Session) -> DashboardSummary:
    visible = _visible_projects_clause()
    total_projects = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(*visible)
        )
        or 0
    )
    not_started = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                *visible,
                Project.status == ProjectStatus.not_started,
            )
        )
        or 0
    )
    in_progress = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                *visible,
                Project.status == ProjectStatus.in_progress,
            )
        )
        or 0
    )
    completed = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                *visible,
                Project.status == ProjectStatus.completed,
            )
        )
        or 0
    )
    archived = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(True),
            )
        )
        or 0
    )
    on_hold = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                *visible,
                Project.status == ProjectStatus.waiting_for_customer,
            )
        )
        or 0
    )
    active = not_started + in_progress + on_hold

    portfolio_hours = aggregate_portfolio_hours(db)

    completed_milestones = int(
        db.scalar(
            select(func.count())
            .select_from(Milestone)
            .where(Milestone.status == MilestoneStatus.completed)
        )
        or 0
    )
    total_milestones = int(
        db.scalar(select(func.count()).select_from(Milestone)) or 0
    )

    if total_milestones == 0:
        overall_progress = Decimal("0.00")
    else:
        overall_progress = _round_percent(
            (Decimal(completed_milestones) / Decimal(total_milestones))
            * Decimal("100")
        )

    green_projects, yellow_projects, red_projects = count_projects_by_health(db)

    return DashboardSummary(
        total_projects=total_projects,
        active_projects=active,
        not_started_projects=not_started,
        in_progress_projects=in_progress,
        completed_projects=completed,
        archived_projects=archived,
        on_hold_projects=on_hold,
        total_quoted_hours=portfolio_hours.quoted,
        total_actual_hours=portfolio_hours.actual,
        total_remaining_hours=portfolio_hours.remaining,
        hours_variance=portfolio_hours.variance,
        completed_milestones=completed_milestones,
        total_milestones=total_milestones,
        overall_progress_percent=overall_progress,
        green_projects=green_projects,
        yellow_projects=yellow_projects,
        red_projects=red_projects,
    )


def get_designer_workload(db: Session) -> list[DesignerWorkload]:
    week_start, week_end = _current_week_bounds()
    users = db.scalars(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(
            Role.name.in_(WORKLOAD_ROLES),
            User.is_active.is_(True),
            User.is_archived.is_(False),
            User.is_deleted.is_(False),
        )
        .order_by(User.last_name, User.first_name)
    ).all()

    workload: list[DesignerWorkload] = []
    for user in users:
        role_name = user.role.name
        assignment_filter = project_assignment_filter(user, role_name)
        if assignment_filter is None:
            continue

        assigned_projects = db.scalars(
            select(Project).where(
                assignment_filter,
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
            )
        ).all()
        active_projects = sum(
            1
            for project in assigned_projects
            if project.status
            in (
                ProjectStatus.not_started,
                ProjectStatus.in_progress,
                ProjectStatus.waiting_for_customer,
            )
        )
        quoted_hours_assigned = _round_hours(
            sum((_decimal(p.quoted_hours) for p in assigned_projects), Decimal("0"))
        )
        actual_hours_logged = _round_hours(
            sum((_decimal(p.actual_hours) for p in assigned_projects), Decimal("0"))
        )

        hours_this_week = db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id == user.id,
                TimesheetEntry.entry_date >= week_start,
                TimesheetEntry.entry_date <= week_end,
            )
        )

        workload.append(
            DesignerWorkload(
                user_id=user.id,
                designer_name=f"{user.first_name} {user.last_name}",
                role=role_name,
                active_projects=active_projects,
                hours_this_week=_round_hours(_decimal(hours_this_week)),
                quoted_hours_assigned=quoted_hours_assigned,
                actual_hours_logged=actual_hours_logged,
            )
        )

    return workload


def get_project_dashboard(db: Session, project_id: UUID) -> ProjectDashboard | None:
    project = db.get(Project, project_id)
    if project is None:
        return None

    completed, remaining, progress_percent = get_milestone_summary(db, project_id)

    hours = calculate_hours(db, project)

    recent_entries = db.scalars(
        select(TimesheetEntry)
        .where(TimesheetEntry.project_id == project_id)
        .order_by(TimesheetEntry.entry_date.desc(), TimesheetEntry.created_at.desc())
        .limit(10)
    ).all()

    return ProjectDashboard(
        project=build_project_read(db, project),
        milestone_summary=MilestoneSummary(
            completed=completed,
            remaining=remaining,
            progress_percent=progress_percent,
        ),
        hours=ProjectHoursSummary(
            quoted=hours.quoted,
            actual=hours.actual,
            remaining=hours.remaining,
            variance=hours.variance,
        ),
        health=project.health,
        recent_timesheet_entries=[
            TimesheetEntryRead.model_validate(entry, from_attributes=True)
            for entry in recent_entries
        ],
    )


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


def get_workflow_dashboard(db: Session, user: User) -> WorkflowDashboard:
    today = date.today()
    week_end = today + timedelta(days=7)
    role_name = get_role_name(db, user)

    assignment_filter = project_assignment_filter(user, role_name)
    visibility = _visible_projects_clause()
    if role_name in READ_ALL_PROJECT_ROLES:
        visible_projects = db.scalars(select(Project).where(*visibility)).all()
    elif assignment_filter is not None:
        visible_projects = db.scalars(
            select(Project).where(assignment_filter, *visibility)
        ).all()
    else:
        visible_projects = []

    project_ids = {project.id for project in visible_projects}
    projects_due_this_week = sum(
        1
        for project in visible_projects
        if project.status != ProjectStatus.completed
        and today <= project.due_date <= week_end
    )

    overdue_milestones = 0
    my_tasks: list[MyTaskItem] = []
    if project_ids:
        milestones = db.scalars(
            select(Milestone)
            .where(
                Milestone.project_id.in_(project_ids),
                Milestone.status != MilestoneStatus.completed,
            )
            .order_by(Milestone.due_date.asc())
        ).all()
        project_map = {project.id: project for project in visible_projects}
        for row in milestones:
            if row.due_date is not None and row.due_date < today:
                overdue_milestones += 1
            my_tasks.append(
                MyTaskItem(
                    id=row.id,
                    title=row.name,
                    task_type="milestone",
                    due_date=row.due_date,
                    project_code=project_map.get(row.project_id).code
                    if project_map.get(row.project_id)
                    else None,
                )
            )

    submitted_timesheets = db.scalars(
        select(Timesheet).where(Timesheet.status == TimesheetStatus.submitted)
    ).all()
    pending_approvals = sum(
        1 for ts in submitted_timesheets if can_approve_timesheet(db, user, ts)
    )

    recent_activity_rows = db.scalars(
        select(Activity).order_by(Activity.created_at.desc()).limit(10)
    ).all()

    return WorkflowDashboard(
        my_tasks=my_tasks[:10],
        projects_due_this_week=projects_due_this_week,
        overdue_milestones=overdue_milestones,
        pending_timesheet_approvals=pending_approvals,
        unread_notifications=count_unread_notifications(db, user.id),
        recent_activity=[_activity_to_read(db, row) for row in recent_activity_rows],
    )
