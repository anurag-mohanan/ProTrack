"""Awarded quotes → Annual Plan sales lines by quoted_date FY quarter."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import FinancePlanSection
from app.models.finance import FinancePlan, FinancePlanLine, Quote, QuoteRevision
from app.models.models import Customer
from app.services.finance.annual_plan_service import (
    QUARTER_FIELDS,
    apply_quarter_amount,
    get_plan,
)
from app.services.finance.renewal_budget_service import fy_quarter_index


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _line_code(quote_id: UUID) -> str:
    return f"awarded_{str(quote_id).replace('-', '')[:12]}"


def _current_revision(db: Session, quote: Quote) -> QuoteRevision | None:
    return db.scalar(
        select(QuoteRevision).where(
            QuoteRevision.quote_id == quote.id,
            QuoteRevision.version == quote.current_version,
            QuoteRevision.revision == quote.current_revision,
        )
    )


def effective_quoted_date(quote: Quote, revision: QuoteRevision | None) -> date | None:
    """Prefer explicit quoted_date; else revision document start_date. Never invent from fx_date."""
    if quote.quoted_date is not None:
        return quote.quoted_date
    if revision is not None and revision.start_date is not None:
        return revision.start_date
    return None


def sync_sales_from_awarded_quotes(
    db: Session,
    plan_id: UUID,
    *,
    team_id: UUID | None = None,
) -> tuple[FinancePlan, dict[str, int]]:
    """
    Upsert sales lines from active awarded quotes into the plan FY quarter
    matching each quote's quoted_date. Returns plan + sync counts.
    """
    plan = get_plan(db, plan_id)
    fy_start = plan.fy_start_date

    stmt = select(Quote).where(Quote.is_active.is_(True))
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)
    quotes = list(db.scalars(stmt).all())

    synced = 0
    skipped_no_date = 0
    skipped_outside_fy = 0
    zero_revenue = 0
    active_codes: set[str] = set()

    for quote in quotes:
        revision = _current_revision(db, quote)
        when = effective_quoted_date(quote, revision)
        if when is None:
            skipped_no_date += 1
            continue
        idx = fy_quarter_index(when, fy_start=fy_start)
        if idx is None:
            skipped_outside_fy += 1
            continue

        revenue = _q(revision.base_quoted_revenue_inr if revision else 0)
        if revenue <= 0:
            zero_revenue += 1
            continue

        code = _line_code(quote.id)
        active_codes.add(code)
        customer = db.get(Customer, quote.customer_id)
        customer_name = customer.name if customer else "Customer"
        quote_no = quote.external_quote_number or quote.tool_number
        label = f"Award: {customer_name} · {quote_no}"[:200]

        line = next(
            (
                row
                for row in plan.lines
                if row.section == FinancePlanSection.sales and row.code == code
            ),
            None,
        )
        if line is None:
            max_sort = max(
                (row.sort_order for row in plan.lines if row.section == FinancePlanSection.sales),
                default=100,
            )
            line = FinancePlanLine(
                plan_id=plan.id,
                section=FinancePlanSection.sales,
                code=code,
                label=label,
                sort_order=max_sort + 10,
                month_01=Decimal("0"),
                month_02=Decimal("0"),
                month_03=Decimal("0"),
                month_04=Decimal("0"),
                month_05=Decimal("0"),
                month_06=Decimal("0"),
                month_07=Decimal("0"),
                month_08=Decimal("0"),
                month_09=Decimal("0"),
                month_10=Decimal("0"),
                month_11=Decimal("0"),
                month_12=Decimal("0"),
            )
            db.add(line)
            plan.lines.append(line)
            db.flush()
        else:
            line.label = label

        for q in QUARTER_FIELDS:
            apply_quarter_amount(line, q, Decimal("0"))
        apply_quarter_amount(line, f"q{idx}", revenue)
        line.notes = (
            f"Auto from awarded quote {quote_no} · quoted {when.isoformat()} · "
            f"{quote.currency_code}"
        )
        synced += 1

    # Soft-removed awards: drop prior auto lines no longer in the active set.
    orphans = [
        row
        for row in list(plan.lines)
        if row.section == FinancePlanSection.sales
        and str(row.code).startswith("awarded_")
        and row.code not in active_codes
    ]
    for row in orphans:
        plan.lines.remove(row)
        db.delete(row)

    db.flush()
    return plan, {
        "synced": synced,
        "skipped_no_date": skipped_no_date,
        "skipped_outside_fy": skipped_outside_fy,
        "zero_revenue": zero_revenue,
        "removed_orphans": len(orphans),
    }
