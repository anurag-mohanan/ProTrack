"""Customer / project financial aggregation from the central quote status engine.

Single source of truth: calculate_awarded_quote_financial_status per quote,
then roll up to project and customer. No parallel masters.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Quote
from app.models.models import Customer, Project
from app.services.finance.payment_terms_service import (
    DEFAULT_DUE_SOON_DAYS,
    payment_timing_status,
)
from app.services.finance.quote_cash_ledger_service import (
    STATUS_OVER_INVOICED_REQUIRES_REVIEW,
    calculate_awarded_quote_financial_status,
)


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def is_quote_financially_closed(cash: dict) -> bool:
    """No billable remaining, no outstanding, no unresolved over-invoice exception."""
    if cash.get("financial_status") == STATUS_OVER_INVOICED_REQUIRES_REVIEW:
        return False
    if cash.get("is_over_invoiced"):
        return False
    remaining = _d(cash.get("remaining_to_invoice"))
    outstanding = _d(cash.get("outstanding_amount", cash.get("balance_due")))
    invoiced = _d(cash.get("invoiced_amount", cash.get("total_invoiced")))
    # Never closed if nothing was ever awarded and nothing invoiced — treat as inactive/not closed
    awarded = _d(cash.get("awarded_amount", cash.get("quoted_revenue")))
    if awarded <= 0 and invoiced <= 0:
        return False
    return remaining <= Decimal("0.01") and outstanding <= Decimal("0.01")


def allocate_invoice_outstanding(
    invoice_lines: list,
    total_paid: Decimal,
) -> list[dict]:
    """FIFO allocate quote-level payments onto invoice lines for aging."""
    remaining_paid = _d(total_paid)
    rows: list[dict] = []
    ordered = sorted(
        invoice_lines,
        key=lambda line: (line.line_date or date.min, line.sort_order or 0),
    )
    for line in ordered:
        amount = _d(line.amount)
        applied = min(amount, remaining_paid)
        remaining_paid -= applied
        outstanding = max(Decimal("0.00"), amount - applied)
        rows.append(
            {
                "invoice_line": line,
                "invoice_amount": amount,
                "paid_amount": applied,
                "outstanding": outstanding,
            }
        )
    return rows


def enrich_quote_financial_snapshot(cash: dict) -> dict:
    """Add is_financially_closed to a quote status snapshot."""
    closed = is_quote_financially_closed(cash)
    return {
        **cash,
        "is_financially_closed": closed,
        "finance_lifecycle": "closed" if closed else "active",
    }


def list_quote_financial_snapshots(
    db: Session,
    *,
    team_id: UUID | None = None,
    customer_id: UUID | None = None,
    project_id: UUID | None = None,
) -> list[dict]:
    stmt = (
        select(Quote)
        .where(Quote.is_active.is_(True))
        .options(
            selectinload(Quote.invoice_lines),
            selectinload(Quote.payment_lines),
        )
    )
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)
    if customer_id is not None:
        stmt = stmt.where(Quote.customer_id == customer_id)
    if project_id is not None:
        stmt = stmt.where(Quote.project_id == project_id)

    out: list[dict] = []
    for quote in db.scalars(stmt).all():
        cash = enrich_quote_financial_snapshot(
            calculate_awarded_quote_financial_status(db, quote)
        )
        out.append(
            {
                "quote_id": quote.id,
                "project_id": quote.project_id,
                "customer_id": quote.customer_id,
                "tool_number": quote.tool_number,
                "external_quote_number": quote.external_quote_number,
                "currency_code": quote.currency_code,
                **{k: cash[k] for k in cash if k not in {"invoice_lines", "payment_lines", "hours"}},
                "invoice_lines": cash.get("invoice_lines") or [],
                "payment_lines": cash.get("payment_lines") or [],
                "hours": cash.get("hours") or {},
            }
        )
    return out


def aggregate_customer_financial_summary(
    db: Session,
    *,
    customer_id: UUID,
    team_id: UUID | None = None,
    today: date | None = None,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
    lifecycle: str | None = None,  # active | closed | None
) -> dict:
    """Authoritative customer roll-up from quote financial status + invoice aging."""
    today = today or date.today()
    customer = db.get(Customer, customer_id)
    if customer is None:
        return {"customer_id": str(customer_id), "error": "Customer not found"}

    snapshots = list_quote_financial_snapshots(
        db, team_id=team_id, customer_id=customer_id
    )
    if lifecycle in {"active", "closed"}:
        want_closed = lifecycle == "closed"
        snapshots = [s for s in snapshots if bool(s.get("is_financially_closed")) == want_closed]

    awarded = sum((_d(s.get("awarded_amount")) for s in snapshots), Decimal("0.00"))
    invoiced = sum((_d(s.get("invoiced_amount")) for s in snapshots), Decimal("0.00"))
    to_invoice = sum((_d(s.get("remaining_to_invoice")) for s in snapshots), Decimal("0.00"))
    collected = sum((_d(s.get("paid_amount")) for s in snapshots), Decimal("0.00"))
    outstanding = sum((_d(s.get("outstanding_amount")) for s in snapshots), Decimal("0.00"))
    closed_waived = sum((_d(s.get("closed_balance_amount")) for s in snapshots), Decimal("0.00"))

    # Project counts (unique project_ids; quotes without project count as separate keys)
    project_ids = {s.get("project_id") for s in snapshots if s.get("project_id")}
    active_projects = {
        s.get("project_id")
        for s in snapshots
        if s.get("project_id") and not s.get("is_financially_closed")
    }
    # Project is closed only when ALL its quotes are closed
    project_closed: set[UUID] = set()
    for pid in project_ids:
        quotes_for = [s for s in snapshots if s.get("project_id") == pid]
        if quotes_for and all(s.get("is_financially_closed") for s in quotes_for):
            project_closed.add(pid)
    active_projects = project_ids - project_closed

    status_breakdown: dict[str, dict] = {}
    for s in snapshots:
        key = str(s.get("financial_status") or "unknown")
        bucket = status_breakdown.setdefault(
            key, {"count": 0, "awarded": Decimal("0.00"), "outstanding": Decimal("0.00")}
        )
        bucket["count"] += 1
        bucket["awarded"] += _d(s.get("awarded_amount"))
        bucket["outstanding"] += _d(s.get("outstanding_amount"))

    # Receivable aging from invoice lines (FIFO paid)
    aging = {
        "not_yet_due": Decimal("0.00"),
        "due_soon": Decimal("0.00"),
        "due_today": Decimal("0.00"),
        "overdue": Decimal("0.00"),
        "1_30_overdue": Decimal("0.00"),
        "31_60_overdue": Decimal("0.00"),
        "61_90_overdue": Decimal("0.00"),
        "90_plus_overdue": Decimal("0.00"),
        "aging_unavailable": Decimal("0.00"),
        "paid": Decimal("0.00"),
    }
    terms_counts: dict[str, int] = {}
    invoice_rows: list[dict] = []

    for s in snapshots:
        allocations = allocate_invoice_outstanding(
            list(s.get("invoice_lines") or []), _d(s.get("paid_amount"))
        )
        for alloc in allocations:
            line = alloc["invoice_line"]
            ostand = alloc["outstanding"]
            terms_label = getattr(line, "payment_terms", None) or "Unknown"
            terms_counts[terms_label] = terms_counts.get(terms_label, 0) + 1
            timing = payment_timing_status(
                due_date=getattr(line, "due_date", None),
                outstanding=ostand,
                invoiced=alloc["invoice_amount"],
                paid=alloc["paid_amount"],
                today=today,
                due_soon_days=due_soon_days,
            )
            bucket = timing["aging_bucket"]
            if bucket in aging:
                aging[bucket] += ostand
            if ostand > 0:
                if timing["payment_timing_status"] == "OVERDUE":
                    aging["overdue"] += ostand
                elif timing["payment_timing_status"] == "DUE_SOON":
                    aging["due_soon"] += ostand
                elif timing["payment_timing_status"] == "DUE_TODAY":
                    aging["due_today"] += ostand
                elif timing["payment_timing_status"] == "NOT_YET_DUE":
                    aging["not_yet_due"] += ostand
            invoice_rows.append(
                {
                    "invoice_line_id": str(line.id),
                    "quote_id": str(s["quote_id"]),
                    "project_id": str(s["project_id"]) if s.get("project_id") else None,
                    "tool_number": s.get("tool_number"),
                    "invoice_number": getattr(line, "invoice_number", None),
                    "invoice_date": line.line_date.isoformat() if line.line_date else None,
                    "due_date": line.due_date.isoformat() if getattr(line, "due_date", None) else None,
                    "payment_terms": getattr(line, "payment_terms", None),
                    "payment_terms_days": getattr(line, "payment_terms_days", None),
                    "payment_terms_source": getattr(line, "payment_terms_source", None),
                    "invoice_amount": alloc["invoice_amount"],
                    "paid_amount": alloc["paid_amount"],
                    "outstanding": ostand,
                    **timing,
                }
            )

    to_be_invoiced_projects = {
        s.get("project_id")
        for s in snapshots
        if s.get("project_id") and _d(s.get("remaining_to_invoice")) > Decimal("0.01")
    }
    payment_pending_projects = {
        s.get("project_id")
        for s in snapshots
        if s.get("project_id") and _d(s.get("outstanding_amount")) > Decimal("0.01")
    }

    quotes_out = []
    for s in snapshots:
        project = db.get(Project, s["project_id"]) if s.get("project_id") else None
        quotes_out.append(
            {
                "quote_id": str(s["quote_id"]),
                "project_id": str(s["project_id"]) if s.get("project_id") else None,
                "project_name": project.name if project else None,
                "tool_number": s.get("tool_number"),
                "external_quote_number": s.get("external_quote_number"),
                "awarded": _d(s.get("awarded_amount")),
                "invoiced": _d(s.get("invoiced_amount")),
                "to_invoice": _d(s.get("remaining_to_invoice")),
                "paid": _d(s.get("paid_amount")),
                "outstanding": _d(s.get("outstanding_amount")),
                "invoice_percentage": s.get("invoice_percentage"),
                "collection_percentage": s.get("collection_percentage"),
                "financial_status": s.get("financial_status"),
                "hours_status": s.get("hours_status"),
                "quoted_hours": s.get("quoted_hours"),
                "invoiced_hours": s.get("invoiced_hours"),
                "remaining_hours": s.get("remaining_hours"),
                "closed_balance_hours": s.get("closed_balance_hours"),
                "is_financially_closed": s.get("is_financially_closed"),
            }
        )

    return {
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "customer_code": customer.code,
        "default_payment_terms": getattr(customer, "default_payment_terms", None),
        "default_payment_terms_days": getattr(customer, "default_payment_terms_days", None),
        "as_of": today.isoformat(),
        "lifecycle_filter": lifecycle,
        "totals": {
            "awarded": awarded,
            "invoiced": invoiced,
            "to_be_invoiced": to_invoice,
            "collected": collected,
            "outstanding": outstanding,
            "closed_waived": closed_waived,
        },
        "projects": {
            "active": len(active_projects),
            "financially_closed": len(project_closed),
            "to_be_invoiced": len(to_be_invoiced_projects),
            "payment_pending": len(payment_pending_projects),
        },
        "status_breakdown": {
            k: {
                "count": v["count"],
                "awarded": v["awarded"],
                "outstanding": v["outstanding"],
            }
            for k, v in status_breakdown.items()
        },
        "receivables": aging,
        "payment_terms_summary": [
            {"payment_terms": k, "invoice_count": v}
            for k, v in sorted(terms_counts.items(), key=lambda x: (-x[1], x[0]))
        ],
        "quotes": quotes_out,
        "invoices": invoice_rows,
    }


def project_financial_summary(
    db: Session,
    *,
    project_id: UUID,
    team_id: UUID | None = None,
) -> dict:
    """Aggregate all awarded quotes on a project — active until every quote is closed."""
    project = db.get(Project, project_id)
    snapshots = list_quote_financial_snapshots(
        db, team_id=team_id, project_id=project_id
    )
    closed = bool(snapshots) and all(s.get("is_financially_closed") for s in snapshots)
    return {
        "project_id": str(project_id),
        "project_name": project.name if project else None,
        "customer_id": str(project.customer_id) if project else None,
        "is_financially_closed": closed,
        "finance_lifecycle": "closed" if closed else "active",
        "quote_count": len(snapshots),
        "awarded": sum((_d(s.get("awarded_amount")) for s in snapshots), Decimal("0.00")),
        "invoiced": sum((_d(s.get("invoiced_amount")) for s in snapshots), Decimal("0.00")),
        "to_be_invoiced": sum(
            (_d(s.get("remaining_to_invoice")) for s in snapshots), Decimal("0.00")
        ),
        "collected": sum((_d(s.get("paid_amount")) for s in snapshots), Decimal("0.00")),
        "outstanding": sum(
            (_d(s.get("outstanding_amount")) for s in snapshots), Decimal("0.00")
        ),
        "quotes": [
            {
                "quote_id": str(s["quote_id"]),
                "financial_status": s.get("financial_status"),
                "is_financially_closed": s.get("is_financially_closed"),
                "awarded": _d(s.get("awarded_amount")),
                "outstanding": _d(s.get("outstanding_amount")),
                "remaining_to_invoice": _d(s.get("remaining_to_invoice")),
            }
            for s in snapshots
        ],
    }


__all__ = [
    "aggregate_customer_financial_summary",
    "allocate_invoice_outstanding",
    "enrich_quote_financial_snapshot",
    "is_quote_financially_closed",
    "list_quote_financial_snapshots",
    "project_financial_summary",
]
