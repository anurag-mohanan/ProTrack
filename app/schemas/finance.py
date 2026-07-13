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
    start_date: date | None = None
    end_date: date | None = None
    is_recurring: bool = False
    team_id: UUID | None = None
    project_id: UUID | None = None


class ExpenseRead(ExpenseCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    base_amount_inr: Decimal
    fx_rate: Decimal
    fx_date: date
    is_active: bool


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


class BudgetCreate(BaseModel):
    name: str
    scope_type: BudgetScopeType
    scope_id: UUID | None = None
    currency_code: str = "INR"
    allocated: Decimal = Decimal("0")
    approved_amount: Decimal = Decimal("0")
    spent: Decimal = Decimal("0")
    forecast: Decimal = Decimal("0")
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
    project_id: UUID | None = None
    tool_number: str
    business_model_id: UUID | None = None
    estimator_id: UUID | None = None
    currency_code: str
    current_version: int
    current_revision: str
    is_active: bool
    revisions: list[QuoteRevisionRead] = Field(default_factory=list)


class QuoteImportResult(BaseModel):
    imported_count: int
    quote_ids: list[UUID]


class FinanceDashboardRead(BaseModel):
    base_currency: str
    revenue: dict
    cost: dict
    profitability: dict
    budget: dict
    productivity: dict
    project_snapshots: list[dict]
    ai_placeholders: list[dict]


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


class CompanyFinanceSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    base_currency: str
    display_name: str
    is_active: bool
