from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

PeriodType = Literal["weekly", "monthly", "quarterly", "yearly", "custom"]
PlanBasis = Literal["current", "original"]
BreakdownDimension = Literal[
    "customer",
    "end_customer",
    "team",
    "design_leader",
    "designer",
    "surfacer",
    "project_type",
    "template",
    "period",
]


class PerformancePeriod(BaseModel):
    period_type: PeriodType
    label: str
    start_date: date
    end_date: date
    financial_year_start_month: int


class KpiDefinition(BaseModel):
    key: str
    label: str
    definition: str


class PerformanceSummary(BaseModel):
    projects_completed: int
    plan_basis: PlanBasis
    planned_hours: float
    projects_without_plan: int
    actual_hours: float
    eac_hours: float
    variance_hours: float
    variance_percent: float | None = None
    on_time_projects: int
    late_projects: int
    projects_without_reference_date: int
    on_time_rate: float | None = None
    average_days_late: float | None = None
    milestones_total: int
    milestones_completed: int
    milestones_on_time: int
    milestone_on_time_rate: float | None = None
    delivery_evaluable_projects: int = 0
    delivered_early: int = 0
    delivered_on_reference_date: int = 0
    delivered_late: int = 0
    average_delivery_variance_days: float | None = None
    median_delivery_variance_days: float | None = None
    delivery_reference_counts: dict[str, int] = Field(default_factory=dict)


class StagePerformanceRow(BaseModel):
    stage: str
    label: str
    projects: int
    original_hours: float
    current_hours: float
    actual_hours: float
    variance_hours: float
    variance_percent: float | None = None
    eligible_projects: int = 0
    average_variance_hours: float | None = None
    median_variance_hours: float | None = None
    projects_over_estimate: int = 0
    percent_over_estimate: float | None = None
    actual_share_percent: float | None = None


class StagePerformance(BaseModel):
    projects_with_stage_plan: int
    projects_without_stage_plan: int
    rows: list[StagePerformanceRow] = Field(default_factory=list)
    unstaged_actual_hours: float = 0.0
    complete_attribution_projects: int = 0
    partial_attribution_projects: int = 0
    unattributed_projects: int = 0
    eligibility_rule: str = ""


class EffortClassificationRow(BaseModel):
    key: str
    label: str
    hours: float
    percent: float | None = None


class BreakdownRow(BaseModel):
    key: str
    label: str
    projects: int
    planned_hours: float
    actual_hours: float
    variance_hours: float
    variance_percent: float | None = None
    on_time_projects: int
    on_time_rate: float | None = None


class Breakdown(BaseModel):
    dimension: BreakdownDimension
    label: str
    rows: list[BreakdownRow] = Field(default_factory=list)


class ProjectPerformanceRow(BaseModel):
    project_id: UUID
    code: str | None = None
    tool_number: str | None = None
    part_description: str | None = None
    customer_name: str | None = None
    end_customer_name: str | None = None
    team_name: str | None = None
    design_leader_name: str | None = None
    designer_name: str | None = None
    surfacer_name: str | None = None
    project_type_name: str | None = None
    template_name: str | None = None
    start_date: date | None = None
    actual_start_date: date | None = None
    actual_completion_date: date
    reference_completion_date: date | None = None
    reference_source: Literal["baseline", "legacy_due_date", "none"]
    on_time: bool | None = None
    days_late: int | None = None
    original_planned_hours: float | None = None
    current_planned_hours: float | None = None
    planned_hours: float | None = None
    plan_source: str
    actual_hours: float
    variance_hours: float | None = None
    variance_percent: float | None = None
    stage_planned: bool
    milestones_total: int
    milestones_completed: int
    milestones_on_time: int
    original_baseline_completion_date: date | None = None
    current_baseline_completion_date: date | None = None
    delivery_reference_source: str = "none"
    delivery_reference_date: date | None = None
    delivery_status: str | None = None
    delivery_variance_days: int | None = None
    stage_attribution_status: str = "unavailable"


class PerformanceDataWarning(BaseModel):
    code: str
    message: str
    project_codes: list[str] = Field(default_factory=list)


class EngineeringPerformanceReport(BaseModel):
    period: PerformancePeriod
    filters: dict[str, str | None] = Field(default_factory=dict)
    summary: PerformanceSummary
    stage_performance: StagePerformance
    effort_by_classification: list[EffortClassificationRow] = Field(default_factory=list)
    breakdowns: list[Breakdown] = Field(default_factory=list)
    projects: list[ProjectPerformanceRow] = Field(default_factory=list)
    warnings: list[PerformanceDataWarning] = Field(default_factory=list)
    definitions: list[KpiDefinition] = Field(default_factory=list)
    empty_message: str | None = None
