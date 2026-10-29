"""Quote-to-Delivery management report.

Every figure is aggregated from ``ProjectEngineeringMetrics`` (the same payload the
project page shows); nothing here is calculated independently.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.engineering_performance import KpiDefinition, PerformanceDataWarning

QtdPopulationKey = Literal["completed", "active"]


class QtdPopulation(BaseModel):
    key: QtdPopulationKey
    label: str
    date_basis: str
    as_of: date


class QtdPeriod(BaseModel):
    period_type: str
    label: str
    start_date: date
    end_date: date
    financial_year_start_month: int = 4
    applies_to: str


class QtdSummary(BaseModel):
    eligible_projects: int = 0
    quoted_hours_total: Decimal = Decimal("0")
    projects_with_quoted_hours: int = 0
    current_estimate_total: Decimal = Decimal("0")
    projects_with_current_estimate: int = 0
    estimate_source_counts: dict[str, int] = Field(default_factory=dict)
    actual_hours_total: Decimal = Decimal("0")
    projects_with_actual_hours: int = 0
    projects_actual_missing: int = 0
    comparable_projects: int = 0
    comparable_estimate_hours: Decimal = Decimal("0")
    comparable_actual_hours: Decimal = Decimal("0")
    variance_hours: Decimal | None = None
    utilization_percent: Decimal | None = None
    projects_over_estimate: int = 0
    projects_under_estimate: int = 0
    projects_on_estimate: int = 0
    projects_not_comparable: int = 0
    projects_metrics_unavailable: int = 0
    projects_metrics_limited: int = 0


class QtdProjectRow(BaseModel):
    project_id: UUID
    code: str | None = None
    tool_number: str | None = None
    part_description: str | None = None
    customer_name: str | None = None
    classification: str | None = None
    classification_label: str | None = None
    project_type_name: str | None = None
    execution_status: str
    design_leader_name: str | None = None
    designer_name: str | None = None
    quoted_hours: Decimal | None = None
    current_estimate_hours: Decimal | None = None
    estimate_source: str
    estimate_source_label: str
    actual_hours: Decimal | None = None
    actual_status: str
    variance_hours: Decimal | None = None
    utilization_percent: Decimal | None = None
    comparable: bool = False
    original_baseline_completion_date: date | None = None
    current_baseline_completion_date: date | None = None
    current_target_date: date | None = None
    delivery_reference_source: str
    actual_completion_date: date | None = None
    delivery_variance_days: int | None = None
    delivery_status: str
    days_overdue: int | None = None
    open_overdue_milestones: int = 0
    stage_attribution_status: str
    data_quality_status: Literal["available", "available_with_limitations", "unavailable"]
    data_quality_issues: list[str] = Field(default_factory=list)
    data_quality_warnings: list[str] = Field(default_factory=list)


class QtdProjectPage(BaseModel):
    items: list[QtdProjectRow] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25
    pages: int = 0
    search: str | None = None
    segment: str | None = None
    stage: str | None = None
    sort: str


class QtdStageRow(BaseModel):
    key: str
    label: str
    projects_in_plan: int = 0
    eligible_projects: int = 0
    estimate_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    variance_hours: Decimal | None = None
    utilization_percent: Decimal | None = None
    projects_over_estimate: int = 0
    projects_missing_attribution: int = 0
    projects_without_estimate: int = 0
    explanation: str | None = None


class QtdStageSection(BaseModel):
    rows: list[QtdStageRow] = Field(default_factory=list)
    eligibility_rule: str
    source: str


class QtdHistoricalDelivery(BaseModel):
    population_rule: str
    completed_projects: int = 0
    eligible_projects: int = 0
    on_or_before_baseline: int = 0
    after_baseline: int = 0
    average_variance_days: float | None = None
    median_variance_days: float | None = None
    excluded_baseline_unverified: int = 0
    excluded_due_date_only: int = 0
    excluded_no_reference: int = 0
    completed_without_completion_date: int = 0


class QtdOperationalDelivery(BaseModel):
    population_rule: str
    as_of: date
    active_projects: int = 0
    projects_with_overdue_milestones: int = 0
    overdue_milestones: int = 0
    projects_past_current_target: int = 0
    projects_without_current_target: int = 0
    projects_without_original_baseline: int = 0


class QtdDelivery(BaseModel):
    sign_convention: str
    historical: QtdHistoricalDelivery
    operational: QtdOperationalDelivery


class QuoteToDeliveryReport(BaseModel):
    population: QtdPopulation
    period: QtdPeriod
    filters: dict[str, str | None] = Field(default_factory=dict)
    summary: QtdSummary
    projects: QtdProjectPage
    stages: QtdStageSection
    delivery: QtdDelivery
    warnings: list[PerformanceDataWarning] = Field(default_factory=list)
    definitions: list[KpiDefinition] = Field(default_factory=list)
    empty_message: str | None = None
    generated_at: datetime
