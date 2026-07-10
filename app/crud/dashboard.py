from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, or_, select

from app.core.team_access import team_member_user_ids, team_project_clause
from app.crud.base import Session
from app.core.non_productive_categories import leave_entry_clause, standard_np_hours_clause
from app.crud.project_metrics import build_project_read
from app.core.permissions import (
    ASSIGNED_PROJECT_ROLES,
    DESIGN_LEADER,
    FULL_ACCESS_ROLES,
    SURFACER,
    can_approve_timesheet,
    get_role_name,
    normalize_role_name,
    project_assignment_filter,
)
from app.models.enums import (
    EngineeringChangeStatus,
    ExecutionStatus,
    MilestoneStatus,
    ProjectHealth,
    ProjectStage,
    TimesheetStatus,
    WorkCategory,
)
from app.models.intelligence import EngineeringChange
from app.models.models import Activity, Customer, Milestone, Project, Role, Timesheet, TimesheetEntry, TimesheetImportHistory, User
from app.schemas.dashboard import (
    DashboardFuturePlaceholders,
    DashboardDesignerAvailabilitySummary,
    DashboardKpis,
    DashboardLeavePanel,
    DashboardMyTasks,
    DashboardNpPanel,
    DashboardOperationalMetrics,
    DashboardOverview,
    DashboardProjectStageRow,
    DashboardSummary,
    DashboardTaskItem,
    DesignerWorkload,
    EngineeringInsight,
    MilestoneSummary,
    MissingTimesheetRow,
    MyTaskItem,
    ProjectAttentionRow,
    ProjectDashboard,
    ProjectHoursSummary,
    StaffDashboardMetrics,
    StaffProjectRow,
    WorkflowDashboard,
)
from app.schemas.timesheet import ActivityRead, TimesheetEntryRead
from app.services.dashboard_service import (
    get_attention_projects,
    get_customer_workload,
    get_dashboard_activity_feed,
    get_dashboard_kpis,
    get_dashboard_my_tasks,
    get_dashboard_recent_activity,
    get_designer_availability,
    get_leave_days_this_month,
    get_np_hours_panel,
    get_team_summary,
    live_project_where,
    safe_dashboard_call,
)
from app.services.notification_service import count_unread_notifications
from app.services.collaboration_service import get_collaboration_dashboard
from app.services.engineering_insights_service import generate_engineering_insights
from app.services.ai.context import build_ai_context, count_overdue_milestones
from app.services.kpi_participation import kpi_user_ids_subquery, workload_planning_users
from app.services.timesheet_compliance_service import get_missing_timesheet_rows
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

_ACTIVE_EXECUTION_STATUSES = (
    ExecutionStatus.planning,
    ExecutionStatus.currently_being_worked_on,
    ExecutionStatus.on_hold,
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
    team_ids: list[UUID] | None = None,
) -> DashboardSummary:
    widget_errors: dict[str, str] = {}
    visible = _visible_projects_clause()
    stage = ()
    if project_stage is not None:
        stage = (Project.project_stage == project_stage,)
    team = ()
    # None = org-wide; [] = deny-all (empty accessible teams); non-empty = filter.
    if team_ids is not None:
        team = team_project_clause(db, list(team_ids))
    elif team_id is not None:
        team = team_project_clause(db, [team_id])
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
    active = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(*live_project_where(project_stage=project_stage, team_id=team_id, team_ids=team_ids, db=db))
        )
        or 0
    )

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

    engineering_kpis = safe_dashboard_call(
        "engineering_kpis",
        lambda: get_dashboard_kpis(
            db,
            project_stage=project_stage,
            team_id=team_id,
            team_ids=team_ids,
        ),
        DashboardKpis(),
        errors=widget_errors,
    )

    engineering_user_ids = kpi_user_ids_subquery("engineering_productivity")

    billable_hours = _round_hours(
        _decimal(
            db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    Timesheet.status == TimesheetStatus.approved,
                    Timesheet.user_id.in_(engineering_user_ids),
                    TimesheetEntry.work_category == WorkCategory.productive,
                    TimesheetEntry.is_billable.is_(True),
                )
            )
        )
    )
    np_hours = _round_hours(
        _decimal(
            db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    Timesheet.status == TimesheetStatus.approved,
                    Timesheet.user_id.in_(engineering_user_ids),
                    standard_np_hours_clause(),
                )
            )
        )
    )
    leave_days_this_month = safe_dashboard_call(
        "leave_days_this_month",
        lambda: get_leave_days_this_month(db),
        0,
        errors=widget_errors,
    )
    non_billable_hours = _round_hours(
        _decimal(
            db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    Timesheet.status == TimesheetStatus.approved,
                    Timesheet.user_id.in_(engineering_user_ids),
                    TimesheetEntry.work_category == WorkCategory.productive,
                    TimesheetEntry.is_billable.is_(False),
                )
            )
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
        lambda: get_attention_projects(
            db,
            limit=25,
            team_id=team_id,
            team_ids=team_ids,
        ),
        [],
        errors=widget_errors,
    )
    my_tasks = safe_dashboard_call(
        "my_tasks",
        lambda: get_dashboard_my_tasks(db, user),
        DashboardMyTasks(),
        errors=widget_errors,
    )
    recent_activity = safe_dashboard_call(
        "recent_activity",
        lambda: get_dashboard_recent_activity(db, limit=20),
        [],
        errors=widget_errors,
    )
    activity_feed = safe_dashboard_call(
        "activity_feed",
        lambda: get_dashboard_activity_feed(db, limit=20),
        [],
        errors=widget_errors,
    )
    customer_workload = safe_dashboard_call(
        "customer_workload",
        lambda: get_customer_workload(db, team_id=team_id, team_ids=team_ids),
        [],
        errors=widget_errors,
    )
    designer_summary, designer_availability = safe_dashboard_call(
        "designer_availability",
        lambda: get_designer_availability(db, team_id=team_id, team_ids=team_ids),
        (DashboardDesignerAvailabilitySummary(), []),
        errors=widget_errors,
    )
    team_summary = safe_dashboard_call(
        "team_summary",
        lambda: get_team_summary(db, team_id=team_id, team_ids=team_ids),
        [],
        errors=widget_errors,
    )
    np_hours_panel = safe_dashboard_call(
        "np_hours_panel",
        lambda: get_np_hours_panel(db),
        None,
        errors=widget_errors,
    )
    if np_hours_panel is None:
        np_hours_panel = DashboardNpPanel()

    operational_metrics = safe_dashboard_call(
        "operational_metrics",
        lambda: _get_operational_metrics(db, user),
        DashboardOperationalMetrics(),
        errors=widget_errors,
    )
    staff_metrics = safe_dashboard_call(
        "staff_metrics",
        lambda: _get_staff_metrics(db, user),
        None,
        errors=widget_errors,
    )
    engineering_insights = safe_dashboard_call(
        "engineering_insights",
        lambda: generate_engineering_insights(db),
        [],
        errors=widget_errors,
    )
    role_name = normalize_role_name(get_role_name(db, user))
    missing_timesheets: list[MissingTimesheetRow] = []
    if role_name in FULL_ACCESS_ROLES | {DESIGN_LEADER}:
        missing_timesheets = safe_dashboard_call(
            "missing_timesheets",
            lambda: get_missing_timesheet_rows(db),
            [],
            errors=widget_errors,
        )

    today = date.today()
    hours_logged_today = _round_hours(
        _decimal(
            db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                    TimesheetEntry.entry_date == today,
                    TimesheetEntry.is_deleted.is_(False),
                )
            )
        )
    )
    open_engineering_changes = int(
        db.scalar(
            select(func.count())
            .select_from(EngineeringChange)
            .join(Project, EngineeringChange.project_id == Project.id)
            .where(
                EngineeringChange.status == EngineeringChangeStatus.open,
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
            )
        )
        or 0
    )
    stage_rows = db.execute(
        select(Project.project_stage, func.count())
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(_ACTIVE_EXECUTION_STATUSES),
            *stage,
            *team,
        )
        .group_by(Project.project_stage)
        .order_by(Project.project_stage)
    ).all()
    projects_by_stage = [
        DashboardProjectStageRow(
            project_stage=row[0],
            project_count=int(row[1] or 0),
        )
        for row in stage_rows
    ]

    projects_due_today = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(_ACTIVE_EXECUTION_STATUSES),
                Project.due_date == today,
                *stage,
                *team,
            )
        )
        or 0
    )
    late_milestones = safe_dashboard_call(
        "late_milestones",
        lambda: count_overdue_milestones(build_ai_context(db, user=user, today=today)),
        0,
        errors=widget_errors,
    )
    my_project_rows = safe_dashboard_call(
        "my_project_rows",
        lambda: _get_my_project_rows(db, user),
        [],
        errors=widget_errors,
    )
    collaboration_activity = safe_dashboard_call(
        "collaboration_activity",
        lambda: get_collaboration_dashboard(db),
        None,
        errors=widget_errors,
    )

    team_scoped = team_id is not None or team_ids is not None

    return DashboardSummary(
        total_projects=total_projects,
        active_projects=active,
        being_worked_on_projects=being_worked_on,
        on_hold_projects=on_hold,
        cancelled_projects=cancelled,
        completed_projects=completed,
        archived_projects=engineering_kpis.archived_projects if not team_scoped else archived,
        not_started_projects=0,
        in_progress_projects=being_worked_on,
        projects_due_this_week=engineering_kpis.projects_due_this_week,
        projects_due_today=projects_due_today,
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
        activity_feed=activity_feed,
        customer_workload=customer_workload,
        designer_availability_summary=designer_summary,
        designer_availability=designer_availability,
        team_summary=team_summary,
        projects_by_stage=projects_by_stage,
        hours_logged_today=hours_logged_today,
        open_engineering_changes=open_engineering_changes,
        np_hours_this_month=engineering_kpis.np_hours_this_month,
        leave_days_this_month=leave_days_this_month,
        np_hours_panel=np_hours_panel,
        leave_panel=DashboardLeavePanel(leave_days_this_month=leave_days_this_month),
        operational_metrics=operational_metrics,
        staff_metrics=staff_metrics,
        engineering_insights=engineering_insights,
        missing_timesheets=missing_timesheets,
        late_milestones=late_milestones,
        my_project_rows=my_project_rows,
        collaboration_activity=collaboration_activity,
        widget_errors=widget_errors,
    )


def _get_my_project_rows(db: Session, user: User) -> list[StaffProjectRow]:
    projects = db.scalars(
        select(Project)
        .where(
            or_(
                Project.designer_id == user.id,
                Project.surfacer_id == user.id,
                Project.design_leader_id == user.id,
            ),
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status != ExecutionStatus.completed,
        )
        .order_by(Project.due_date.asc().nullslast())
        .limit(12)
    ).all()
    rows: list[StaffProjectRow] = []
    for project in projects:
        project_read = build_project_read(db, project)
        rows.append(
            StaffProjectRow(
                project_id=project.id,
                tool_number=project.tool_number,
                customer_name=project_read.customer_name or "—",
                current_stage=project.project_stage.value if project.project_stage else "—",
                due_date=project.due_date,
                progress_percent=_decimal(project_read.progress_percent),
                hours_logged=_round_hours(_decimal(project.actual_hours)),
                remaining_planned_hours=_round_hours(
                    max(_decimal(0), _decimal(project.quoted_hours) - _decimal(project.actual_hours))
                ),
                health=project.health.value if project.health else None,
            )
        )
    return rows


def _get_operational_metrics(db: Session, user: User) -> DashboardOperationalMetrics:
    role_name = normalize_role_name(get_role_name(db, user))
    if role_name not in FULL_ACCESS_ROLES:
        return DashboardOperationalMetrics()

    submitted = db.scalars(
        select(Timesheet).where(Timesheet.status == TimesheetStatus.submitted)
    ).all()
    pending_timesheets = sum(
        1 for timesheet in submitted if can_approve_timesheet(db, user, timesheet)
    )
    pending_imports = int(
        db.scalar(
            select(func.count())
            .select_from(TimesheetImportHistory)
            .where(TimesheetImportHistory.status != "completed")
        )
        or 0
    )
    pending_projects = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status == ExecutionStatus.on_hold,
            )
        )
        or 0
    )
    return DashboardOperationalMetrics(
        pending_timesheet_approvals=pending_timesheets,
        pending_project_approvals=pending_projects,
        pending_import_jobs=pending_imports,
    )


def _get_staff_metrics(db: Session, user: User) -> StaffDashboardMetrics | None:
    role_name = normalize_role_name(get_role_name(db, user))
    if role_name not in ASSIGNED_PROJECT_ROLES:
        return None

    assignment = project_assignment_filter(user, role_name)
    if assignment is None:
        return None

    week_start, week_end = _current_week_bounds()
    today = date.today()
    projects = db.scalars(
        select(Project)
        .where(
            assignment,
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status != ExecutionStatus.completed,
        )
        .order_by(Project.due_date.asc().nullslast())
    ).all()

    current = next(
        (
            project
            for project in projects
            if project.execution_status == ExecutionStatus.currently_being_worked_on
        ),
        projects[0] if projects else None,
    )

    project_ids = [project.id for project in projects]
    assigned_milestones = 0
    upcoming_due = 0
    if project_ids:
        milestones = db.scalars(
            select(Milestone).where(
                Milestone.project_id.in_(project_ids),
                Milestone.status != MilestoneStatus.completed,
            )
        ).all()
        assigned_milestones = len(milestones)
        upcoming_due = sum(
            1
            for milestone in milestones
            if milestone.due_date is not None
            and today <= milestone.due_date <= today + timedelta(days=7)
        )

    hours_week = db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.user_id == user.id,
            TimesheetEntry.entry_date >= week_start,
            TimesheetEntry.entry_date <= week_end,
        )
    )
    pending_drafts = int(
        db.scalar(
            select(func.count())
            .select_from(Timesheet)
            .where(
                Timesheet.user_id == user.id,
                Timesheet.status == TimesheetStatus.draft,
            )
        )
        or 0
    )

    return StaffDashboardMetrics(
        my_projects=len(projects),
        my_project_rows=[
            (
                lambda project_read: StaffProjectRow(
                    project_id=project.id,
                    tool_number=project.tool_number,
                    customer_name=project_read.customer_name or "—",
                    current_stage=project.project_stage.value if project.project_stage else "—",
                    due_date=project.due_date,
                    progress_percent=_decimal(project_read.progress_percent),
                    hours_logged=_round_hours(_decimal(project.actual_hours)),
                    remaining_planned_hours=_round_hours(
                        max(_decimal(0), _decimal(project.quoted_hours) - _decimal(project.actual_hours))
                    ),
                    health=project.health.value if project.health else None,
                )
            )(build_project_read(db, project))
            for project in projects
        ],
        current_tool_number=current.tool_number if current else None,
        current_part_description=current.part_description if current else None,
        assigned_milestones=assigned_milestones,
        hours_logged_this_week=_round_hours(_decimal(hours_week)),
        pending_timesheet_submissions=pending_drafts,
        upcoming_due_dates=upcoming_due,
        task_label="Surfacing Tasks" if role_name == SURFACER else "Design Tasks",
    )


def get_designer_workload(
    db: Session,
    *,
    team_ids: list[UUID] | None = None,
) -> list[DesignerWorkload]:
    week_start, week_end = _current_week_bounds()
    users = workload_planning_users(db)
    if team_ids is not None:
        allowed_user_ids = team_member_user_ids(db, list(team_ids)) if team_ids else set()
        users = [user for user in users if user.id in allowed_user_ids]

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
            _decimal(
                db.scalar(
                    select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                    .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                    .where(
                        Timesheet.user_id == user.id,
                        TimesheetEntry.is_deleted.is_(False),
                    )
                )
            )
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
    from app.core.team_access import project_visibility_clause

    visibility = _visible_projects_clause()
    scope_clause = project_visibility_clause(db, user)
    if scope_clause is None:
        visible_projects = db.scalars(select(Project).where(*visibility)).all()
    else:
        visible_projects = db.scalars(
            select(Project).where(scope_clause, *visibility)
        ).all()

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
