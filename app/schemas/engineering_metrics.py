"""Per-project engineering metrics: approved estimate, actual hours and variance."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.engineering_performance import KpiDefinition

MetricStatus = Literal["available", "unavailable", "not_applicable"]
EstimateSource = Literal["stage_estimates", "milestone_hours", "quoted_hours", "none"]


class MetricValue(BaseModel):
    """A calculated value; ``value`` is null whenever ``status`` is not ``available``."""

    value: Decimal | None = None
    status: MetricStatus
    reason: str | None = None


class DataQualityIssue(BaseModel):
    code: str
    severity: Literal["info", "warning"]
    message: str


class EstimateMetrics(BaseModel):
    quoted_hours: Decimal | None = None
    original_estimate_hours: Decimal | None = None
    current_estimate_hours: Decimal | None = None
    estimate_source: EstimateSource
    estimate_source_label: str
    revision_count: int = 0
    last_revised_at: datetime | None = None


class ActualHoursMetrics(BaseModel):
    status: Literal["recorded", "none_recorded", "missing"]
    total_hours: Decimal | None = None
    entry_count: int = 0
    before_completion_hours: Decimal = Decimal("0")
    post_completion_hours: Decimal = Decimal("0")
    approved_hours: Decimal = Decimal("0")
    submitted_hours: Decimal = Decimal("0")
    draft_hours: Decimal = Decimal("0")
    rejected_hours: Decimal = Decimal("0")


class StageHoursRow(BaseModel):
    key: str
    label: str
    original_estimate_hours: Decimal | None = None
    current_estimate_hours: Decimal | None = None
    actual_hours: Decimal
    variance_hours: Decimal | None = None


class StageAttributionMetrics(BaseModel):
    status: Literal["complete", "partial", "unavailable", "no_hours"]
    coverage_percent: Decimal | None = None
    attributed_hours: Decimal = Decimal("0")
    other_stage_hours: Decimal = Decimal("0")
    no_stage_hours: Decimal = Decimal("0")
    no_milestone_hours: Decimal = Decimal("0")
    invalid_milestone_hours: Decimal = Decimal("0")
    rows: list[StageHoursRow] = Field(default_factory=list)


class MilestoneReadiness(BaseModel):
    total: int = 0
    completed: int = 0
    open: int = 0
    skipped: int = 0
    open_required: int = 0
    open_without_target_date: int = 0
    open_overdue: int = 0
    completed_with_completion_date: int = 0
    with_baseline_finish_date: int = 0
    with_original_planned_hours: int = 0
    current_target_date: date | None = None
    baseline_completion_date: date | None = None
    original_baseline_completion_date: date | None = None
    baseline_revision_count: int = 0
    actual_completion_date: date | None = None


class QuoteLinkage(BaseModel):
    status: Literal["linked", "unlinked", "ambiguous"]
    active_quote_count: int = 0
    details_visible: bool = False
    quote_reference: str | None = None
    quote_version: int | None = None
    quote_revision: str | None = None
    quote_hours: Decimal | None = None


class ProjectEngineeringMetrics(BaseModel):
    project_id: UUID
    code: str | None = None
    tool_number: str | None = None
    part_description: str | None = None
    execution_status: str
    data_quality_status: Literal["available", "available_with_limitations", "unavailable"]
    estimate: EstimateMetrics
    actual: ActualHoursMetrics
    variance_hours: MetricValue
    utilization_percent: MetricValue
    remaining_hours: MetricValue
    original_variance_hours: MetricValue
    stage_attribution: StageAttributionMetrics
    milestones: MilestoneReadiness
    quote_linkage: QuoteLinkage
    issues: list[DataQualityIssue] = Field(default_factory=list)
    definitions: list[KpiDefinition] = Field(default_factory=list)
    calculated_at: datetime
