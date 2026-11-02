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
    billable_hours: Decimal | None = None
    entry_count: int = 0
    before_completion_hours: Decimal = Decimal("0")
    post_completion_hours: Decimal = Decimal("0")
    approved_hours: Decimal = Decimal("0")
    submitted_hours: Decimal = Decimal("0")
    draft_hours: Decimal = Decimal("0")
    rejected_hours: Decimal = Decimal("0")


class StageHoursRow(BaseModel):
    """One engineering stage that exists in this project's plan.

    ``actual_hours`` is null when stage hours cannot be determined (no timesheet
    entry is linked to a staged milestone, or the project's actual hours are
    missing). ``variance_hours`` mirrors ``variance.value`` for older clients.
    """

    key: str
    label: str
    has_approved_estimate: bool = False
    original_estimate_hours: Decimal | None = None
    current_estimate_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    percent_of_project_actual: Decimal | None = None
    variance_hours: Decimal | None = None
    variance: MetricValue = Field(default_factory=lambda: MetricValue(status="unavailable"))
    utilization_percent: MetricValue = Field(
        default_factory=lambda: MetricValue(status="unavailable")
    )
    remaining_hours: MetricValue = Field(default_factory=lambda: MetricValue(status="unavailable"))
    data_quality: Literal["complete", "limited", "unavailable"] = "unavailable"
    data_quality_notes: list[str] = Field(default_factory=list)


class StageAttributionMetrics(BaseModel):
    """Stage rows plus unattributed hours reconcile to ``total_hours``.

    ``attributed_hours`` covers every stage row (including stages without an
    approved estimate, such as Feasibility); ``other_stage_hours`` is the part of
    it on stages outside Blockout / Intermediate Design / Final Design.
    """

    status: Literal["complete", "partial", "unavailable", "no_hours"]
    coverage_percent: Decimal | None = None
    total_hours: Decimal | None = None
    attributed_hours: Decimal = Decimal("0")
    unattributed_hours: Decimal = Decimal("0")
    other_stage_hours: Decimal = Decimal("0")
    no_stage_hours: Decimal = Decimal("0")
    no_milestone_hours: Decimal = Decimal("0")
    invalid_milestone_hours: Decimal = Decimal("0")
    source: str = ""
    rows: list[StageHoursRow] = Field(default_factory=list)


DeliveryStatus = Literal[
    "early",
    "on_time",
    "late",
    "overdue",
    "not_due",
    "no_target",
    "completion_date_missing",
    "not_applicable",
]
DeliveryReference = Literal["original_baseline", "baseline_unverified", "current_due_date", "none"]


class ProjectDelivery(BaseModel):
    """Project delivery dates and variance. Variance days = actual − reference (positive = late)."""

    status: DeliveryStatus
    reference_source: DeliveryReference
    reference_label: str
    reference_date: date | None = None
    original_baseline_completion_date: date | None = None
    current_baseline_completion_date: date | None = None
    current_due_date: date | None = None
    current_target_date: date | None = None
    actual_completion_date: date | None = None
    schedule_variance_days: int | None = None
    current_target_variance_days: int | None = None
    days_overdue: int | None = None
    target_moved_days: int | None = None
    baseline_revision_count: int = 0
    original_due_date_preserved: bool = False


class MilestoneDelivery(BaseModel):
    milestone_id: UUID
    name: str
    stage: str | None = None
    stage_label: str | None = None
    milestone_status: str
    is_required: bool = True
    original_baseline_finish_date: date | None = None
    current_baseline_finish_date: date | None = None
    current_due_date: date | None = None
    current_target_date: date | None = None
    actual_completion_date: date | None = None
    reference_date: date | None = None
    reference_source: DeliveryReference
    status: DeliveryStatus
    schedule_variance_days: int | None = None
    days_overdue: int | None = None


class DeliveryMetrics(BaseModel):
    sign_convention: str
    project: ProjectDelivery
    milestones: list[MilestoneDelivery] = Field(default_factory=list)
    milestone_status_counts: dict[str, int] = Field(default_factory=dict)


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
    delivery: DeliveryMetrics
    quote_linkage: QuoteLinkage
    issues: list[DataQualityIssue] = Field(default_factory=list)
    definitions: list[KpiDefinition] = Field(default_factory=list)
    calculated_at: datetime
