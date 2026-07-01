from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectHealth, ProjectStage, TimesheetStatus, WorkCategory
from app.schemas.dashboard import DesignerWorkload


class ProjectHoursReportRow(BaseModel):
    project_id: UUID
    tool_number: str
    part_description: str
    customer_name: str
    quoted_hours: Decimal
    actual_hours: Decimal
    hours_variance: Decimal
    execution_status: ExecutionStatus
    project_stage: ProjectStage


class CustomerSummaryReportRow(BaseModel):
    customer_id: UUID
    customer_name: str
    project_count: int
    total_quoted_hours: Decimal
    total_actual_hours: Decimal
    hours_variance: Decimal


class ReportsBundle(BaseModel):
    project_hours: list[ProjectHoursReportRow]
    designer_utilization: list[DesignerWorkload]
    customer_summary: list[CustomerSummaryReportRow]


class TimesheetApprovalReportRow(BaseModel):
    timesheet_id: UUID
    user_name: str
    week_start: date
    status: TimesheetStatus
    total_hours: Decimal
    approved_by_name: str | None = None
    approval_comments: str | None = None


class ProjectDelayReportRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    due_date: date
    days_overdue: int
    health: ProjectHealth
    execution_status: ExecutionStatus
    project_stage: ProjectStage


class MilestoneCompletionReportRow(BaseModel):
    project_code: str
    milestone_name: str
    status: MilestoneStatus
    due_date: date | None = None
    completed_at: datetime | None = None


class DesignerProductivityReportRow(BaseModel):
    user_id: UUID
    designer_name: str
    role: str
    approved_hours: Decimal
    submitted_hours: Decimal
    draft_hours: Decimal


class ProductiveHoursReportRow(BaseModel):
    project_id: UUID | None = None
    tool_number: str | None = None
    customer_name: str | None = None
    task_type_name: str | None = None
    total_hours: Decimal
    billable_hours: Decimal
    non_billable_hours: Decimal


class NonProductiveHoursReportRow(BaseModel):
    non_productive_code: str
    description: str
    customer_name: str | None = None
    total_hours: Decimal


class BillableUtilizationReportRow(BaseModel):
    user_id: UUID
    designer_name: str
    billable_hours: Decimal
    non_billable_hours: Decimal
    np_hours: Decimal
    billable_percent: Decimal
    non_billable_percent: Decimal


class MonthlyNpTrendReportRow(BaseModel):
    month: str
    total_np_hours: Decimal


class NpHoursByDesignerReportRow(BaseModel):
    user_id: UUID
    designer_name: str
    total_np_hours: Decimal


class BillableVsNonBillableReportRow(BaseModel):
    billable_hours: Decimal
    non_billable_hours: Decimal
    np_hours: Decimal
    billable_percent: Decimal
    non_billable_percent: Decimal


class TopNpActivityReportRow(BaseModel):
    non_productive_code: str
    description: str
    total_hours: Decimal
    entry_count: int


class ProjectPortfolioReportRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    project_stage: ProjectStage
    execution_status: ExecutionStatus
    due_date: date
    health: ProjectHealth


class ProjectStageSummaryRow(BaseModel):
    project_stage: ProjectStage
    project_count: int


class ExecutionStatusSummaryRow(BaseModel):
    execution_status: ExecutionStatus
    project_count: int
