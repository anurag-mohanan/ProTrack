"""Phase 3 forecasting responses. Actual, approved plan and forecast values are separate fields."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ForecastStatus = Literal["available", "preliminary", "unavailable"]
ValueKind = Literal["actual", "approved_plan", "forecast", "scenario", "commitment"]
Granularity = Literal["week", "month"]


class ForecastMetadata(BaseModel):
    forecast_type: str
    method_version: str
    generated_at: datetime
    as_of: date
    period_start: date | None = None
    period_end: date | None = None
    status: ForecastStatus
    status_reason: str | None = None
    confidence: None = None
    confidence_note: str
    sources: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ForecastDefinition(BaseModel):
    key: str
    label: str
    value_kind: ValueKind
    method_version: str
    description: str
    deferred: bool = False
    deferred_reason: str | None = None


class ForecastPeriod(BaseModel):
    key: str
    label: str
    start_date: date
    end_date: date


# ----------------------------------------------------------------- engineering


class EffortHistorySummary(BaseModel):
    sample_size: int
    minimum_sample: int
    factor: Decimal | None = None
    factor_status: ForecastStatus
    factor_reason: str | None = None
    basis: str
    visible_sample_project_ids: list[UUID] = Field(default_factory=list)


class EffortBacktest(BaseModel):
    status: Literal["evaluated", "not_possible"]
    reason: str | None = None
    candidate_count: int = 0
    evaluated_count: int = 0
    mean_absolute_error_hours: Decimal | None = None
    mean_absolute_percentage_error: Decimal | None = None
    mean_signed_error_hours: Decimal | None = None
    naive_mean_absolute_error_hours: Decimal | None = None
    naive_mean_absolute_percentage_error: Decimal | None = None
    method: str


class ProjectEffortForecast(BaseModel):
    project_id: UUID
    code: str | None = None
    tool_number: str | None = None
    execution_status: str
    quoted_hours: Decimal | None = None
    estimate_source: str
    approved_original_estimate_hours: Decimal | None = None
    approved_current_estimate_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    actual_status: str
    actual_unapproved_hours: Decimal = Decimal("0")
    actual_rejected_hours: Decimal = Decimal("0")
    approved_remaining_hours: Decimal | None = None
    forecast_status: ForecastStatus
    forecast_reason: str | None = None
    forecast_at_completion_hours: Decimal | None = None
    forecast_remaining_hours: Decimal | None = None
    original_commitment_date: date | None = None
    original_commitment_source: str
    current_target_date: date | None = None
    target_moved_days: int | None = None
    provisional_schedule_date: date | None = None
    provisional_schedule_status: str | None = None
    completion_forecast_status: ForecastStatus = "unavailable"
    completion_forecast_reason: str
    stage_forecast_status: ForecastStatus = "unavailable"
    stage_forecast_reason: str
    data_quality_codes: list[str] = Field(default_factory=list)


class EngineeringForecastSummary(BaseModel):
    projects: int = 0
    available: int = 0
    preliminary: int = 0
    unavailable: int = 0
    approved_remaining_hours: Decimal = Decimal("0")
    forecast_remaining_hours: Decimal | None = None
    forecast_remaining_note: str


class EngineeringForecastResponse(BaseModel):
    metadata: ForecastMetadata
    history: EffortHistorySummary
    backtest: EffortBacktest
    summary: EngineeringForecastSummary
    projects: list[ProjectEffortForecast]


# ----------------------------------------------------------------- capacity


class CapacityBreakdown(BaseModel):
    period_key: str
    scheduled_hours: Decimal = Decimal("0")
    holiday_hours: Decimal = Decimal("0")
    outside_employment_hours: Decimal = Decimal("0")
    status_unavailable_hours: Decimal = Decimal("0")
    available_hours: Decimal = Decimal("0")
    allocatable_hours: Decimal = Decimal("0")


class PersonCapacity(BaseModel):
    user_id: UUID
    name: str
    team_id: UUID | None = None
    team_name: str | None = None
    hours_source: Literal["shift", "baseline", "mixed", "none"]
    availability_status: str
    max_allocation_percent: int
    joining_date: date | None = None
    leaving_date: date | None = None
    periods: list[CapacityBreakdown]
    total: CapacityBreakdown


class TeamCapacity(BaseModel):
    team_id: UUID | None = None
    team_name: str
    headcount: int
    periods: list[CapacityBreakdown]
    total: CapacityBreakdown


class DesignerDemand(BaseModel):
    user_id: UUID
    name: str
    approved_remaining_hours: Decimal
    projects: int


class DemandSummary(BaseModel):
    value_kind: ValueKind = "approved_plan"
    approved_remaining_hours: Decimal = Decimal("0")
    projects_with_approved_estimate: int = 0
    projects_without_approved_estimate: int = 0
    projects_without_designer: int = 0
    by_designer: list[DesignerDemand] = Field(default_factory=list)
    phasing_status: ForecastStatus = "unavailable"
    phasing_reason: str


class CapacityForecastResponse(BaseModel):
    metadata: ForecastMetadata
    granularity: Granularity
    periods: list[ForecastPeriod]
    totals: list[CapacityBreakdown]
    grand_total: CapacityBreakdown
    teams: list[TeamCapacity]
    people: list[PersonCapacity]
    demand: DemandSummary
    gap_analysis_status: ForecastStatus = "unavailable"
    gap_analysis_reason: str
    skill_demand_status: ForecastStatus = "unavailable"
    skill_demand_reason: str


# ----------------------------------------------------------------- finance


class CollectionItem(BaseModel):
    quote_id: UUID
    tool_number: str
    customer_id: UUID | None = None
    customer_name: str | None = None
    project_id: UUID | None = None
    currency: str
    invoice_line_id: UUID
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    due_date_source: str | None = None
    invoice_amount: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    timing: Literal["scheduled", "overdue", "no_due_date"]
    expected_period_key: str | None = None
    days_overdue: int | None = None


class BillingItem(BaseModel):
    quote_id: UUID
    tool_number: str
    project_id: UUID
    project_code: str | None = None
    currency: str
    kind: Literal["milestone", "unscheduled_remaining"]
    milestone_id: UUID | None = None
    milestone_name: str | None = None
    trigger_type: str | None = None
    trigger_status: str | None = None
    amount: Decimal
    date_status: Literal["ready_to_invoice", "dated_by_target", "undated"]
    expected_invoice_date: date | None = None
    expected_period_key: str | None = None
    depends_on_delivery: bool = False
    reason: str


class ExcludedQuote(BaseModel):
    quote_id: UUID
    tool_number: str
    currency: str
    remaining_to_invoice: Decimal
    reason: str


class CurrencyTotals(BaseModel):
    currency: str
    quotes: int = 0
    awarded_value: Decimal = Decimal("0")
    invoiced: Decimal = Decimal("0")
    collected: Decimal = Decimal("0")
    outstanding: Decimal = Decimal("0")
    outstanding_scheduled: Decimal = Decimal("0")
    outstanding_overdue: Decimal = Decimal("0")
    outstanding_no_due_date: Decimal = Decimal("0")
    remaining_to_invoice: Decimal = Decimal("0")
    billing_ready: Decimal = Decimal("0")
    billing_dated: Decimal = Decimal("0")
    billing_undated: Decimal = Decimal("0")
    excluded_remaining_to_invoice: Decimal = Decimal("0")
    collections_by_period: dict[str, Decimal] = Field(default_factory=dict)
    billing_by_period: dict[str, Decimal] = Field(default_factory=dict)


class FinanceReconciliation(BaseModel):
    quotes_considered: int
    outstanding_matches_ledger: bool
    billing_matches_remaining: bool
    notes: list[str] = Field(default_factory=list)


class FinanceForecastResponse(BaseModel):
    metadata: ForecastMetadata
    granularity: Granularity
    periods: list[ForecastPeriod]
    totals: list[CurrencyTotals]
    collections: list[CollectionItem]
    billing: list[BillingItem]
    excluded: list[ExcludedQuote]
    warnings: list[str] = Field(default_factory=list)
    reconciliation: FinanceReconciliation


class ForecastCatalogResponse(BaseModel):
    definitions: list[ForecastDefinition]
    can_view_engineering: bool
    can_view_capacity: bool
    can_view_finance: bool
