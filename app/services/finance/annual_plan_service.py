"""Annual finance plan service — Apr–Mar grids + P&L summary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import FinancePlanSection, FinancePlanStatus
from app.models.finance import FinancePlan, FinancePlanLine
from app.services.finance.fx_service import get_base_currency

MONTH_FIELDS = tuple(f"month_{i:02d}" for i in range(1, 13))
MONTH_LABELS = ("Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar")

SEED_SALES = [
    ("abc_mold", "ABC-mold", 10),
    ("abc_programming", "ABC-programming", 20),
    ("lanko_mold", "Lanko-mold", 30),
    ("sybridge", "Sybridge", 40),
]

SEED_EXPENSES = [
    ("capex_depreciation", "Capex depreciation", 10),
    ("wages", "Wages", 20),
    ("nx_mach_3", "NX Mach 3", 30),
    ("nx_mach_2", "NX Mach 2", 40),
    ("overhead", "Overhead", 50),
]


def fiscal_year_bounds(start_year: int, *, fy_start_month: int = 4) -> tuple[date, date, str]:
    """Return (fy_start, fy_end, label) for an FY starting in `fy_start_month` (default April)."""
    from calendar import monthrange

    if fy_start_month < 1 or fy_start_month > 12:
        raise ProTrackValidationError("fy_start_month must be 1–12")
    start = date(start_year, fy_start_month, 1)
    if fy_start_month == 1:
        end = date(start_year, 12, 31)
        label = str(start_year)
    else:
        end_year = start_year + 1
        end_month = fy_start_month - 1
        end = date(end_year, end_month, monthrange(end_year, end_month)[1])
        label = f"{start_year}-{str(end_year)[-2:]}"
    return start, end, label


def current_fy_start(today: date | None = None, *, fy_start_month: int = 4) -> date:
    """Most recent FY start (default 1 Apr) on or before today."""
    today = today or date.today()
    year = today.year if today.month >= fy_start_month else today.year - 1
    return date(year, fy_start_month, 1)


def current_fy_label(today: date | None = None, *, fy_start_month: int = 4) -> str:
    start = current_fy_start(today, fy_start_month=fy_start_month)
    _, _, label = fiscal_year_bounds(start.year, fy_start_month=fy_start_month)
    return f"FY {label}"


def _zero_months() -> dict[str, Decimal]:
    return {field: Decimal("0") for field in MONTH_FIELDS}


def _line_month_total(line: FinancePlanLine) -> Decimal:
    return sum((getattr(line, field) or Decimal("0")) for field in MONTH_FIELDS)


def _sum_section_months(lines: list[FinancePlanLine], section: FinancePlanSection) -> dict[str, Decimal]:
    totals = _zero_months()
    for line in lines:
        if line.section != section or line.is_total_row:
            continue
        for field in MONTH_FIELDS:
            totals[field] += getattr(line, field) or Decimal("0")
    return totals


def compute_plan_summary(plan: FinancePlan) -> dict:
    lines = list(plan.lines or [])
    sales = _sum_section_months(lines, FinancePlanSection.sales)
    expenses = _sum_section_months(lines, FinancePlanSection.expenses)
    gain_loss_months = {
        field: sales[field] - expenses[field] for field in MONTH_FIELDS
    }
    sales_fy = sum(sales.values())
    expenses_fy = sum(expenses.values())
    gain_loss_fy = sales_fy - expenses_fy
    tax = Decimal(str(plan.tax_percent or 0))
    provision = Decimal(str(plan.provision_percent or 0))
    after_tax = (gain_loss_fy * (Decimal("100") - tax) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    provision_amount = (after_tax * provision / Decimal("100")).quantize(Decimal("0.01"))
    after_provision = (after_tax - provision_amount).quantize(Decimal("0.01"))
    return {
        "month_labels": list(MONTH_LABELS),
        "sales_by_month": {k: str(v) for k, v in sales.items()},
        "expenses_by_month": {k: str(v) for k, v in expenses.items()},
        "gain_loss_by_month": {k: str(v) for k, v in gain_loss_months.items()},
        "sales_fy": str(sales_fy),
        "expenses_fy": str(expenses_fy),
        "gain_loss": str(gain_loss_fy),
        "after_tax": str(after_tax),
        "provision_amount": str(provision_amount),
        "gain_loss_after_provision": str(after_provision),
        "tax_percent": str(tax),
        "provision_percent": str(provision),
    }


def _seed_lines(plan: FinancePlan) -> None:
    for code, label, sort_order in SEED_SALES:
        plan.lines.append(
            FinancePlanLine(
                section=FinancePlanSection.sales,
                code=code,
                label=label,
                sort_order=sort_order,
                **_zero_months(),
            )
        )
    for code, label, sort_order in SEED_EXPENSES:
        plan.lines.append(
            FinancePlanLine(
                section=FinancePlanSection.expenses,
                code=code,
                label=label,
                sort_order=sort_order,
                **_zero_months(),
            )
        )


def list_plans(db: Session) -> list[FinancePlan]:
    return list(
        db.scalars(
            select(FinancePlan).order_by(FinancePlan.fy_start_date.desc(), FinancePlan.name)
        ).all()
    )


def get_plan(db: Session, plan_id: UUID) -> FinancePlan:
    plan = db.scalar(
        select(FinancePlan)
        .where(FinancePlan.id == plan_id)
        .options(selectinload(FinancePlan.lines))
    )
    if plan is None:
        raise ProTrackValidationError("Finance plan not found")
    return plan


def create_plan(
    db: Session,
    *,
    name: str,
    fiscal_year_start_year: int,
    fy_start_month: int = 4,
    currency_code: str | None = None,
    tax_percent: Decimal = Decimal("30"),
    provision_percent: Decimal = Decimal("20"),
) -> FinancePlan:
    fy_start, fy_end, label = fiscal_year_bounds(
        fiscal_year_start_year, fy_start_month=fy_start_month
    )
    currency = currency_code or get_base_currency(db)
    existing = db.scalar(
        select(FinancePlan).where(FinancePlan.fiscal_year_label == label)
    )
    if existing is not None:
        raise ProTrackValidationError(f"A plan for FY {label} already exists")
    plan = FinancePlan(
        name=name.strip() or f"FY {label}",
        fiscal_year_label=label,
        fy_start_date=fy_start,
        fy_end_date=fy_end,
        currency_code=currency,
        tax_percent=tax_percent,
        provision_percent=provision_percent,
        status=FinancePlanStatus.draft,
    )
    _seed_lines(plan)
    db.add(plan)
    db.flush()
    return plan


def update_plan(
    db: Session,
    plan_id: UUID,
    *,
    name: str | None = None,
    tax_percent: Decimal | None = None,
    provision_percent: Decimal | None = None,
    status: FinancePlanStatus | None = None,
) -> FinancePlan:
    plan = get_plan(db, plan_id)
    if name is not None:
        plan.name = name.strip() or plan.name
    if tax_percent is not None:
        plan.tax_percent = tax_percent
    if provision_percent is not None:
        plan.provision_percent = provision_percent
    if status is not None:
        plan.status = status
    db.flush()
    return plan


def add_line(
    db: Session,
    plan_id: UUID,
    *,
    section: FinancePlanSection,
    code: str,
    label: str,
) -> FinancePlanLine:
    if section not in {FinancePlanSection.sales, FinancePlanSection.expenses}:
        raise ProTrackValidationError("Only sales and expenses lines can be added in this release")
    plan = get_plan(db, plan_id)
    code_key = code.strip().lower().replace(" ", "_")
    if not code_key:
        raise ProTrackValidationError("Line code is required")
    dup = next(
        (row for row in plan.lines if row.section == section and row.code == code_key),
        None,
    )
    if dup is not None:
        raise ProTrackValidationError(f"Line code already exists: {code_key}")
    max_sort = max((row.sort_order for row in plan.lines if row.section == section), default=0)
    line = FinancePlanLine(
        plan_id=plan.id,
        section=section,
        code=code_key,
        label=label.strip() or code_key,
        sort_order=max_sort + 10,
        **_zero_months(),
    )
    db.add(line)
    db.flush()
    return line


def update_line(
    db: Session,
    plan_id: UUID,
    line_id: UUID,
    *,
    label: str | None = None,
    notes: str | None = None,
    months: dict[str, Decimal] | None = None,
) -> FinancePlanLine:
    plan = get_plan(db, plan_id)
    line = next((row for row in plan.lines if row.id == line_id), None)
    if line is None:
        raise ProTrackValidationError("Plan line not found")
    if line.is_total_row:
        raise ProTrackValidationError("Total rows are not editable")
    if label is not None:
        line.label = label.strip() or line.label
    if notes is not None:
        line.notes = notes
    if months:
        for field, value in months.items():
            if field not in MONTH_FIELDS:
                raise ProTrackValidationError(f"Invalid month field: {field}")
            setattr(line, field, Decimal(str(value)))
    db.flush()
    return line


def delete_line(db: Session, plan_id: UUID, line_id: UUID) -> None:
    plan = get_plan(db, plan_id)
    line = next((row for row in plan.lines if row.id == line_id), None)
    if line is None:
        raise ProTrackValidationError("Plan line not found")
    if line.is_total_row:
        raise ProTrackValidationError("Total rows cannot be deleted")
    db.delete(line)
    db.flush()


def plan_to_detail_dict(plan: FinancePlan) -> dict:
    lines = sorted(plan.lines, key=lambda row: (row.section.value, row.sort_order, row.label))
    return {
        "id": plan.id,
        "name": plan.name,
        "fiscal_year_label": plan.fiscal_year_label,
        "fy_start_date": plan.fy_start_date,
        "fy_end_date": plan.fy_end_date,
        "currency_code": plan.currency_code,
        "tax_percent": plan.tax_percent,
        "provision_percent": plan.provision_percent,
        "status": plan.status,
        "lines": lines,
        "summary": compute_plan_summary(plan),
        "line_totals": {
            str(line.id): str(_line_month_total(line)) for line in lines if not line.is_total_row
        },
    }
