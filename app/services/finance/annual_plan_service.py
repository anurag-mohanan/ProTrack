"""Annual finance plan service — Apr–Mar FY with quarterly edit surface + P&L summary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import FinancePlanSection, FinancePlanStatus
from app.models.finance import FinancePlan, FinancePlanLine
from app.services.finance.fx_service import get_base_currency

MONTH_FIELDS = tuple(f"month_{i:02d}" for i in range(1, 13))
MONTH_LABELS = ("Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar")
QUARTER_FIELDS = ("q1", "q2", "q3", "q4")
QUARTER_LABELS = ("Q1 Apr–Jun", "Q2 Jul–Sep", "Q3 Oct–Dec", "Q4 Jan–Mar")
QUARTER_MONTHS: dict[str, tuple[str, str, str]] = {
    "q1": ("month_01", "month_02", "month_03"),
    "q2": ("month_04", "month_05", "month_06"),
    "q3": ("month_07", "month_08", "month_09"),
    "q4": ("month_10", "month_11", "month_12"),
}

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


def _quantize_money(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def line_quarter_totals(line: FinancePlanLine) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for q, months in QUARTER_MONTHS.items():
        out[q] = sum((getattr(line, field) or Decimal("0")) for field in months)
    return out


def apply_quarter_amount(line: FinancePlanLine, quarter: str, total: Decimal) -> None:
    """Write a quarter total by even split across the three FY month cells."""
    if quarter not in QUARTER_MONTHS:
        raise ProTrackValidationError(f"Invalid quarter field: {quarter}")
    total = _quantize_money(total)
    months = QUARTER_MONTHS[quarter]
    third = _quantize_money(total / Decimal("3"))
    setattr(line, months[0], third)
    setattr(line, months[1], third)
    setattr(line, months[2], _quantize_money(total - third - third))


def _sum_section_months(lines: list[FinancePlanLine], section: FinancePlanSection) -> dict[str, Decimal]:
    totals = _zero_months()
    for line in lines:
        if line.section != section or line.is_total_row:
            continue
        for field in MONTH_FIELDS:
            totals[field] += getattr(line, field) or Decimal("0")
    return totals


def _quarters_from_months(month_totals: dict[str, Decimal]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for q, months in QUARTER_MONTHS.items():
        out[q] = sum(month_totals[m] for m in months)
    return out


def compute_plan_summary(plan: FinancePlan) -> dict:
    lines = list(plan.lines or [])
    sales = _sum_section_months(lines, FinancePlanSection.sales)
    expenses = _sum_section_months(lines, FinancePlanSection.expenses)
    gain_loss_months = {
        field: sales[field] - expenses[field] for field in MONTH_FIELDS
    }
    sales_q = _quarters_from_months(sales)
    expenses_q = _quarters_from_months(expenses)
    gain_loss_q = {q: sales_q[q] - expenses_q[q] for q in QUARTER_FIELDS}
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
        "quarter_labels": list(QUARTER_LABELS),
        "sales_by_month": {k: str(v) for k, v in sales.items()},
        "expenses_by_month": {k: str(v) for k, v in expenses.items()},
        "gain_loss_by_month": {k: str(v) for k, v in gain_loss_months.items()},
        "sales_by_quarter": {k: str(v) for k, v in sales_q.items()},
        "expenses_by_quarter": {k: str(v) for k, v in expenses_q.items()},
        "gain_loss_by_quarter": {k: str(v) for k, v in gain_loss_q.items()},
        "sales_fy": str(sales_fy),
        "expenses_fy": str(expenses_fy),
        "gain_loss": str(gain_loss_fy),
        "after_tax": str(after_tax),
        "provision_amount": str(provision_amount),
        "gain_loss_after_provision": str(after_provision),
        "tax_percent": str(tax),
        "provision_percent": str(provision),
    }


def line_to_read_dict(line: FinancePlanLine) -> dict:
    quarters = line_quarter_totals(line)
    payload = {
        "id": line.id,
        "plan_id": line.plan_id,
        "section": line.section,
        "code": line.code,
        "label": line.label,
        "sort_order": line.sort_order,
        "is_total_row": line.is_total_row,
        "notes": line.notes,
        **{field: getattr(line, field) or Decimal("0") for field in MONTH_FIELDS},
        **quarters,
    }
    return payload


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
    plan_name = name.strip() or f"FY {label}"
    existing = db.scalar(
        select(FinancePlan).where(
            FinancePlan.fiscal_year_label == label,
            FinancePlan.name == plan_name,
        )
    )
    if existing is not None:
        raise ProTrackValidationError(
            f"A plan named '{plan_name}' for FY {label} already exists"
        )
    plan = FinancePlan(
        name=plan_name,
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


def clone_plan(
    db: Session,
    plan_id: UUID,
    *,
    scenario_name: str,
) -> FinancePlan:
    """Clone a plan under the same FY as a named scenario (Base / Stretch / Downside)."""
    source = get_plan(db, plan_id)
    label = (scenario_name or "").strip() or "Scenario"
    new_name = f"{source.name} — {label}"
    dup = db.scalar(
        select(FinancePlan).where(
            FinancePlan.fiscal_year_label == source.fiscal_year_label,
            FinancePlan.name == new_name,
        )
    )
    if dup is not None:
        raise ProTrackValidationError(f"Scenario already exists: {new_name}")
    plan = FinancePlan(
        name=new_name,
        fiscal_year_label=source.fiscal_year_label,
        fy_start_date=source.fy_start_date,
        fy_end_date=source.fy_end_date,
        currency_code=source.currency_code,
        tax_percent=source.tax_percent,
        provision_percent=source.provision_percent,
        status=FinancePlanStatus.draft,
    )
    for row in sorted(source.lines, key=lambda item: (item.section.value, item.sort_order)):
        months = {field: getattr(row, field) or Decimal("0") for field in MONTH_FIELDS}
        plan.lines.append(
            FinancePlanLine(
                section=row.section,
                code=row.code,
                label=row.label,
                sort_order=row.sort_order,
                is_total_row=row.is_total_row,
                notes=row.notes,
                **months,
            )
        )
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
    quarters: dict[str, Decimal] | None = None,
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
    if quarters:
        for field, value in quarters.items():
            apply_quarter_amount(line, field, Decimal(str(value)))
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
        "lines": [line_to_read_dict(line) for line in lines],
        "summary": compute_plan_summary(plan),
        "line_totals": {
            str(line.id): str(_line_month_total(line)) for line in lines if not line.is_total_row
        },
    }
