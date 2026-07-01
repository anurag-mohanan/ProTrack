from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ExecutionStatus, ProjectHealth, ProjectStage
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
    np_hours_this_month: Decimal = Decimal("0")
    np_hours_panel: DashboardNpPanel = Field(default_factory=DashboardNpPanel)


class DashboardFuturePlaceholders(BaseModel):
    notifications_enabled: bool = False
    ai_recommendations_enabled: bool = False
    todays_priorities_enabled: bool = False


class DashboardOverview(BaseModel):
    kpis: DashboardKpis
    projects_requiring_attention: list[ProjectAttentionRow] = Field(default_factory=list)
    my_tasks: DashboardMyTasks
    recent_activity: list[ActivityRead] = Field(default_factory=list)
    placeholders: DashboardFuturePlaceholders = Field(
        default_factory=DashboardFuturePlaceholders
    )
