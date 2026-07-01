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
from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth, ProjectStage, TimesheetStatus, WorkCategory
from app.models.models import Activity, Customer, Milestone, Project, Role, Timesheet, TimesheetEntry, User
from app.schemas.dashboard import (
    DashboardFuturePlaceholders,
    DashboardKpis,
    DashboardMyTasks,
    DashboardNpPanel,
    DashboardOverview,
    DashboardSummary,
    DashboardTaskItem,
    DesignerWorkload,
    MilestoneSummary,
    MyTaskItem,
    ProjectAttentionRow,
    ProjectDashboard,
    ProjectHoursSummary,
    WorkflowDashboard,
)
from app.schemas.timesheet import ActivityRead, TimesheetEntryRead
from app.services.dashboard_service import (
    get_attention_projects,
    get_dashboard_kpis,
    get_dashboard_my_tasks,
    get_dashboard_recent_activity,
    get_np_hours_panel,
    safe_dashboard_call,
)
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


def get_dashboard_overview(db: Session, user: User) -> DashboardOverview:
    kpis = safe_dashboard_call(
        "kpis",
        lambda: get_dashboard_kpis(db),
        DashboardKpis(),
    )
    projects_requiring_attention = safe_dashboard_call(
        "attention_projects",
        lambda: get_attention_projects(db, limit=10),
        [],
    )
    my_tasks = safe_dashboard_call(
        "my_tasks",
        lambda: get_dashboard_my_tasks(db, user),
        DashboardMyTasks(),
    )
    recent_activity = safe_dashboard_call(
        "recent_activity",
        lambda: get_dashboard_recent_activity(db, limit=20),
        [],
    )
    return DashboardOverview(
        kpis=kpis,
        projects_requiring_attention=projects_requiring_attention,
        my_tasks=my_tasks,
        recent_activity=recent_activity,
        placeholders=DashboardFuturePlaceholders(),
    )


def get_dashboard_summary(
    db: Session,
    user: User,
    *,
    project_stage: ProjectStage | None = None,
    team_id: UUID | None = None,
) -> DashboardSummary:
    visible = _visible_projects_clause()
    stage = ()
    if project_stage is not None:
        stage = (Project.project_stage == project_stage,)
    team = ()
    if team_id is not None:
        team = (Project.team_id == team_id,)
    total_projects = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(*visible, *stage, *team)
        )
        or 0
    )
    being_worked_on = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                *visible,
                *stage,
                *team,
                Project.execution_status == ExecutionStatus.currently_being_worked_on,
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
                *stage,
                *team,
                Project.execution_status == ExecutionStatus.on_hold,
            )
        )
        or 0
    )
    cancelled = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                *visible,
                *stage,
                *team,
                Project.execution_status == ExecutionStatus.cancelled,
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
                *stage,
                *team,
                Project.execution_status == ExecutionStatus.completed,
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
    active = being_worked_on + on_hold

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

    engineering_kpis = get_dashboard_kpis(db, project_stage=project_stage)

    approved_entries = db.scalars(
        select(TimesheetEntry)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(Timesheet.status == TimesheetStatus.approved)
    ).all()
    billable_hours = _round_hours(
        sum(
            (_decimal(entry.hours) for entry in approved_entries if entry.is_billable and entry.work_category == WorkCategory.productive),
            Decimal("0"),
        )
    )
    np_hours = _round_hours(
        sum(
            (_decimal(entry.hours) for entry in approved_entries if entry.work_category == WorkCategory.non_productive),
            Decimal("0"),
        )
    )
    non_billable_hours = _round_hours(
        sum(
            (
                _decimal(entry.hours)
                for entry in approved_entries
                if entry.work_category == WorkCategory.productive and not entry.is_billable
            ),
            Decimal("0"),
        )
    )
    total_logged = billable_hours + non_billable_hours + np_hours
    productive_percent = (
        _round_percent((billable_hours / total_logged) * Decimal("100"))
        if total_logged > 0
        else Decimal("0.00")
    )

    attention_projects = safe_dashboard_call(
        "attention_projects",
        lambda: get_attention_projects(db, limit=10),
        [],
    )
    my_tasks = safe_dashboard_call(
        "my_tasks",
        lambda: get_dashboard_my_tasks(db, user),
        DashboardMyTasks(),
    )
    recent_activity = safe_dashboard_call(
        "recent_activity",
        lambda: get_dashboard_recent_activity(db, limit=20),
        [],
    )
    np_hours_panel = safe_dashboard_call(
        "np_hours_panel",
        lambda: get_np_hours_panel(db),
        None,
    )
    if np_hours_panel is None:
        np_hours_panel = DashboardNpPanel()

    return DashboardSummary(
        total_projects=total_projects,
        active_projects=active,
        being_worked_on_projects=being_worked_on,
        on_hold_projects=on_hold,
        cancelled_projects=cancelled,
        completed_projects=completed,
        archived_projects=archived,
        not_started_projects=0,
        in_progress_projects=being_worked_on,
        projects_due_this_week=engineering_kpis.projects_due_this_week,
        overdue_projects=engineering_kpis.overdue_projects,
        completed_this_month=engineering_kpis.completed_this_month,
        billable_hours=billable_hours,
        non_billable_hours=non_billable_hours,
        np_hours=np_hours,
        productive_percent=productive_percent,
        total_quoted_hours=portfolio_hours.quoted,
        total_actual_hours=portfolio_hours.actual,
        total_quoted_hours_active=engineering_kpis.total_quoted_hours_active,
        total_actual_hours_productive=engineering_kpis.total_actual_hours_productive,
        total_remaining_hours=portfolio_hours.remaining,
        hours_variance=portfolio_hours.variance,
        completed_milestones=completed_milestones,
        total_milestones=total_milestones,
        overall_progress_percent=overall_progress,
        green_projects=green_projects,
        yellow_projects=yellow_projects,
        red_projects=red_projects,
        attention_projects=attention_projects,
        my_tasks=my_tasks,
        recent_activity=recent_activity,
        np_hours_this_month=engineering_kpis.np_hours_this_month,
        np_hours_panel=np_hours_panel,
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
            if project.execution_status
            in (
                ExecutionStatus.currently_being_worked_on,
                ExecutionStatus.on_hold,
            )
        )
        active_assigned = [
            p
            for p in assigned_projects
            if p.execution_status
            in (
                ExecutionStatus.currently_being_worked_on,
                ExecutionStatus.on_hold,
            )
        ]
        quoted_hours_assigned = _round_hours(
            sum((_decimal(p.quoted_hours) for p in active_assigned), Decimal("0"))
        )
        actual_hours_logged = _round_hours(
            sum((_decimal(p.actual_hours) for p in active_assigned), Decimal("0"))
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
        if project.execution_status != ExecutionStatus.completed
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
