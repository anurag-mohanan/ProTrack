"""Schemas for the Engineering Management Reporting Engine."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ExecutionStatus, ProjectHealth, ProjectStage


class ReportPeriod(BaseModel):
    period_type: str
    label: str
    start_date: date
    end_date: date
    working_days: int


class ReportCatalogEntry(BaseModel):
    id: str
    title: str
    description: str
    category: str
    supported_periods: list[str] = Field(default_factory=lambda: ["monthly"])
    export_formats: list[str] = Field(default_factory=lambda: ["xlsx", "json"])
    drill_down_routes: dict[str, str] = Field(default_factory=dict)


class ReportCatalog(BaseModel):
    reports: list[ReportCatalogEntry]


class ExecutiveKpiCard(BaseModel):
    label: str
    value: str
    accent: str | None = None


class ExecutiveSummary(BaseModel):
    period: ReportPeriod
    company_name: str
    kpis: list[ExecutiveKpiCard]
    total_engineering_hours: Decimal
    productive_hours: Decimal
    non_productive_hours: Decimal
    billable_percent: Decimal
    utilization_percent: Decimal
    leave_days: int
    team_size: int


class DesignerProductivityRow(BaseModel):
    user_id: UUID
    designer_name: str
    team_name: str | None = None
    productive_hours: Decimal
    non_productive_hours: Decimal
    leave_days: Decimal
    total_hours: Decimal
    billable_percent: Decimal
    utilization_percent: Decimal
    project_count: int
    customer_count: int


class DesignerToolBreakdownRow(BaseModel):
    user_id: UUID
    designer_name: str
    tool_number: str
    customer_name: str
    project_id: UUID | None = None
    design_hours: Decimal = Decimal("0")
    surfacing_hours: Decimal = Decimal("0")
    review_hours: Decimal = Decimal("0")
    bom_hours: Decimal = Decimal("0")
    meeting_hours: Decimal = Decimal("0")
    np_hours: Decimal = Decimal("0")
    other_hours: Decimal = Decimal("0")
    total_hours: Decimal = Decimal("0")


class ToolHoursRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    part_description: str
    design_leader_name: str | None = None
    designer_name: str | None = None
    surfacer_name: str | None = None
    quoted_hours: Decimal
    actual_hours: Decimal
    variance_hours: Decimal
    variance_percent: Decimal
    completion_percent: Decimal
    project_stage: ProjectStage
    execution_status: ExecutionStatus
    health: ProjectHealth | None = None


class CustomerHoursRow(BaseModel):
    customer_id: UUID
    customer_name: str
    project_count: int
    productive_hours: Decimal
    np_hours: Decimal
    total_hours: Decimal
    designer_count: int
    avg_hours_per_project: Decimal


class TeamSummaryRow(BaseModel):
    team_id: UUID | None = None
    team_name: str
    designer_count: int
    project_count: int
    productive_hours: Decimal
    np_hours: Decimal
    leave_days: Decimal
    total_hours: Decimal
    utilization_percent: Decimal


class FunctionHoursRow(BaseModel):
    function_group: str
    hours: Decimal
    percent: Decimal


class NpAnalysisRow(BaseModel):
    code: str
    description: str
    hours: Decimal
    percent: Decimal


class LeaveAnalysisRow(BaseModel):
    user_id: UUID
    designer_name: str
    leave_days: Decimal
    leave_hours: Decimal


class QuotedVsActualRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    quoted_hours: Decimal
    actual_hours: Decimal
    variance_hours: Decimal
    variance_percent: Decimal
    completion_percent: Decimal
    health: ProjectHealth | None = None
    late_milestones: int = 0


class ProjectPerformanceRow(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    designer_name: str | None = None
    surfacer_name: str | None = None
    project_stage: ProjectStage
    quoted_hours: Decimal
    actual_hours: Decimal
    milestone_completion_percent: Decimal
    health: ProjectHealth | None = None
    predicted_finish: date | None = None


class DetailedTimesheetRow(BaseModel):
    entry_date: date
    designer_name: str
    team_name: str | None = None
    customer_name: str | None = None
    tool_number: str | None = None
    task_name: str | None = None
    hours: Decimal
    is_billable: bool
    category: str
    notes: str | None = None


class ChartSeries(BaseModel):
    title: str
    labels: list[str]
    values: list[float]


class EngineeringReportPayload(BaseModel):
    report_id: str
    period: ReportPeriod
    company_name: str
    executive: ExecutiveSummary
    designer_productivity: list[DesignerProductivityRow]
    designer_tool_breakdown: list[DesignerToolBreakdownRow]
    tool_hours: list[ToolHoursRow]
    customer_summary: list[CustomerHoursRow]
    team_summary: list[TeamSummaryRow]
    function_hours: list[FunctionHoursRow]
    np_analysis: list[NpAnalysisRow]
    leave_analysis: list[LeaveAnalysisRow]
    quoted_vs_actual: list[QuotedVsActualRow]
    project_performance: list[ProjectPerformanceRow]
    detailed_entries: list[DetailedTimesheetRow]
    charts: list[ChartSeries] = Field(default_factory=list)
    ai_insights: list[str] = Field(default_factory=list)


class ReportScheduleRequest(BaseModel):
  report_id: str
  period_type: str = "monthly"
  frequency: str = "monthly"
  enabled: bool = True


class ReportScheduleEntry(BaseModel):
    report_id: str
    period_type: str
    frequency: str
    enabled: bool
    note: str = "Scheduled reports are stored and will email recipients when SMTP is enabled."
