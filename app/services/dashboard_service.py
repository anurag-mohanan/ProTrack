"""Optimized, fault-tolerant dashboard data assembly."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.non_productive_categories import (
    leave_entry_clause,
    standard_np_code_clause,
    standard_np_hours_clause,
)
from app.core.permissions import (
    READ_ALL_PROJECT_ROLES,
    can_approve_timesheet,
    get_role_name,
    project_assignment_filter,
)
from app.models.enums import (
    ActivityAction,
    DashboardActivityCategory,
    DesignerAvailabilityStatus,
    EntityType,
    ExecutionStatus,
    MilestoneStatus,
    ProjectHealth,
    ProjectStage,
    TimesheetStatus,
    UserAvailabilityStatus,
    WorkCategory,
)
from app.models.models import (
    Activity,
    Customer,
    Milestone,
    NonProductiveCode,
    Project,
    Role,
    Team,
    TeamMember,
    Timesheet,
    TimesheetEntry,
    TimesheetImportHistory,
    User,
)
from app.schemas.dashboard import (
    DashboardActivityItem,
    DashboardCustomerWorkloadRow,
    DashboardDesignerAvailabilityRow,
    DashboardDesignerAvailabilitySummary,
    DashboardKpis,
    DashboardMyTasks,
    DashboardNpCodeRow,
    DashboardNpPanel,
    DashboardTaskItem,
    DashboardTeamSummaryRow,
    ProjectAttentionRow,
)
from app.schemas.timesheet import ActivityRead
from app.services.holiday_service import is_holiday

logger = logging.getLogger(__name__)

_ATTENTION_PRIORITY = {"overdue": 0, "blocked": 1, "due_soon": 2, "on_hold": 3}

WORKLOAD_ROLES = (
    "Design Leader",
    "Senior Designer",
    "Designer",
    "Junior Designer",
    "Surfacer",
)

_WEEKLY_CAPACITY_HOURS = Decimal("40")

_DASHBOARD_ACTIVITY_ACTIONS = (
    ActivityAction.project_created,
    ActivityAction.project_updated,
    ActivityAction.milestone_completed,
    ActivityAction.timesheet_submitted,
    ActivityAction.project_archived,
    ActivityAction.project_restored,
    ActivityAction.project_restored_from_deleted,
)


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _visible_projects_clause():
    return (Project.is_deleted.is_(False), Project.is_archived.is_(False))


def _stage_clause(project_stage: ProjectStage | None):
    if project_stage is None:
        return ()
    return (Project.project_stage == project_stage,)


def _team_clause(team_id: UUID | None):
    if team_id is None:
        return ()
    return (Project.team_id == team_id,)


def _task_priority(due_date: date | None, today: date) -> str:
    if due_date is None:
        return "low"
    if due_date < today:
        return "high"
    if due_date <= today + timedelta(days=3):
        return "high"
    if due_date <= today + timedelta(days=7):
        return "medium"
    return "low"


def _active_project_clause(project_stage: ProjectStage | None = None):
    return (
        *_visible_projects_clause(),
        *_stage_clause(project_stage),
        Project.execution_status != ExecutionStatus.completed,
    )


def _current_week_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    return week_start, week_start + timedelta(days=6)


def _attention_reason(project: Project, today: date) -> str | None:
    if project.execution_status == ExecutionStatus.completed:
        return None
    if project.due_date is not None and project.due_date < today:
        return "overdue"
    if project.health == ProjectHealth.red:
        return "blocked"
    if project.due_date is not None and project.due_date <= today + timedelta(days=7):
        return "due_soon"
    if project.execution_status == ExecutionStatus.on_hold:
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


def get_dashboard_kpis(
    db: Session,
    *,
    project_stage: ProjectStage | None = None,
    team_id: UUID | None = None,
) -> DashboardKpis:
    """Reliable engineering KPIs from aggregate SQL — no user-specific estimates."""
    today = date.today()
    month_start = today.replace(day=1)
    due_cutoff = today + timedelta(days=7)
    visible = _visible_projects_clause()
    stage = _stage_clause(project_stage)
    team = _team_clause(team_id)
    active = _active_project_clause(project_stage) + team
    not_completed = Project.execution_status != ExecutionStatus.completed
    being_worked_on = and_(
        Project.execution_status == ExecutionStatus.currently_being_worked_on,
        *visible,
        *stage,
        *team,
    )
    on_hold = and_(
        Project.execution_status == ExecutionStatus.on_hold,
        *visible,
        *stage,
        *team,
    )
    cancelled = and_(
        Project.execution_status == ExecutionStatus.cancelled,
        *visible,
        *stage,
        *team,
    )
    completed_month = and_(
        Project.execution_status == ExecutionStatus.completed,
        *visible,
        *stage,
        *team,
        Project.completed_at.is_not(None),
        func.date(Project.completed_at) >= month_start,
        func.date(Project.completed_at) <= today,
    )
    due_next_7_days = and_(
        *visible,
        *stage,
        *team,
        not_completed,
        Project.due_date >= today,
        Project.due_date <= due_cutoff,
    )
    overdue = and_(*visible, *stage, *team, not_completed, Project.due_date < today)
    archived = and_(Project.is_deleted.is_(False), Project.is_archived.is_(True))
    if team_id is not None:
        archived = and_(archived, Project.team_id == team_id)

    project_row = db.execute(
        select(
            func.count().filter(being_worked_on),
            func.count().filter(on_hold),
            func.count().filter(cancelled),
            func.count().filter(completed_month),
            func.count().filter(due_next_7_days),
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

    np_hours_this_month = _round_hours(
        _decimal(
            db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    Timesheet.status == TimesheetStatus.approved,
                    TimesheetEntry.entry_date >= month_start,
                    TimesheetEntry.entry_date <= today,
                    standard_np_hours_clause(),
                )
            )
        )
    )

    being_worked_on_count = int(project_row[0] or 0)
    return DashboardKpis(
        being_worked_on_projects=being_worked_on_count,
        on_hold_projects=int(project_row[1] or 0),
        cancelled_projects=int(project_row[2] or 0),
        completed_this_month=int(project_row[3] or 0),
        projects_due_this_week=int(project_row[4] or 0),
        overdue_projects=int(project_row[5] or 0),
        archived_projects=int(project_row[6] or 0),
        total_quoted_hours_active=_round_hours(_decimal(project_row[7])),
        total_actual_hours_productive=total_actual_hours,
        np_hours_this_month=np_hours_this_month,
        in_progress_projects=being_worked_on_count,
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


def get_leave_days_this_month(db: Session) -> int:
    today = date.today()
    month_start = today.replace(day=1)
    total = db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.leave_count), 0))
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.status == TimesheetStatus.approved,
            TimesheetEntry.entry_date >= month_start,
            TimesheetEntry.entry_date <= today,
            leave_entry_clause(),
        )
    )
    return int(total or 0)


def get_np_hours_panel(db: Session) -> DashboardNpPanel:
    today = date.today()
    month_start = today.replace(day=1)

    codes = db.scalars(
        select(NonProductiveCode)
        .where(
            NonProductiveCode.is_archived.is_(False),
            standard_np_code_clause(),
        )
        .order_by(NonProductiveCode.sort_order, NonProductiveCode.code)
    ).all()

    hour_rows = db.execute(
        select(
            NonProductiveCode.code,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(TimesheetEntry, TimesheetEntry.non_productive_code_id == NonProductiveCode.id)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.status == TimesheetStatus.approved,
            TimesheetEntry.entry_date >= month_start,
            TimesheetEntry.entry_date <= today,
            standard_np_hours_clause(),
            standard_np_code_clause(),
        )
        .group_by(NonProductiveCode.code)
    ).all()
    hours_by_code = {row[0]: _decimal(row[1]) for row in hour_rows}

    panel_rows = [
        DashboardNpCodeRow(
            code=code.code,
            description=code.description,
            hours_this_month=_round_hours(hours_by_code.get(code.code, Decimal("0"))),
        )
        for code in codes
    ]
    total = _round_hours(
        sum((row.hours_this_month for row in panel_rows), Decimal("0"))
    )
    return DashboardNpPanel(
        total_np_hours_this_month=total,
        codes=panel_rows,
    )


def get_attention_projects(
    db: Session,
    *,
    limit: int = 10,
    team_id: UUID | None = None,
) -> list[ProjectAttentionRow]:
    today = date.today()
    due_soon_cutoff = today + timedelta(days=7)
    visibility = _visible_projects_clause()
    team = _team_clause(team_id)

    candidates = db.scalars(
        select(Project)
        .where(
            *visibility,
            *team,
            Project.execution_status != ExecutionStatus.completed,
            or_(
                Project.due_date < today,
                Project.health == ProjectHealth.red,
                and_(Project.due_date >= today, Project.due_date <= due_soon_cutoff),
                Project.execution_status == ExecutionStatus.on_hold,
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
            execution_status=project.execution_status,
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
            title="Pending approval",
            task_type="approval",
            subtitle=f"Timesheet week of {ts.week_start.isoformat()}",
            due_date=ts.week_start,
            href="/timesheets",
            priority=_task_priority(ts.week_start, today),
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
                Milestone.due_date <= today + timedelta(days=21),
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
                    priority=_task_priority(row.due_date, today),
                )
            )

    pending_reviews: list[DashboardTaskItem] = []
    for project in user_projects:
        if project.execution_status not in (
            ExecutionStatus.currently_being_worked_on,
            ExecutionStatus.on_hold,
        ):
            continue
        if project.health != ProjectHealth.yellow:
            continue
        pending_reviews.append(
            DashboardTaskItem(
                id=project.id,
                title=project.tool_number or project.code,
                task_type="review",
                subtitle="Pending review",
                due_date=project.due_date,
                project_code=project.code,
                project_id=project.id,
                href=f"/projects/{project.id}",
                priority=_task_priority(project.due_date, today),
            )
        )
    pending_reviews.sort(key=lambda item: item.due_date or today)
    pending_reviews = pending_reviews[:5]

    return DashboardMyTasks(
        pending_approvals=pending_approvals,
        upcoming_milestones=upcoming_milestones,
        pending_reviews=pending_reviews,
    )


def safe_dashboard_call(name: str, fn, default):
    try:
        return fn()
    except Exception:
        logger.exception("Dashboard section failed: %s", name)
        return default


def _activity_category(action: ActivityAction) -> DashboardActivityCategory:
    if action in (
        ActivityAction.project_created,
        ActivityAction.project_updated,
        ActivityAction.project_archived,
        ActivityAction.project_restored,
        ActivityAction.project_deleted,
        ActivityAction.project_restored_from_deleted,
    ):
        return DashboardActivityCategory.project
    if action in (
        ActivityAction.milestone_completed,
        ActivityAction.milestone_reopened,
    ):
        return DashboardActivityCategory.milestone
    if action in (
        ActivityAction.timesheet_submitted,
        ActivityAction.timesheet_approved,
        ActivityAction.timesheet_rejected,
    ):
        return DashboardActivityCategory.timesheet
    return DashboardActivityCategory.user


def _activity_title(action: ActivityAction) -> str:
    labels = {
        ActivityAction.project_created: "Project created",
        ActivityAction.project_updated: "Project updated",
        ActivityAction.milestone_completed: "Milestone completed",
        ActivityAction.timesheet_submitted: "Timesheet submitted",
        ActivityAction.timesheet_approved: "Timesheet approved",
        ActivityAction.timesheet_rejected: "Timesheet rejected",
        ActivityAction.project_archived: "Project archived",
        ActivityAction.project_restored: "Project restored",
        ActivityAction.project_restored_from_deleted: "Project restored",
        ActivityAction.user_logged_in: "User signed in",
        ActivityAction.user_logged_out: "User signed out",
        ActivityAction.login_failed: "Failed login attempt",
        ActivityAction.password_changed: "Password changed",
        ActivityAction.password_reset: "Password reset",
        ActivityAction.admin_impersonation_started: "Administrator impersonation started",
        ActivityAction.admin_impersonation_stopped: "Administrator impersonation ended",
        ActivityAction.user_archived: "User archived",
        ActivityAction.user_restored: "User restored",
    }
    return labels.get(action, action.value.replace("_", " ").title())


def get_dashboard_activity_feed(
    db: Session,
    *,
    limit: int = 20,
) -> list[DashboardActivityItem]:
    feed: list[DashboardActivityItem] = []

    activity_rows = db.scalars(
        select(Activity)
        .where(Activity.action.in_(_DASHBOARD_ACTIVITY_ACTIONS))
        .order_by(Activity.created_at.desc())
        .limit(limit)
    ).all()
    for activity in activity_rows:
        read = _activity_to_read(db, activity)
        href = None
        if activity.entity_type == EntityType.project:
            href = f"/projects/{activity.entity_id}"
        elif activity.entity_type == EntityType.timesheet:
            href = "/timesheets"
        feed.append(
            DashboardActivityItem(
                id=str(activity.id),
                category=_activity_category(activity.action),
                title=_activity_title(activity.action),
                detail=read.new_value or read.old_value,
                actor_name=read.user_name,
                occurred_at=activity.created_at,
                href=href,
            )
        )

    import_rows = db.scalars(
        select(TimesheetImportHistory)
        .order_by(TimesheetImportHistory.created_at.desc())
        .limit(max(5, limit // 4))
    ).all()
    for record in import_rows:
        importer = db.get(User, record.imported_by_id)
        importer_name = (
            f"{importer.first_name} {importer.last_name}" if importer else None
        )
        feed.append(
            DashboardActivityItem(
                id=f"import-{record.id}",
                category=DashboardActivityCategory.import_event,
                title="Timesheet import",
                detail=f"{record.filename} · {record.rows_imported} rows · {record.designer_name}",
                actor_name=importer_name,
                occurred_at=record.created_at,
                href="/admin/imports/historical-timesheets#history",
            )
        )

    feed.sort(key=lambda item: item.occurred_at, reverse=True)
    return feed[:limit]


def get_customer_workload(
    db: Session,
    *,
    team_id: UUID | None = None,
    limit: int = 20,
) -> list[DashboardCustomerWorkloadRow]:
    team = _team_clause(team_id)
    active_statuses = (
        ExecutionStatus.currently_being_worked_on,
        ExecutionStatus.on_hold,
    )
    designer_key = func.coalesce(Project.designer_id, Project.design_leader_id)
    rows = db.execute(
        select(
            Customer.id,
            Customer.name,
            func.count(Project.id),
            func.coalesce(func.sum(Project.quoted_hours), 0),
            func.coalesce(func.sum(Project.actual_hours), 0),
            func.count(func.distinct(designer_key)),
        )
        .join(Customer, Project.customer_id == Customer.id)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(active_statuses),
            *team,
        )
        .group_by(Customer.id, Customer.name)
        .order_by(func.count(Project.id).desc(), Customer.name)
        .limit(limit)
    ).all()

    return [
        DashboardCustomerWorkloadRow(
            customer_id=row[0],
            customer_name=row[1],
            active_tools=int(row[2] or 0),
            quoted_hours=_round_hours(_decimal(row[3])),
            actual_hours=_round_hours(_decimal(row[4])),
            designers_assigned=int(row[5] or 0),
        )
        for row in rows
    ]


def _designer_user_ids_for_team(db: Session, team_id: UUID | None) -> set[UUID] | None:
    if team_id is None:
        return None
    member_ids = set(
        db.scalars(
            select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        ).all()
    )
    assigned_ids = set(
        db.scalars(
            select(User.id).where(User.team_id == team_id, User.is_deleted.is_(False))
        ).all()
    )
    return member_ids | assigned_ids


def get_designer_availability(
    db: Session,
    *,
    team_id: UUID | None = None,
) -> tuple[DashboardDesignerAvailabilitySummary, list[DashboardDesignerAvailabilityRow]]:
    today = date.today()
    team_user_ids = _designer_user_ids_for_team(db, team_id)

    designers = db.scalars(
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
    if team_user_ids is not None:
        designers = [designer for designer in designers if designer.id in team_user_ids]

    if not designers:
        return DashboardDesignerAvailabilitySummary(), []

    designer_ids = [designer.id for designer in designers]

    leave_ids = set(
        db.scalars(
            select(Timesheet.user_id)
            .join(TimesheetEntry, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id.in_(designer_ids),
                Timesheet.status == TimesheetStatus.approved,
                TimesheetEntry.entry_date == today,
                leave_entry_clause(),
                TimesheetEntry.hours > 0,
            )
            .distinct()
        ).all()
    )

    active_projects = db.scalars(
        select(Project).where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(
                (
                    ExecutionStatus.currently_being_worked_on,
                    ExecutionStatus.on_hold,
                )
            ),
            or_(
                Project.designer_id.in_(designer_ids),
                Project.design_leader_id.in_(designer_ids),
            ),
            *_team_clause(team_id),
        )
    ).all()

    projects_by_designer: dict[UUID, list[Project]] = {designer_id: [] for designer_id in designer_ids}
    for project in active_projects:
        for designer_id in (project.designer_id, project.design_leader_id):
            if designer_id in projects_by_designer:
                projects_by_designer[designer_id].append(project)

    all_project_ids = [project.id for project in active_projects]
    milestone_names = _batch_current_milestones(db, all_project_ids)
    customer_ids = {project.customer_id for project in active_projects}
    customer_names = {
        row.id: row.name
        for row in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
    } if customer_ids else {}

    rows: list[DashboardDesignerAvailabilityRow] = []
    allocated = 0
    available_count = 0
    on_leave_count = 0

    for designer in designers:
        assigned = projects_by_designer.get(designer.id, [])
        current_tool_number = None
        current_customer_name = None
        current_stage = None
        current_milestone = None

        if designer.id in leave_ids or is_holiday(db, today):
            status = DesignerAvailabilityStatus.leave
            on_leave_count += 1
        elif designer.availability_status in (
            UserAvailabilityStatus.on_leave,
            UserAvailabilityStatus.unavailable,
        ):
            status = DesignerAvailabilityStatus.leave
            on_leave_count += 1
        else:
            working = [
                project
                for project in assigned
                if project.execution_status == ExecutionStatus.currently_being_worked_on
            ]
            on_hold_projects = [
                project
                for project in assigned
                if project.execution_status == ExecutionStatus.on_hold
            ]
            if working:
                status = DesignerAvailabilityStatus.working
                allocated += 1
            elif on_hold_projects:
                status = DesignerAvailabilityStatus.on_hold
                allocated += 1
            else:
                status = DesignerAvailabilityStatus.available
                available_count += 1

            if assigned:
                primary = sorted(
                    assigned,
                    key=lambda project: (
                        0
                        if project.execution_status
                        == ExecutionStatus.currently_being_worked_on
                        else 1,
                        project.due_date or today,
                    ),
                )[0]
                current_tool_number = primary.tool_number or primary.code
                current_customer_name = customer_names.get(primary.customer_id)
                current_stage = primary.project_stage
                current_milestone = milestone_names.get(primary.id)

        rows.append(
            DashboardDesignerAvailabilityRow(
                user_id=designer.id,
                designer_name=f"{designer.first_name} {designer.last_name}",
                status=status,
                current_tool_number=current_tool_number,
                current_customer_name=current_customer_name,
                current_stage=current_stage,
                current_milestone=current_milestone,
            )
        )

    summary = DashboardDesignerAvailabilitySummary(
        total_designers=len(designers),
        allocated=allocated,
        available=available_count,
        on_leave=on_leave_count,
    )
    return summary, rows


def get_team_summary(
    db: Session,
    *,
    team_id: UUID | None = None,
) -> list[DashboardTeamSummaryRow]:
    teams = db.scalars(
        select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    ).all()
    if team_id is not None:
        teams = [team for team in teams if team.id == team_id]

    active_statuses = (
        ExecutionStatus.currently_being_worked_on,
        ExecutionStatus.on_hold,
    )
    rows: list[DashboardTeamSummaryRow] = []

    for team in teams:
        member_count = int(
            db.scalar(
                select(func.count())
                .select_from(TeamMember)
                .where(TeamMember.team_id == team.id)
            )
            or 0
        )
        project_row = db.execute(
            select(
                func.count(Project.id),
                func.coalesce(func.sum(Project.quoted_hours), 0),
                func.coalesce(func.sum(Project.actual_hours), 0),
            )
            .select_from(Project)
            .where(
                Project.team_id == team.id,
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(active_statuses),
            )
        ).one()
        quoted = _round_hours(_decimal(project_row[1]))
        capacity = _round_hours(_WEEKLY_CAPACITY_HOURS * Decimal(member_count))
        available = _round_hours(max(capacity - quoted, Decimal("0")))

        rows.append(
            DashboardTeamSummaryRow(
                team_id=team.id,
                team_name=team.name,
                team_colour=team.colour,
                project_count=int(project_row[0] or 0),
                designer_count=member_count,
                quoted_hours=quoted,
                actual_hours=_round_hours(_decimal(project_row[2])),
                available_capacity_hours=available,
            )
        )

    return rows
