from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    DashboardActivityCategory,
    DesignerAvailabilityStatus,
    ExecutionStatus,
    ProjectHealth,
    ProjectStage,
)
from app.schemas.project import ProjectRead
from app.schemas.timesheet import ActivityRead, TimesheetEntryRead


class DesignerWorkload(BaseModel):
    user_id: UUID
    designer_name: str
    role: str
    active_projects: int = 0
    hours_this_week: Decimal = Decimal("0")
    quoted_hours_assigned: Decimal = Decimal("0")
    actual_hours_logged: Decimal = Decimal("0")


class MilestoneSummary(BaseModel):
    completed: int = 0
    remaining: int = 0
    progress_percent: Decimal = Decimal("0.00")


class ProjectHoursSummary(BaseModel):
    quoted: Decimal = Decimal("0")
    actual: Decimal = Decimal("0")
    remaining: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")


class ProjectDashboard(BaseModel):
    project: ProjectRead
    milestone_summary: MilestoneSummary
    hours: ProjectHoursSummary
    health: ProjectHealth
    recent_timesheet_entries: list[TimesheetEntryRead] = Field(default_factory=list)


class MyTaskItem(BaseModel):
    id: UUID
    title: str
    task_type: str
    due_date: date | None = None
    project_code: str | None = None


class WorkflowDashboard(BaseModel):
    my_tasks: list[MyTaskItem] = Field(default_factory=list)
    projects_due_this_week: int = 0
    overdue_milestones: int = 0
    pending_timesheet_approvals: int = 0
    unread_notifications: int = 0
    recent_activity: list[ActivityRead] = Field(default_factory=list)


class DashboardKpis(BaseModel):
    being_worked_on_projects: int = 0
    on_hold_projects: int = 0
    cancelled_projects: int = 0
    completed_this_month: int = 0
    projects_due_this_week: int = 0
    overdue_projects: int = 0
    archived_projects: int = 0
    total_quoted_hours_active: Decimal = Decimal("0")
    total_actual_hours_productive: Decimal = Decimal("0")
    np_hours_this_month: Decimal = Decimal("0")
    # Legacy alias for older clients
    in_progress_projects: int = 0


class DashboardNpCodeRow(BaseModel):
    code: str
    description: str
    hours_this_month: Decimal = Decimal("0")


class DashboardNpPanel(BaseModel):
    total_np_hours_this_month: Decimal = Decimal("0")
    codes: list[DashboardNpCodeRow] = Field(default_factory=list)


class DashboardLeavePanel(BaseModel):
    leave_days_this_month: int = 0


class ProjectAttentionRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    current_milestone: str | None = None
    designer_name: str | None = None
    due_date: date
    health: ProjectHealth
    execution_status: ExecutionStatus
    attention_reason: str


class DashboardTaskItem(BaseModel):
    id: UUID
    title: str
    task_type: str
    subtitle: str | None = None
    due_date: date | None = None
    project_code: str | None = None
    project_id: UUID | None = None
    href: str | None = None
    priority: str | None = None


class DashboardCustomerWorkloadRow(BaseModel):
    customer_id: UUID
    customer_name: str
    active_tools: int = 0
    quoted_hours: Decimal = Decimal("0")
    actual_hours: Decimal = Decimal("0")
    designers_assigned: int = 0


class DashboardDesignerAvailabilitySummary(BaseModel):
    total_designers: int = 0
    allocated: int = 0
    available: int = 0
    on_leave: int = 0


class DashboardDesignerAvailabilityRow(BaseModel):
    user_id: UUID
    designer_name: str
    status: DesignerAvailabilityStatus
    current_tool_number: str | None = None
    current_customer_name: str | None = None
    current_stage: ProjectStage | None = None
    current_milestone: str | None = None


class DashboardTeamSummaryRow(BaseModel):
    team_id: UUID
    team_name: str
    team_colour: str | None = None
    project_count: int = 0
    designer_count: int = 0
    quoted_hours: Decimal = Decimal("0")
    actual_hours: Decimal = Decimal("0")
    available_capacity_hours: Decimal = Decimal("0")


class DashboardProjectStageRow(BaseModel):
    project_stage: ProjectStage
    project_count: int = 0


class DashboardActivityItem(BaseModel):
    id: str
    category: DashboardActivityCategory
    title: str
    detail: str | None = None
    actor_name: str | None = None
    occurred_at: datetime
    href: str | None = None


class DashboardOperationalMetrics(BaseModel):
    pending_timesheet_approvals: int = 0
    pending_project_approvals: int = 0
    pending_import_jobs: int = 0


class StaffProjectRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    current_stage: str
    due_date: date | None = None
    progress_percent: Decimal = Decimal("0")
    hours_logged: Decimal = Decimal("0")
    remaining_planned_hours: Decimal = Decimal("0")
    health: str | None = None


class EngineeringInsight(BaseModel):
    category: str
    severity: str = "info"
    title: str
    detail: str | None = None
    href: str | None = None


class MissingTimesheetRow(BaseModel):
    user_id: UUID
    employee_name: str
    last_entry_date: date | None = None
    missing_days: int = 0


class CollaborationProjectRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str | None = None
    contributor_count: int = 0
    support_hours: Decimal = Decimal("0")


class CollaborationDesignerRow(BaseModel):
    user_id: UUID
    user_name: str
    hours_received: Decimal | None = None
    hours_provided: Decimal | None = None
    peer_review_hours: Decimal = Decimal("0")


class CollaborationActivityDashboard(BaseModel):
    most_assisted_projects: list[CollaborationProjectRow] = Field(default_factory=list)
    designers_receiving_support: list[CollaborationDesignerRow] = Field(default_factory=list)
    designers_providing_support: list[CollaborationDesignerRow] = Field(default_factory=list)
    cross_team_collaboration_count: int = 0
    peer_review_hours_this_month: Decimal = Decimal("0")
    multi_contributor_projects: int = 0


class StaffDashboardMetrics(BaseModel):
    my_projects: int = 0
    my_project_rows: list[StaffProjectRow] = Field(default_factory=list)
    current_tool_number: str | None = None
    current_part_description: str | None = None
    assigned_milestones: int = 0
    hours_logged_this_week: Decimal = Decimal("0")
    pending_timesheet_submissions: int = 0
    upcoming_due_dates: int = 0
    task_label: str = "Design Tasks"


class DashboardMyTasks(BaseModel):
    pending_approvals: list[DashboardTaskItem] = Field(default_factory=list)
    upcoming_milestones: list[DashboardTaskItem] = Field(default_factory=list)
    pending_reviews: list[DashboardTaskItem] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    total_projects: int = 0
    active_projects: int = 0
    being_worked_on_projects: int = 0
    on_hold_projects: int = 0
    cancelled_projects: int = 0
    completed_projects: int = 0
    archived_projects: int = 0
    projects_due_this_week: int = 0
    projects_due_today: int = 0
    overdue_projects: int = 0
    completed_this_month: int = 0
    # Legacy fields retained for compatibility
    not_started_projects: int = 0
    in_progress_projects: int = 0
    billable_hours: Decimal = Decimal("0")
    non_billable_hours: Decimal = Decimal("0")
    np_hours: Decimal = Decimal("0")
    productive_percent: Decimal = Decimal("0.00")
    total_quoted_hours: Decimal = Decimal("0")
    total_actual_hours: Decimal = Decimal("0")
    total_quoted_hours_active: Decimal = Decimal("0")
    total_actual_hours_productive: Decimal = Decimal("0")
    total_remaining_hours: Decimal = Decimal("0")
    hours_variance: Decimal = Decimal("0")
    completed_milestones: int = 0
    total_milestones: int = 0
    overall_progress_percent: Decimal = Decimal("0.00")
    green_projects: int = 0
    yellow_projects: int = 0
    red_projects: int = 0
    attention_projects: list[ProjectAttentionRow] = Field(default_factory=list)
    my_tasks: DashboardMyTasks = Field(default_factory=DashboardMyTasks)
    recent_activity: list[ActivityRead] = Field(default_factory=list)
    activity_feed: list[DashboardActivityItem] = Field(default_factory=list)
    customer_workload: list[DashboardCustomerWorkloadRow] = Field(default_factory=list)
    designer_availability_summary: DashboardDesignerAvailabilitySummary = Field(
        default_factory=DashboardDesignerAvailabilitySummary
    )
    designer_availability: list[DashboardDesignerAvailabilityRow] = Field(
        default_factory=list
    )
    team_summary: list[DashboardTeamSummaryRow] = Field(default_factory=list)
    projects_by_stage: list[DashboardProjectStageRow] = Field(default_factory=list)
    hours_logged_today: Decimal = Decimal("0")
    open_engineering_changes: int = 0
    np_hours_this_month: Decimal = Decimal("0")
    leave_days_this_month: int = 0
    np_hours_panel: DashboardNpPanel = Field(default_factory=DashboardNpPanel)
    leave_panel: DashboardLeavePanel = Field(default_factory=DashboardLeavePanel)
    operational_metrics: DashboardOperationalMetrics = Field(
        default_factory=DashboardOperationalMetrics
    )
    staff_metrics: StaffDashboardMetrics | None = None
    engineering_insights: list[EngineeringInsight] = Field(default_factory=list)
    missing_timesheets: list[MissingTimesheetRow] = Field(default_factory=list)
    late_milestones: int = 0
    my_project_rows: list[StaffProjectRow] = Field(default_factory=list)
    collaboration_activity: CollaborationActivityDashboard | None = None
    widget_errors: dict[str, str] = Field(default_factory=dict)


class DashboardFuturePlaceholders(BaseModel):
    notifications_enabled: bool = True
    ai_recommendations_enabled: bool = True
    todays_priorities_enabled: bool = True


class DashboardOverview(BaseModel):
    kpis: DashboardKpis
    projects_requiring_attention: list[ProjectAttentionRow] = Field(default_factory=list)
    my_tasks: DashboardMyTasks
    recent_activity: list[ActivityRead] = Field(default_factory=list)
    placeholders: DashboardFuturePlaceholders = Field(
        default_factory=DashboardFuturePlaceholders
    )
