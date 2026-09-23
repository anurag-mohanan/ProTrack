"""Quote cash ledger — partial invoices and payments with running balance."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote, QuoteInvoiceLine, QuotePaymentLine, QuoteRevision

_TOLERANCE = Decimal("1.01")
_AMOUNT_TOLERANCE = Decimal("0.01")

# Lifecycle statuses derived from awarded + invoices + payments (never manual).
STATUS_NOT_INVOICED = "not_invoiced"
STATUS_PARTIALLY_INVOICED_PAID = "partially_invoiced_paid"
STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING = "partially_invoiced_payment_pending"
STATUS_FULLY_INVOICED_PAYMENT_PENDING = "fully_invoiced_payment_pending"
STATUS_FULLY_INVOICED_FULLY_PAID = "fully_invoiced_fully_paid"
STATUS_OVER_INVOICED_REQUIRES_REVIEW = "over_invoiced_requires_review"

AWARDED_FINANCIAL_STATUSES = (
    STATUS_NOT_INVOICED,
    STATUS_PARTIALLY_INVOICED_PAID,
    STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING,
    STATUS_FULLY_INVOICED_PAYMENT_PENDING,
    STATUS_FULLY_INVOICED_FULLY_PAID,
    STATUS_OVER_INVOICED_REQUIRES_REVIEW,
)


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

def _current_revision(db: Session, quote: Quote) -> QuoteRevision | None:
    current = db.scalar(
        select(QuoteRevision).where(
            QuoteRevision.quote_id == quote.id,
            QuoteRevision.version == quote.current_version,
            QuoteRevision.revision == quote.current_revision,
        )
    )
    if current is not None:
        return current
    return db.scalar(
        select(QuoteRevision)
        .where(QuoteRevision.quote_id == quote.id)
        .order_by(QuoteRevision.version.desc())
        .limit(1)
    )


def load_quote_with_ledger(db: Session, quote_id: UUID) -> Quote | None:
    return db.scalar(
        select(Quote)
        .where(Quote.id == quote_id)
        .options(
            selectinload(Quote.invoice_lines),
            selectinload(Quote.payment_lines),
        )
    )


def list_invoice_lines(db: Session, quote_id: UUID) -> list[QuoteInvoiceLine]:
    return list(
        db.scalars(
            select(QuoteInvoiceLine)
            .where(QuoteInvoiceLine.quote_id == quote_id)
            .order_by(QuoteInvoiceLine.sort_order, QuoteInvoiceLine.line_date)
        ).all()
    )


def list_payment_lines(db: Session, quote_id: UUID) -> list[QuotePaymentLine]:
    return list(
        db.scalars(
            select(QuotePaymentLine)
            .where(QuotePaymentLine.quote_id == quote_id)
            .order_by(QuotePaymentLine.sort_order, QuotePaymentLine.line_date)
        ).all()
    )


def summarize_quote_cash(
    db: Session,
    quote: Quote,
    *,
    revision: QuoteRevision | None = None,
) -> dict:
    if revision is None:
        revision = _current_revision(db, quote)
    quoted = _d(revision.quoted_revenue) if revision else Decimal("0")
    invoices = list_invoice_lines(db, quote.id)
    payments = list_payment_lines(db, quote.id)
    total_invoiced = sum((_d(row.amount) for row in invoices), Decimal("0"))
    total_paid = sum((_d(row.amount) for row in payments), Decimal("0"))
    balance_due = max(Decimal("0"), total_invoiced - total_paid)

    from app.services.finance.quote_hours_balance_service import (
        calculate_quote_hours_balance,
        sum_closed_amount,
    )

    hours_snap = calculate_quote_hours_balance(
        db, quote, revision=revision, invoice_lines=invoices
    )
    closed_amount = sum_closed_amount(db, quote.id)
    # Billable remaining value: awarded − invoiced − explicitly closed balance
    remaining_to_invoice = max(Decimal("0"), quoted - total_invoiced - closed_amount)
    remaining_contract = max(Decimal("0"), quoted - total_paid)
    earliest_invoice = min((row.line_date for row in invoices), default=None)
    latest_payment = max((row.line_date for row in payments), default=None)
    is_invoiced = total_invoiced > 0
    is_paid = is_invoiced and balance_due == 0
    # Compare to quoted contract. Never treat as fully invoiced when quoted is
    # unknown/zero but cash lines exist (avoids false "Invoiced" / "Settled").
    if total_invoiced <= 0:
        invoice_status = "none"
    elif quoted <= 0:
        invoice_status = "partial"
    elif remaining_to_invoice <= Decimal("0.01"):
        invoice_status = "full"
    else:
        invoice_status = "partial"
    if total_paid <= 0:
        payment_status = "none"
    elif invoice_status == "partial" and balance_due <= Decimal("0.01"):
        # Settled vs invoices so far, but contract still open.
        payment_status = "partial"
    elif balance_due <= Decimal("0.01"):
        payment_status = "full"
    else:
        payment_status = "partial"
    # is_paid means contract cash is closed (fully invoiced and settled).
    is_paid = invoice_status == "full" and balance_due <= Decimal("0.01")
    return {
        "quoted_revenue": quoted,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "balance_due": balance_due,
        "remaining_to_invoice": remaining_to_invoice,
        "remaining_contract": remaining_contract,
        "is_invoiced": is_invoiced,
        "is_partially_invoiced": invoice_status == "partial",
        "invoice_status": invoice_status,
        "invoiced_date": earliest_invoice,
        "is_paid": is_paid,
        "is_partially_paid": payment_status == "partial",
        "payment_status": payment_status,
        "paid_date": latest_payment if is_paid else None,
        "last_invoice_date": max((row.line_date for row in invoices), default=None),
        "last_payment_date": latest_payment,
        "invoice_lines": invoices,
        "payment_lines": payments,
        "hours": hours_snap,
        "closed_balance_amount": closed_amount,
    }


def derive_awarded_quote_financial_status(
    *,
    awarded_amount: Decimal,
    invoiced_amount: Decimal,
    paid_amount: Decimal,
) -> str:
    """Deterministic lifecycle status from awarded / invoiced / paid amounts."""
    awarded = _d(awarded_amount)
    invoiced = _d(invoiced_amount)
    paid = _d(paid_amount)
    outstanding = max(Decimal("0"), invoiced - paid)

    # Over-invoicing only when a positive awarded value exists (avoid false flags
    # when quoted revenue is still zero / unknown).
    if awarded > 0 and invoiced > awarded + _AMOUNT_TOLERANCE:
        return STATUS_OVER_INVOICED_REQUIRES_REVIEW

    if invoiced <= 0:
        return STATUS_NOT_INVOICED

    fully_invoiced = awarded <= 0 or invoiced >= awarded - _AMOUNT_TOLERANCE
    settled = outstanding <= _AMOUNT_TOLERANCE

    if not fully_invoiced:
        if settled:
            return STATUS_PARTIALLY_INVOICED_PAID
        return STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING

    if settled:
        return STATUS_FULLY_INVOICED_FULLY_PAID
    return STATUS_FULLY_INVOICED_PAYMENT_PENDING


def calculate_awarded_quote_financial_status(
    db: Session,
    quote: Quote | UUID,
    *,
    revision: QuoteRevision | None = None,
) -> dict:
    """
    Authoritative awarded-quote financial snapshot.

    Status is always derived from Awarded Value + invoice lines + payment lines.
    """
    if isinstance(quote, UUID):
        loaded = load_quote_with_ledger(db, quote)
        if loaded is None:
            raise ProTrackValidationError("Quote not found.")
        quote = loaded
    cash = summarize_quote_cash(db, quote, revision=revision)
    awarded = _d(cash["quoted_revenue"])
    invoiced = _d(cash["total_invoiced"])
    paid = _d(cash["total_paid"])
    outstanding = _d(cash["balance_due"])
    remaining_to_invoice = _d(cash["remaining_to_invoice"])
    status = derive_awarded_quote_financial_status(
        awarded_amount=awarded,
        invoiced_amount=invoiced,
        paid_amount=paid,
    )
    # Balance closed: treat remaining-to-invoice as settled for status when hours closed
    hours = cash.get("hours") or {}
    if hours.get("hours_status") == "BALANCE_CLOSED" and remaining_to_invoice <= _AMOUNT_TOLERANCE:
        if paid >= invoiced - _AMOUNT_TOLERANCE:
            status = STATUS_FULLY_INVOICED_FULLY_PAID if invoiced > 0 else status
        elif invoiced > 0:
            status = STATUS_FULLY_INVOICED_PAYMENT_PENDING
    overpayment_amount = max(Decimal("0"), paid - invoiced)
    over_invoiced_variance = (
        max(Decimal("0"), invoiced - awarded) if awarded > 0 else Decimal("0")
    )
    return {
        **cash,
        "awarded_amount": awarded,
        "invoiced_amount": invoiced,
        "paid_amount": paid,
        "outstanding_amount": outstanding,
        "remaining_to_invoice": remaining_to_invoice,
        "invoice_percentage": _pct(invoiced, awarded),
        "collection_percentage": _pct(paid, invoiced),
        "awarded_collection_percentage": _pct(paid, awarded),
        "financial_status": status,
        "is_over_invoiced": status == STATUS_OVER_INVOICED_REQUIRES_REVIEW,
        "over_invoiced_variance": over_invoiced_variance,
        "is_overpayment": overpayment_amount > _AMOUNT_TOLERANCE,
        "overpayment_amount": overpayment_amount,
        "quoted_hours": hours.get("quoted_hours", Decimal("0")),
        "invoiced_hours": hours.get("invoiced_hours", Decimal("0")),
        "remaining_hours": hours.get("remaining_hours", Decimal("0")),
        "closed_balance_hours": hours.get("closed_balance_hours", Decimal("0")),
        "closed_balance_amount": cash.get("closed_balance_amount", Decimal("0")),
        "hours_status": hours.get("hours_status", "UNKNOWN"),
        "remaining_hours_value": hours.get("remaining_value"),
        "is_financially_closed": (
            status != STATUS_OVER_INVOICED_REQUIRES_REVIEW
            and remaining_to_invoice <= _AMOUNT_TOLERANCE
            and outstanding <= _AMOUNT_TOLERANCE
            and (awarded > 0 or invoiced > 0)
        ),
    }


def sync_quote_cash_flags(db: Session, quote: Quote) -> dict:
    """Recompute and persist derived is_invoiced / is_paid flags on the quote."""
    summary = summarize_quote_cash(db, quote)
    quote.is_invoiced = bool(summary["is_invoiced"])
    quote.invoiced_date = summary["invoiced_date"]
    quote.is_paid = bool(summary["is_paid"])
    quote.paid_date = summary["paid_date"]
    db.add(quote)
    return summary


def _next_sort_order(db: Session, model, quote_id: UUID) -> int:
    current = db.scalar(
        select(func.coalesce(func.max(model.sort_order), -1)).where(model.quote_id == quote_id)
    )
    return int(current or -1) + 1


def add_invoice_line(
    db: Session,
    *,
    quote: Quote,
    amount: Decimal,
    line_date: date,
    notes: str | None = None,
    invoice_number: str | None = None,
    due_date: date | None = None,
    tax_amount: Decimal | None = None,
    subtotal_amount: Decimal | None = None,
    content_sha256: str | None = None,
    quantity_hours: Decimal | None = None,
    payment_terms: str | None = None,
    payment_terms_days: int | None = None,
    payment_terms_source: str | None = None,
) -> QuoteInvoiceLine:
    amount = _d(amount)
    if amount <= 0:
        raise ProTrackValidationError("Invoice amount must be greater than zero.")
    revision = _current_revision(db, quote)
    quoted = _d(revision.quoted_revenue) if revision else Decimal("0")
    existing = sum((_d(row.amount) for row in list_invoice_lines(db, quote.id)), Decimal("0"))
    if quoted > 0 and existing + amount > quoted * _TOLERANCE:
        raise ProTrackValidationError(
            f"Invoice total would exceed quoted revenue ({quoted})."
        )
    qty = _d(quantity_hours) if quantity_hours is not None else None
    if qty is not None and qty < 0:
        raise ProTrackValidationError("Invoice quantity hours cannot be negative.")
    terms_label = (payment_terms or "").strip() or None
    terms_days = payment_terms_days
    if terms_days is not None:
        terms_days = int(terms_days)
        if terms_days < 0 or terms_days > 365:
            raise ProTrackValidationError("payment_terms_days must be between 0 and 365.")
    line = QuoteInvoiceLine(
        id=uuid4(),
        quote_id=quote.id,
        amount=amount,
        line_date=line_date,
        notes=(notes or "").strip() or None,
        invoice_number=(invoice_number or "").strip() or None,
        due_date=due_date,
        tax_amount=_d(tax_amount) if tax_amount is not None else None,
        subtotal_amount=_d(subtotal_amount) if subtotal_amount is not None else None,
        quantity_hours=qty if qty is not None and qty > 0 else None,
        payment_terms=terms_label,
        payment_terms_days=terms_days,
        payment_terms_source=(payment_terms_source or "").strip() or None,
        content_sha256=(content_sha256 or "").strip() or None,
        sort_order=_next_sort_order(db, QuoteInvoiceLine, quote.id),
    )
    db.add(line)
    db.flush()
    sync_quote_cash_flags(db, quote)
    return line

def delete_invoice_line(db: Session, *, quote: Quote, line_id: UUID) -> None:
    line = db.get(QuoteInvoiceLine, line_id)
    if line is None or line.quote_id != quote.id:
        raise ProTrackValidationError("Invoice line not found.")
    paid = sum((_d(row.amount) for row in list_payment_lines(db, quote.id)), Decimal("0"))
    remaining_invoiced = sum(
        (
            _d(row.amount)
            for row in list_invoice_lines(db, quote.id)
            if row.id != line_id
        ),
        Decimal("0"),
    )
    if paid > remaining_invoiced * _TOLERANCE:
        raise ProTrackValidationError(
            "Cannot delete this invoice: payments exceed the remaining invoiced total."
        )
    db.delete(line)
    db.flush()
    sync_quote_cash_flags(db, quote)


def add_payment_line(
    db: Session,
    *,
    quote: Quote,
    amount: Decimal,
    line_date: date,
    reference: str | None = None,
    notes: str | None = None,
    invoice_line_id: UUID | None = None,
) -> QuotePaymentLine:
    amount = _d(amount)
    if amount <= 0:
        raise ProTrackValidationError("Payment amount must be greater than zero.")
    invoices = list_invoice_lines(db, quote.id)
    if not invoices:
        raise ProTrackValidationError(
            "Add at least one invoice before recording a payment."
        )
    if invoice_line_id is not None:
        target = next((row for row in invoices if row.id == invoice_line_id), None)
        if target is None:
            raise ProTrackValidationError("Invoice line not found for payment allocation.")
    total_invoiced = sum((_d(row.amount) for row in invoices), Decimal("0"))
    total_paid = sum((_d(row.amount) for row in list_payment_lines(db, quote.id)), Decimal("0"))
    if total_paid + amount > total_invoiced * _TOLERANCE:
        raise ProTrackValidationError(
            f"Payment would exceed invoiced balance "
            f"(invoiced {total_invoiced}, already paid {total_paid})."
        )
    line = QuotePaymentLine(
        id=uuid4(),
        quote_id=quote.id,
        amount=amount,
        line_date=line_date,
        reference=(reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        invoice_line_id=invoice_line_id,
        sort_order=_next_sort_order(db, QuotePaymentLine, quote.id),
    )
    db.add(line)
    db.flush()
    sync_quote_cash_flags(db, quote)
    return line

def delete_payment_line(db: Session, *, quote: Quote, line_id: UUID) -> None:
    line = db.get(QuotePaymentLine, line_id)
    if line is None or line.quote_id != quote.id:
        raise ProTrackValidationError("Payment line not found.")
    db.delete(line)
    db.flush()
    sync_quote_cash_flags(db, quote)


def ensure_invoice_from_legacy_flags(
    db: Session,
    *,
    quote: Quote,
    amount: Decimal | None = None,
    line_date: date | None = None,
) -> QuoteInvoiceLine | None:
    """If quote marked invoiced with no lines, create one invoice for amount."""
    if list_invoice_lines(db, quote.id):
        return None
    revision = _current_revision(db, quote)
    amt = _d(amount if amount is not None else (revision.quoted_revenue if revision else 0))
    if amt <= 0:
        return None
    return add_invoice_line(
        db,
        quote=quote,
        amount=amt,
        line_date=line_date or quote.invoiced_date or date.today(),
        notes="Migrated from invoiced flag",
    )


def ensure_payment_from_legacy_flags(
    db: Session,
    *,
    quote: Quote,
    amount: Decimal | None = None,
    line_date: date | None = None,
) -> QuotePaymentLine | None:
    if list_payment_lines(db, quote.id):
        return None
    summary = summarize_quote_cash(db, quote)
    if summary["total_invoiced"] <= 0:
        return None
    amt = _d(amount if amount is not None else summary["balance_due"])
    if amt <= 0:
        return None
    return add_payment_line(
        db,
        quote=quote,
        amount=amt,
        line_date=line_date or quote.paid_date or date.today(),
        reference="Migrated from paid flag",
    )
