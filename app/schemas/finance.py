"""Pydantic schemas for Financial Planning."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AiForecastKind,
    BudgetApprovalStatus,
    BudgetScopeType,
    CostFrequency,
    CostNature,
    ExpensePaidBy,
    FinancePlanSection,
    FinancePlanStatus,
    TeamBillingMode,
    TeamBillingPeriod,
)


class CurrencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    symbol: str | None = None
    is_active: bool
    is_base: bool


class FxRateCreate(BaseModel):
    from_currency: str
    to_currency: str = "INR"
    rate: Decimal
    effective_date: date
    source: str = "manual"


class FxRateRead(FxRateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime | None = None


class CostCentreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    nature: CostNature
    default_frequency: CostFrequency
    is_active: bool
    sort_order: int


class ExpenseCreate(BaseModel):
    cost_centre_id: UUID
    name: str
    description: str | None = None
    nature: CostNature = CostNature.opex
    frequency: CostFrequency = CostFrequency.monthly
    currency_code: str = "INR"
    amount: Decimal
    purchase_date: date
    start_date: date | None = None
    end_date: date | None = None
    is_recurring: bool = False
    paid_by: ExpensePaidBy | None = None
    vendor_name: str | None = None
    next_renewal_date: date | None = None
    notify_before_days: int = Field(default=7, ge=0, le=365)
    notify_enabled: bool = True
    team_id: UUID
    project_id: UUID | None = None


class ExpenseUpdate(BaseModel):
    cost_centre_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    nature: CostNature | None = None
    frequency: CostFrequency | None = None
    currency_code: str | None = None
    amount: Decimal | None = None
    purchase_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_recurring: bool | None = None
    paid_by: ExpensePaidBy | None = None
    vendor_name: str | None = None
    next_renewal_date: date | None = None
    notify_before_days: int | None = Field(default=None, ge=0, le=365)
    notify_enabled: bool | None = None
    team_id: UUID | None = None
    project_id: UUID | None = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cost_centre_id: UUID
    name: str
    description: str | None = None
    nature: CostNature
    frequency: CostFrequency
    currency_code: str
    amount: Decimal
    purchase_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_recurring: bool
    paid_by: ExpensePaidBy
    vendor_name: str | None = None
    next_renewal_date: date | None = None
    notify_before_days: int
    notify_enabled: bool
    team_id: UUID | None = None
    project_id: UUID | None = None
    base_amount_inr: Decimal
    fx_rate: Decimal
    fx_date: date
    is_active: bool
    renewal_notified_for: date | None = None
    prior_fy_excluded_from_overview: bool = False


class PaidByDefaultRead(BaseModel):
    paid_by: ExpensePaidBy
    reason: str


class EmployeeCostProfileCreate(BaseModel):
    user_id: UUID
    currency_code: str = "INR"
    monthly_salary: Decimal = Decimal("0")
    hourly_cost: Decimal = Decimal("0")
    contractor_cost: Decimal | None = None
    effective_from: date
    notes: str | None = None


class EmployeeCostProfileRead(EmployeeCostProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    base_monthly_salary_inr: Decimal
    base_hourly_cost_inr: Decimal
    fx_rate: Decimal
    is_active: bool


class EmployeeCostRosterItem(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    team_names: list[str] = Field(default_factory=list)
    requires_salary: bool = True
    has_profile: bool
    profile_id: UUID | None = None
    currency_code: str | None = None
    monthly_salary: Decimal | None = None
    hourly_cost: Decimal | None = None
    base_monthly_salary_inr: Decimal | None = None
    effective_from: date | None = None
    notes: str | None = None
    joining_date: date | None = None
    leaving_date: date | None = None
    salary_month_factor: str | None = None


class EmployeeLeavingDateUpdate(BaseModel):
    leaving_date: date | None = None


class TeamCommercialFeeBandInput(BaseModel):
    skill_level: str | None = None
    fee_amount: Decimal = Decimal("0")
    currency_code: str | None = None
    notes: str | None = None


class TeamCommercialFeeBandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    terms_id: UUID
    skill_level: str | None = None
    fee_amount: Decimal
    currency_code: str
    base_fee_inr: Decimal
    fx_rate: Decimal
    notes: str | None = None
    billable_count: int = 0


class TeamCommercialTermsCreate(BaseModel):
    team_id: UUID
    working_model_id: UUID
    billing_mode: TeamBillingMode | None = None
    customer_fee_amount: Decimal = Decimal("0")
    currency_code: str = "INR"
    billing_period: TeamBillingPeriod = TeamBillingPeriod.monthly
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    customer_pays_software: bool = False
    customer_pays_hardware: bool = False
    fee_bands: list[TeamCommercialFeeBandInput] = Field(default_factory=list)


class TeamCommercialTermsUpdate(BaseModel):
    working_model_id: UUID | None = None
    billing_mode: TeamBillingMode | None = None
    customer_fee_amount: Decimal | None = None
    currency_code: str | None = None
    billing_period: TeamBillingPeriod | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    notes: str | None = None
    is_active: bool | None = None
    customer_pays_software: bool | None = None
    customer_pays_hardware: bool | None = None
    fee_bands: list[TeamCommercialFeeBandInput] | None = None


class TeamCommercialTermsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    working_model_id: UUID
    billing_mode: TeamBillingMode
    customer_fee_amount: Decimal
    currency_code: str
    billing_period: TeamBillingPeriod
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    customer_pays_software: bool = False
    customer_pays_hardware: bool = False
    base_fee_inr: Decimal
    fx_rate: Decimal
    is_active: bool
    team_name: str | None = None
    working_model_name: str | None = None
    working_model_strategy: str | None = None
    resource_count: int | None = None
    monthly_fee_signal_inr: Decimal | None = None
    fee_bands: list[TeamCommercialFeeBandRead] = Field(default_factory=list)


class TeamFinanceBreakdown(BaseModel):
    team_id: str
    team_name: str
    is_overhead_home: bool = False
    salary_cost_inr: Decimal
    prosohm_opex_inr: Decimal
    pass_through_opex_inr: Decimal
    monthly_operating_cost_inr: Decimal
    team_commercial_fee_monthly_inr: Decimal
    quote_revenue_inr: Decimal = Decimal("0")
    estimated_cost_inr: Decimal = Decimal("0")
    planning_revenue_signal_inr: Decimal
    gross_profit_inr: Decimal = Decimal("0")
    net_profit_inr: Decimal = Decimal("0")
    gross_margin_percent: Decimal = Decimal("0")
    net_margin_percent: Decimal = Decimal("0")
    quarterly_revenue_signal_inr: Decimal = Decimal("0")


class UpcomingRenewalRead(BaseModel):
    expense_id: UUID
    name: str
    vendor_name: str | None = None
    paid_by: ExpensePaidBy
    next_renewal_date: date
    notify_before_days: int
    amount: Decimal
    currency_code: str
    base_amount_inr: Decimal
    days_until: int
    team_id: UUID | None = None
    team_name: str | None = None


class RenewalNotifyResult(BaseModel):
    notified_count: int
    expense_ids: list[UUID] = Field(default_factory=list)


class BudgetCreate(BaseModel):
    name: str
    scope_type: BudgetScopeType
    scope_id: UUID | None = None
    currency_code: str = "INR"
    allocated: Decimal = Decimal("0")
    approved_amount: Decimal = Decimal("0")
    spent: Decimal = Decimal("0")
    forecast: Decimal = Decimal("0")
    q1_allocated: Decimal = Decimal("0")
    q2_allocated: Decimal = Decimal("0")
    q3_allocated: Decimal = Decimal("0")
    q4_allocated: Decimal = Decimal("0")
    q1_forecast: Decimal = Decimal("0")
    q2_forecast: Decimal = Decimal("0")
    q3_forecast: Decimal = Decimal("0")
    q4_forecast: Decimal = Decimal("0")
    fiscal_year: int | None = None
    notes: str | None = None


class BudgetRead(BudgetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    remaining: Decimal
    variance: Decimal
    base_allocated_inr: Decimal
    base_spent_inr: Decimal
    fx_rate: Decimal
    approval_status: BudgetApprovalStatus
    is_active: bool


class BudgetStatusUpdate(BaseModel):
    approval_status: BudgetApprovalStatus


class BudgetCockpitInsight(BaseModel):
    id: str
    severity: str
    title: str
    detail: str


class BudgetCockpitTotals(BaseModel):
    budget_count: int
    allocated: Decimal
    spent: Decimal
    forecast: Decimal
    remaining: Decimal
    utilization_percent: Decimal
    draft_count: int
    approved_count: int
    at_risk_count: int


class BudgetCockpitItem(BaseModel):
    id: UUID
    name: str
    scope_type: BudgetScopeType
    scope_id: UUID | None = None
    currency_code: str
    allocated: Decimal
    spent: Decimal
    forecast: Decimal
    remaining: Decimal
    variance: Decimal
    approval_status: BudgetApprovalStatus
    fiscal_year: int | None = None
    q1_allocated: Decimal = Decimal("0")
    q2_allocated: Decimal = Decimal("0")
    q3_allocated: Decimal = Decimal("0")
    q4_allocated: Decimal = Decimal("0")
    q1_forecast: Decimal = Decimal("0")
    q2_forecast: Decimal = Decimal("0")
    q3_forecast: Decimal = Decimal("0")
    q4_forecast: Decimal = Decimal("0")
    utilization_percent: Decimal = Decimal("0")
    at_risk: bool = False
    is_active: bool = True


class BudgetCockpitRead(BaseModel):
    team_id: UUID | None = None
    currency_code: str
    planning_fy_start: str
    months_elapsed: int
    operating_monthly_inr: Decimal
    operating_ytd_inr: Decimal
    totals: BudgetCockpitTotals
    quarters: dict[str, Decimal]
    insights: list[BudgetCockpitInsight]
    budgets: list[BudgetCockpitItem]


class QuoteRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    revision: str
    quoted_hours: Decimal
    estimated_cost: Decimal
    quoted_revenue: Decimal
    margin: Decimal
    margin_percent: Decimal
    base_estimated_cost_inr: Decimal
    base_quoted_revenue_inr: Decimal
    fx_rate: Decimal
    fx_date: date
    start_date: date | None = None
    end_date: date | None = None
    imported_from: str | None = None
    imported_at: datetime | None = None


class QuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    team_id: UUID | None = None
    project_id: UUID | None = None
    tool_number: str
    external_quote_number: str | None = None
    business_model_id: UUID | None = None
    estimator_id: UUID | None = None
    currency_code: str
    quoted_date: date | None = None
    current_version: int
    current_revision: str
    is_active: bool
    team_name: str | None = None
    customer_name: str | None = None
    project_linked: bool = False
    quoted_hours: Decimal | None = None
    quoted_revenue: Decimal | None = None
    base_quoted_revenue_inr: Decimal | None = None
    fx_rate: Decimal | None = None
    fx_date: date | None = None
    revisions: list[QuoteRevisionRead] = Field(default_factory=list)


class QuoteImportItemResult(BaseModel):
    quote_id: UUID
    tool_number: str
    external_quote_number: str | None = None
    customer_name: str | None = None
    team_name: str | None = None
    quoted_hours: Decimal | None = None
    quoted_revenue: Decimal | None = None
    currency_code: str | None = None
    project_linked: bool = False
    project_created: bool = False
    warnings: list[str] = Field(default_factory=list)


class QuoteImportResult(BaseModel):
    imported_count: int
    quote_ids: list[UUID]
    items: list[QuoteImportItemResult] = Field(default_factory=list)


class QuoteManualCreate(BaseModel):
    """Phase lock: typed Quote # / Project # / Cost — no AI/PDF required."""

    team_id: UUID
    customer_id: UUID
    tool_number: str = Field(..., min_length=1, description="Customer Project #")
    quoted_revenue: Decimal = Field(..., ge=0, description="Quoted amount / cost")
    external_quote_number: str | None = Field(
        default=None, description="Quote # (e.g. QT-2026-27-005)"
    )
    currency_code: str | None = None
    quoted_hours: Decimal = Field(default=Decimal("0"), ge=0)
    quoted_date: date | None = Field(
        default=None,
        description="Award / quote document date — drives Annual Plan sales quarter",
    )
    create_project: bool = True


class QuoteUpdate(BaseModel):
    """In-place edit of awarded quote header + current revision amounts."""

    team_id: UUID | None = None
    customer_id: UUID | None = None
    tool_number: str | None = Field(default=None, min_length=1)
    quoted_revenue: Decimal | None = Field(default=None, ge=0)
    external_quote_number: str | None = None
    currency_code: str | None = None
    quoted_hours: Decimal | None = Field(default=None, ge=0)
    quoted_date: date | None = None
    create_project: bool = False


class FinanceDashboardRead(BaseModel):
    base_currency: str
    revenue: dict
    cost: dict
    profitability: dict
    budget: dict
    productivity: dict
    project_snapshots: list[dict]
    ai_placeholders: list[dict]
    upcoming_renewals: list[UpcomingRenewalRead] = Field(default_factory=list)
    team_commercial_fee_monthly_inr: Decimal = Decimal("0")
    pass_through_opex_inr: Decimal = Decimal("0")
    salary_cost_inr: Decimal = Decimal("0")
    selected_team_id: str | None = None
    selected_team_name: str | None = None
    planning_fy_start: date | None = None
    planning_fy_label: str | None = None
    by_team: list[TeamFinanceBreakdown] = Field(default_factory=list)
    overhead: dict = Field(default_factory=dict)


class AiForecastPlaceholderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: AiForecastKind
    title: str
    description: str | None = None
    is_active: bool


class FinanceReportRow(BaseModel):
    label: str
    amount: Decimal
    amount_inr: Decimal
    currency_code: str = "INR"


class KpiBreakdownLine(BaseModel):
    id: str
    label: str
    detail: str | None = None
    amount_inr: Decimal
    share_pct: Decimal = Decimal("0")
    band: str = "normal"
    kind: str = "expense"
    category_code: str | None = None


class KpiBreakdownGroup(BaseModel):
    label: str
    total_inr: Decimal
    lines: list[KpiBreakdownLine] = Field(default_factory=list)


class KpiBreakdownRead(BaseModel):
    metric: str
    title: str
    subtitle: str
    total_inr: Decimal
    currency_code: str = "INR"
    formula: str | None = None
    insights: list[str] = Field(default_factory=list)
    groups: list[KpiBreakdownGroup] = Field(default_factory=list)
    empty_hints: list[KpiBreakdownLine] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class CompanyFinanceSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    base_currency: str
    display_name: str
    is_active: bool


class FinancePlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    fiscal_year_start_year: int = Field(ge=2000, le=2100)
    fy_start_month: int = Field(default=4, ge=1, le=12)
    currency_code: str | None = None
    tax_percent: Decimal = Decimal("30")
    provision_percent: Decimal = Decimal("20")


class FinancePlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    tax_percent: Decimal | None = None
    provision_percent: Decimal | None = None
    status: FinancePlanStatus | None = None


class FinancePlanLineCreate(BaseModel):
    section: FinancePlanSection
    code: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)


class FinancePlanLineUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = None
    month_01: Decimal | None = None
    month_02: Decimal | None = None
    month_03: Decimal | None = None
    month_04: Decimal | None = None
    month_05: Decimal | None = None
    month_06: Decimal | None = None
    month_07: Decimal | None = None
    month_08: Decimal | None = None
    month_09: Decimal | None = None
    month_10: Decimal | None = None
    month_11: Decimal | None = None
    month_12: Decimal | None = None
    q1: Decimal | None = None
    q2: Decimal | None = None
    q3: Decimal | None = None
    q4: Decimal | None = None


class FinancePlanLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    section: FinancePlanSection
    code: str
    label: str
    sort_order: int
    is_total_row: bool
    month_01: Decimal
    month_02: Decimal
    month_03: Decimal
    month_04: Decimal
    month_05: Decimal
    month_06: Decimal
    month_07: Decimal
    month_08: Decimal
    month_09: Decimal
    month_10: Decimal
    month_11: Decimal
    month_12: Decimal
    q1: Decimal = Decimal("0")
    q2: Decimal = Decimal("0")
    q3: Decimal = Decimal("0")
    q4: Decimal = Decimal("0")
    notes: str | None = None


class FinancePlanSummary(BaseModel):
    month_labels: list[str]
    quarter_labels: list[str] = Field(default_factory=list)
    sales_by_month: dict[str, str]
    expenses_by_month: dict[str, str]
    gain_loss_by_month: dict[str, str]
    sales_by_quarter: dict[str, str] = Field(default_factory=dict)
    expenses_by_quarter: dict[str, str] = Field(default_factory=dict)
    gain_loss_by_quarter: dict[str, str] = Field(default_factory=dict)
    sales_fy: str
    expenses_fy: str
    gain_loss: str
    after_tax: str
    provision_amount: str
    gain_loss_after_provision: str
    tax_percent: str
    provision_percent: str


class FinancePlanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    fiscal_year_label: str
    fy_start_date: date
    fy_end_date: date
    currency_code: str
    tax_percent: Decimal
    provision_percent: Decimal
    status: FinancePlanStatus


class FinancePlanDetail(FinancePlanListItem):
    lines: list[FinancePlanLineRead]
    summary: FinancePlanSummary
    line_totals: dict[str, str] = Field(default_factory=dict)


class FinancePlanCloneRequest(BaseModel):
    scenario_name: str = Field(..., min_length=1, max_length=80)


class PlanVsActualRead(BaseModel):
    plan_id: UUID
    fiscal_year_label: str
    as_of: str
    months_elapsed: int
    months_remaining: int
    currency_code: str
    sales_monthly_run_rate: str
    expenses_monthly_run_rate: str
    plan_sales_ytd: str
    actual_sales_ytd: str
    sales_variance_ytd: str
    sales_variance_pct: str
    plan_expenses_ytd: str
    actual_expenses_ytd: str
    expenses_variance_ytd: str
    expenses_variance_pct: str
    plan_gain_loss_ytd: str
    actual_gain_loss_ytd: str
    gain_loss_variance_ytd: str
    plan_sales_fy: str
    plan_expenses_fy: str
    plan_gain_loss_fy: str
    rolling_forecast_sales_fy: str
    rolling_forecast_expenses_fy: str
    rolling_forecast_gain_loss_fy: str
    remaining_plan_sales: str
    remaining_plan_expenses: str
    methodology: str


class FinancePlanAiInsight(BaseModel):
    id: str
    severity: str
    title: str
    detail: str
    action_code: str | None = None
    action_label: str | None = None


class FinancePlanAiInsightsRead(BaseModel):
    plan_id: UUID
    fiscal_year_label: str
    engine: str
    disclaimer: str
    confidence_percent: int
    fill_ratio_percent: int
    months_elapsed: int
    insights: list[FinancePlanAiInsight]
    headline: str


class FinancePlanAiApplyRequest(BaseModel):
    action_code: str = Field(..., min_length=1, max_length=80)
