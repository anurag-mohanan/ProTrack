"""Commercial quote vs invoice hours balance (partial invoice intelligence).

Compares Awarded Quote commercial hours (QuoteRevision.quoted_hours) against
cumulative invoice line quantity_hours — never work-breakdown / timesheet hours.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote, QuoteBalanceClosure, QuoteInvoiceLine, QuoteRevision
from app.models.models import User

_HOURS_TOLERANCE = Decimal("0.01")

HOURS_STATUS_NOT_INVOICED = "NOT_INVOICED"
HOURS_STATUS_PARTIALLY_INVOICED = "PARTIALLY_INVOICED"
HOURS_STATUS_FULLY_INVOICED = "FULLY_INVOICED"
HOURS_STATUS_OVER_INVOICED = "OVER_INVOICED"
HOURS_STATUS_BALANCE_CLOSED = "BALANCE_CLOSED"
HOURS_STATUS_UNKNOWN = "UNKNOWN"  # quoted hours not set


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def serialize_hours_balance(snapshot: dict | None) -> dict | None:
    """JSON-safe hours snapshot (Decimals → float) for API / extract payloads."""
    if not snapshot:
        return None

    def _ser(v):
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, dict):
            return {k: _ser(x) for k, x in v.items()}
        if isinstance(v, list):
            return [_ser(x) for x in v]
        return v

    return _ser(snapshot)


def _current_revision(db: Session, quote: Quote) -> QuoteRevision | None:
    return db.scalar(
        select(QuoteRevision)
        .where(QuoteRevision.quote_id == quote.id)
        .order_by(QuoteRevision.version.desc(), QuoteRevision.revision.desc())
        .limit(1)
    )


def list_active_balance_closures(db: Session, quote_id: UUID) -> list[QuoteBalanceClosure]:
    return list(
        db.scalars(
            select(QuoteBalanceClosure).where(
                QuoteBalanceClosure.quote_id == quote_id,
                QuoteBalanceClosure.is_active.is_(True),
            )
        ).all()
    )


def sum_closed_hours(db: Session, quote_id: UUID) -> Decimal:
    return sum((_d(row.closed_hours) for row in list_active_balance_closures(db, quote_id)), Decimal("0"))


def sum_closed_amount(db: Session, quote_id: UUID) -> Decimal:
    return sum((_d(row.closed_amount) for row in list_active_balance_closures(db, quote_id)), Decimal("0"))


def sum_invoiced_hours(invoice_lines: list[QuoteInvoiceLine]) -> Decimal:
    """Cumulative commercial hours from invoice lines (excludes cancelled via delete)."""
    total = Decimal("0")
    for line in invoice_lines:
        if line.quantity_hours is not None:
            total += _d(line.quantity_hours)
    return total


def derive_hours_status(
    *,
    quoted_hours: Decimal,
    invoiced_hours: Decimal,
    closed_hours: Decimal,
) -> str:
    quoted = _d(quoted_hours)
    invoiced = _d(invoiced_hours)
    closed = _d(closed_hours)
    if quoted <= 0:
        return HOURS_STATUS_UNKNOWN
    remaining_before_close = quoted - invoiced
    billable_remaining = max(Decimal("0"), remaining_before_close - closed)
    if invoiced > quoted + _HOURS_TOLERANCE:
        return HOURS_STATUS_OVER_INVOICED
    if closed > 0 and billable_remaining <= _HOURS_TOLERANCE and invoiced + _HOURS_TOLERANCE < quoted:
        return HOURS_STATUS_BALANCE_CLOSED
    if invoiced <= 0:
        return HOURS_STATUS_NOT_INVOICED
    if billable_remaining <= _HOURS_TOLERANCE:
        return HOURS_STATUS_FULLY_INVOICED
    return HOURS_STATUS_PARTIALLY_INVOICED


def calculate_quote_hours_balance(
    db: Session,
    quote: Quote,
    *,
    revision: QuoteRevision | None = None,
    invoice_lines: list[QuoteInvoiceLine] | None = None,
    this_invoice_hours: Decimal | None = None,
) -> dict:
    """Authoritative commercial hours snapshot for a quote (+ optional pending invoice)."""
    if revision is None:
        revision = _current_revision(db, quote)
    quoted_hours = _d(revision.quoted_hours) if revision else Decimal("0")
    quoted_amount = _d(revision.quoted_revenue) if revision else Decimal("0")
    lines = invoice_lines if invoice_lines is not None else list(quote.invoice_lines or [])
    previously_invoiced_hours = sum_invoiced_hours(lines)
    this_hours = _d(this_invoice_hours) if this_invoice_hours is not None else Decimal("0")
    cumulative = previously_invoiced_hours + this_hours
    closed_hours = sum_closed_hours(db, quote.id)
    closed_amount = sum_closed_amount(db, quote.id)

    remaining_before_close = max(Decimal("0"), quoted_hours - cumulative) if quoted_hours > 0 else Decimal("0")
    billable_remaining_hours = max(Decimal("0"), remaining_before_close - closed_hours)

    # Monetary remaining mirrors hours when rate is consistent; else use amount ledger.
    unit_rate = (
        (quoted_amount / quoted_hours).quantize(Decimal("0.01"))
        if quoted_hours > 0 and quoted_amount > 0
        else None
    )
    remaining_value_from_hours = (
        (billable_remaining_hours * unit_rate).quantize(Decimal("0.01"))
        if unit_rate is not None
        else None
    )

    hours_status = derive_hours_status(
        quoted_hours=quoted_hours,
        invoiced_hours=cumulative,
        closed_hours=closed_hours,
    )
    requires_balance_decision = (
        quoted_hours > 0
        and this_invoice_hours is not None
        and remaining_before_close > _HOURS_TOLERANCE
        and closed_hours <= 0
        and hours_status in {HOURS_STATUS_PARTIALLY_INVOICED, HOURS_STATUS_NOT_INVOICED}
        and cumulative > 0
        and cumulative + _HOURS_TOLERANCE < quoted_hours
    )
    over_hours = max(Decimal("0"), cumulative - quoted_hours) if quoted_hours > 0 else Decimal("0")

    return {
        "quoted_hours": quoted_hours,
        "previously_invoiced_hours": previously_invoiced_hours,
        "this_invoice_hours": this_hours if this_invoice_hours is not None else None,
        "invoiced_hours": cumulative,
        "closed_balance_hours": closed_hours,
        "closed_balance_amount": closed_amount,
        "remaining_hours": billable_remaining_hours,
        "remaining_hours_before_closure": remaining_before_close,
        "remaining_value": remaining_value_from_hours,
        "unit_rate": unit_rate,
        "hours_status": hours_status,
        "requires_balance_decision": requires_balance_decision,
        "is_partial_invoice": hours_status == HOURS_STATUS_PARTIALLY_INVOICED
        or (
            this_invoice_hours is not None
            and quoted_hours > 0
            and cumulative > 0
            and cumulative + _HOURS_TOLERANCE < quoted_hours
            and closed_hours <= 0
        ),
        "is_over_invoiced_hours": over_hours > _HOURS_TOLERANCE,
        "over_invoiced_hours": over_hours,
        "balance_already_closed": closed_hours > 0 and billable_remaining_hours <= _HOURS_TOLERANCE,
    }


def preview_partial_invoice_for_import(
    db: Session,
    *,
    quote_id: UUID,
    this_invoice_hours: Decimal | None,
) -> dict | None:
    """Preview hours balance for Invoice PDF import review (no writes)."""
    from app.services.finance.quote_cash_ledger_service import load_quote_with_ledger

    quote = load_quote_with_ledger(db, quote_id)
    if quote is None:
        return None
    balance = calculate_quote_hours_balance(
        db, quote, this_invoice_hours=this_invoice_hours
    )
    if balance["quoted_hours"] <= 0:
        return {
            **balance,
            "message": "Awarded quote has no commercial hours — hours-based partial check skipped.",
            "decision_required": False,
        }
    if balance["this_invoice_hours"] is None or balance["this_invoice_hours"] <= 0:
        return {
            **balance,
            "message": "This invoice has no commercial quantity/hours — hours-based partial check skipped.",
            "decision_required": False,
        }
    if balance["is_over_invoiced_hours"]:
        return {
            **balance,
            "message": (
                f"Invoice quantity exceeds quoted quantity by "
                f"{balance['over_invoiced_hours']} hours."
            ),
            "decision_required": False,
            "decision_options": [],
        }
    if balance["balance_already_closed"]:
        return {
            **balance,
            "message": "Remaining balance was already closed for this awarded quote.",
            "decision_required": False,
        }
    remaining = balance["remaining_hours_before_closure"]
    if remaining <= _HOURS_TOLERANCE:
        return {
            **balance,
            "message": "FULLY INVOICED — commercial hours match the awarded quote.",
            "decision_required": False,
        }
    return {
        **balance,
        "message": f"{remaining} hours remain to be invoiced. Do you want to keep this balance?",
        "decision_required": True,
        "decision_options": ["keep_balance", "close_remaining_balance"],
        "default_decision": "keep_balance",
    }


def close_remaining_balance(
    db: Session,
    *,
    quote: Quote,
    related_invoice_line: QuoteInvoiceLine | None,
    user: User | None,
    reason: str | None = None,
) -> QuoteBalanceClosure:
    """Persist explicit closure of remaining commercial hours/value. Does not alter quote."""
    from app.services.finance.quote_cash_ledger_service import list_invoice_lines

    invoice_lines = list_invoice_lines(db, quote.id)
    balance = calculate_quote_hours_balance(db, quote, invoice_lines=invoice_lines)
    remaining_hours = _d(balance["remaining_hours_before_closure"])
    if remaining_hours <= _HOURS_TOLERANCE:
        raise ProTrackValidationError("No remaining hours to close.")
    if balance["closed_balance_hours"] > 0 and balance["remaining_hours"] <= _HOURS_TOLERANCE:
        raise ProTrackValidationError("Remaining balance is already closed.")

    revision = _current_revision(db, quote)
    quoted_amount = _d(revision.quoted_revenue) if revision else Decimal("0")
    invoiced_amount = sum((_d(row.amount) for row in invoice_lines), Decimal("0"))
    remaining_amount = max(Decimal("0"), quoted_amount - invoiced_amount)
    # Prefer hours × rate when available
    if balance["unit_rate"] is not None:
        remaining_amount = (remaining_hours * balance["unit_rate"]).quantize(Decimal("0.01"))

    row = QuoteBalanceClosure(
        id=uuid4(),
        quote_id=quote.id,
        related_invoice_line_id=related_invoice_line.id if related_invoice_line else None,
        closed_hours=remaining_hours,
        closed_amount=remaining_amount,
        quoted_hours_snapshot=balance["quoted_hours"],
        invoiced_hours_snapshot=balance["invoiced_hours"],
        quoted_amount_snapshot=quoted_amount,
        invoiced_amount_snapshot=invoiced_amount,
        reason=(reason or "Closed remaining balance on invoice import").strip() or None,
        closed_by_id=user.id if user else None,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


__all__ = [
    "HOURS_STATUS_BALANCE_CLOSED",
    "HOURS_STATUS_FULLY_INVOICED",
    "HOURS_STATUS_NOT_INVOICED",
    "HOURS_STATUS_OVER_INVOICED",
    "HOURS_STATUS_PARTIALLY_INVOICED",
    "HOURS_STATUS_UNKNOWN",
    "calculate_quote_hours_balance",
    "close_remaining_balance",
    "derive_hours_status",
    "list_active_balance_closures",
    "preview_partial_invoice_for_import",
    "serialize_hours_balance",
    "sum_closed_amount",
    "sum_closed_hours",
    "sum_invoiced_hours",
]
