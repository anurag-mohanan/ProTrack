"""Financial Planning domain models (EBMP Module 2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
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
from app.models.mixins import TimestampMixin


class Currency(Base, TimestampMixin):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(8))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_base: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FxRate(Base, TimestampMixin):
    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint(
            "from_currency",
            "to_currency",
            "effective_date",
            name="uq_fx_rates_pair_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    to_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")


class CompanyFinanceSettings(Base, TimestampMixin):
    __tablename__ = "company_finance_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    base_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Default")
    # India corporate income tax rate for Overview / Team P&L after-tax net (Annual Plan has its own %).
    corporate_tax_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("30")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CostCentre(Base, TimestampMixin):
    __tablename__ = "cost_centres"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    nature: Mapped[CostNature] = mapped_column(
        Enum(CostNature, name="cost_nature", native_enum=False),
        nullable=False,
        default=CostNature.opex,
    )
    default_frequency: Mapped[CostFrequency] = mapped_column(
        Enum(CostFrequency, name="cost_frequency", native_enum=False),
        nullable=False,
        default=CostFrequency.monthly,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EmployeeCostProfile(Base, TimestampMixin):
    __tablename__ = "employee_cost_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    monthly_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    hourly_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    contractor_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    base_monthly_salary_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    base_hourly_cost_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cost_centre_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cost_centres.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    nature: Mapped[CostNature] = mapped_column(
        Enum(CostNature, name="expense_cost_nature", native_enum=False),
        nullable=False,
        default=CostNature.opex,
    )
    frequency: Mapped[CostFrequency] = mapped_column(
        Enum(CostFrequency, name="expense_cost_frequency", native_enum=False),
        nullable=False,
        default=CostFrequency.monthly,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    base_amount_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    fx_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_by: Mapped[ExpensePaidBy] = mapped_column(
        Enum(ExpensePaidBy, name="expense_paid_by", native_enum=False),
        nullable=False,
        default=ExpensePaidBy.prosohm,
    )
    vendor_name: Mapped[Optional[str]] = mapped_column(String(200))
    next_renewal_date: Mapped[Optional[date]] = mapped_column(Date)
    notify_before_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    notify_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    renewal_notified_for: Mapped[Optional[date]] = mapped_column(Date)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TeamCommercialTerms(Base, TimestampMixin):
    """Per-team engagement model and customer fee used by finance rollups."""

    __tablename__ = "team_commercial_terms"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=False, index=True
    )
    working_model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_models.id"), nullable=False
    )
    billing_mode: Mapped[TeamBillingMode] = mapped_column(
        Enum(TeamBillingMode, name="team_billing_mode", native_enum=False),
        nullable=False,
        default=TeamBillingMode.project_based,
    )
    customer_fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    base_fee_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    billing_period: Mapped[TeamBillingPeriod] = mapped_column(
        Enum(TeamBillingPeriod, name="team_billing_period", native_enum=False),
        nullable=False,
        default=TeamBillingPeriod.monthly,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    customer_pays_software: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    customer_pays_hardware: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    fee_bands: Mapped[list["TeamCommercialFeeBand"]] = relationship(
        "TeamCommercialFeeBand",
        back_populates="terms",
        cascade="all, delete-orphan",
    )


class TeamCommercialFeeBand(Base, TimestampMixin):
    """Per-skill customer fee for fixed-cost / retainer headcount on a terms row."""

    __tablename__ = "team_commercial_fee_bands"
    __table_args__ = (
        UniqueConstraint("terms_id", "skill_level", name="uq_team_commercial_fee_band_skill"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    terms_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("team_commercial_terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_level: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    base_fee_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    terms: Mapped["TeamCommercialTerms"] = relationship(
        "TeamCommercialTerms", back_populates="fee_bands"
    )


class Quote(Base, TimestampMixin):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.id"), nullable=True, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    tool_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_quote_number: Mapped[Optional[str]] = mapped_column(String(100))
    business_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_models.id"), nullable=True
    )
    estimator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    quoted_date: Mapped[Optional[date]] = mapped_column(Date)
    invoiced_date: Mapped[Optional[date]] = mapped_column(Date)
    is_invoiced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_invoicing_reminder_at: Mapped[Optional[date]] = mapped_column(Date)
    customer_po_number: Mapped[Optional[str]] = mapped_column(String(100))
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    last_payment_reminder_at: Mapped[Optional[date]] = mapped_column(Date)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_revision: Mapped[str] = mapped_column(String(20), nullable=False, default="A")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    revisions: Mapped[list["QuoteRevision"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )
    invoice_lines: Mapped[list["QuoteInvoiceLine"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteInvoiceLine.sort_order, QuoteInvoiceLine.line_date",
    )
    payment_lines: Mapped[list["QuotePaymentLine"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuotePaymentLine.sort_order, QuotePaymentLine.line_date",
    )


class QuoteInvoiceLine(Base, TimestampMixin):
    """Partial or full invoice entry against an awarded quote."""

    __tablename__ = "quote_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quotes.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    quote: Mapped[Quote] = relationship(back_populates="invoice_lines")


class QuotePaymentLine(Base, TimestampMixin):
    """Partial or full customer payment against invoiced amounts."""

    __tablename__ = "quote_payment_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quotes.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    quote: Mapped[Quote] = relationship(back_populates="payment_lines")


class QuoteRevision(Base, TimestampMixin):
    __tablename__ = "quote_revisions"
    __table_args__ = (
        UniqueConstraint("quote_id", "version", "revision", name="uq_quote_version_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quotes.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[str] = mapped_column(String(20), nullable=False)
    quoted_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    quoted_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    margin: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    base_estimated_cost_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    base_quoted_revenue_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    fx_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    imported_from: Mapped[Optional[str]] = mapped_column(String(20))
    imported_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    imported_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    quote: Mapped[Quote] = relationship(back_populates="revisions")


class Budget(Base, TimestampMixin):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope_type: Mapped[BudgetScopeType] = mapped_column(
        Enum(BudgetScopeType, name="budget_scope_type", native_enum=False),
        nullable=False,
    )
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    allocated: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    approved_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    spent: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    forecast: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    remaining: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    variance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    base_allocated_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    base_spent_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=1)
    q1_allocated: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    q2_allocated: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    q3_allocated: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    q4_allocated: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    q1_forecast: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    q2_forecast: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    q3_forecast: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    q4_forecast: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    fiscal_year: Mapped[Optional[int]] = mapped_column(Integer)
    approval_status: Mapped[BudgetApprovalStatus] = mapped_column(
        Enum(BudgetApprovalStatus, name="budget_approval_status", native_enum=False),
        nullable=False,
        default=BudgetApprovalStatus.draft,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProjectFinancialSnapshot(Base, TimestampMixin):
    __tablename__ = "project_financial_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, unique=True
    )
    quote_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quotes.id"), nullable=True
    )
    quoted_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    quoted_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    net_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    recovery_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    profitability_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=0
    )
    engineering_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    overhead_allocation: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    base_revenue_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    base_gross_profit_inr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    business_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("working_models.id"), nullable=True
    )


class AiForecastPlaceholder(Base, TimestampMixin):
    __tablename__ = "ai_forecast_placeholders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[AiForecastKind] = mapped_column(
        Enum(AiForecastKind, name="ai_forecast_kind", native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    payload_json: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FinancePlan(Base, TimestampMixin):
    """Annual financial plan (Apr–Mar FY) aligned to the legacy Excel workbook."""

    __tablename__ = "finance_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    fiscal_year_label: Mapped[str] = mapped_column(String(20), nullable=False)
    fy_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    fy_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False, default="INR"
    )
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=30)
    provision_percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=20)
    status: Mapped[FinancePlanStatus] = mapped_column(
        Enum(FinancePlanStatus, name="finance_plan_status", native_enum=False),
        nullable=False,
        default=FinancePlanStatus.draft,
    )

    lines: Mapped[list["FinancePlanLine"]] = relationship(
        "FinancePlanLine",
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class FinancePlanLine(Base, TimestampMixin):
    """One editable row in an annual plan section (month_01=Apr … month_12=Mar)."""

    __tablename__ = "finance_plan_lines"
    __table_args__ = (
        UniqueConstraint("plan_id", "section", "code", name="uq_finance_plan_lines_plan_section_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("finance_plans.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[FinancePlanSection] = mapped_column(
        Enum(FinancePlanSection, name="finance_plan_section", native_enum=False),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_total_row: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    month_01: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_02: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_03: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_04: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_05: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_06: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_07: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_08: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_09: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_10: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_11: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    month_12: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    plan: Mapped[FinancePlan] = relationship("FinancePlan", back_populates="lines")
