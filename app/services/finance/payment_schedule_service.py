"""Customer / quote commercial payment schedules (planned milestones).

Payment Schedule = when/what % to invoice.
Payment Terms = when payment is due after an invoice.

Future milestones are never overdue. Only posted invoices with due dates age.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote, QuoteInvoiceLine, QuotePaymentMilestone
from app.models.models import Customer, CustomerPaymentMilestone
from app.services.finance.payment_terms_service import (
    TIMING_DUE_SOON,
    TIMING_DUE_TODAY,
    TIMING_FULLY_PAID,
    TIMING_NOT_YET_DUE,
    TIMING_OVERDUE,
    TIMING_PARTIALLY_PAID,
    calculate_due_date,
    payment_timing_status,
)
from app.services.finance.quote_cash_ledger_service import (
    calculate_awarded_quote_financial_status,
    list_invoice_lines,
    list_payment_lines,
)

PAYMENT_MODELS = frozenset(
    {"NET_TERMS", "MILESTONE_BASED", "MIXED", "DUE_ON_RECEIPT", "CUSTOM"}
)

TRIGGER_TYPES = frozenset(
    {
        "PROJECT_START",
        "PROJECT_KICKOFF",
        "OKTT_DATA_RECEIVED",
        "PART_DATA_RECEIVED",
        "OKTT_PART_DATA_RECEIVED",
        "DESIGN_START",
        "DESIGN_MILESTONE",
        "INTERMEDIATE_REVIEW",
        "FINAL_REVIEW",
        "PROJECT_COMPLETION",
        "FILE_RELEASE",
        "BOM_RELEASE",
        "CUSTOM_EVENT",
    }
)

INVOICE_TIMINGS = frozenset({"IMMEDIATE", "ON_TRIGGER", "BEFORE_TRIGGER", "AFTER_TRIGGER"})
PAYMENT_TIMINGS = frozenset({"DUE_ON_RECEIPT", "NET_DAYS", "CUSTOM_DATE"})

STATUS_NOT_YET_TRIGGERED = "NOT_YET_TRIGGERED"
STATUS_TRIGGERED = "TRIGGERED"
STATUS_READY_TO_INVOICE = "READY_TO_INVOICE"
STATUS_INVOICED = "INVOICED"
STATUS_WAIVED = "WAIVED"

SCHEDULE_SOURCE_CUSTOMER = "CUSTOMER_DEFAULT"
SCHEDULE_SOURCE_QUOTE = "QUOTE_OVERRIDE"
SCHEDULE_SOURCE_NONE = "NONE"


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _pct_d(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def _validate_milestone_payload(item: dict[str, Any], *, index: int) -> None:
    name = (item.get("name") or "").strip()
    if not name:
        raise ProTrackValidationError(f"Milestone {index + 1}: name is required.")
    trigger = (item.get("trigger_type") or "CUSTOM_EVENT").strip().upper()
    if trigger not in TRIGGER_TYPES:
        raise ProTrackValidationError(f"Milestone {index + 1}: invalid trigger_type.")
    inv_t = (item.get("invoice_timing") or "ON_TRIGGER").strip().upper()
    if inv_t not in INVOICE_TIMINGS:
        raise ProTrackValidationError(f"Milestone {index + 1}: invalid invoice_timing.")
    pay_t = (item.get("payment_timing") or "NET_DAYS").strip().upper()
    if pay_t not in PAYMENT_TIMINGS:
        raise ProTrackValidationError(f"Milestone {index + 1}: invalid payment_timing.")
    pct = item.get("percentage")
    fixed = item.get("fixed_amount")
    if pct is None and fixed is None:
        raise ProTrackValidationError(
            f"Milestone {index + 1}: percentage or fixed_amount is required."
        )
    if pct is not None and (float(pct) < 0 or float(pct) > 100):
        raise ProTrackValidationError(f"Milestone {index + 1}: percentage must be 0–100.")
    days = item.get("payment_terms_days")
    if pay_t == "DUE_ON_RECEIPT":
        item["payment_terms_days"] = 0
    elif days is not None and (int(days) < 0 or int(days) > 365):
        raise ProTrackValidationError(
            f"Milestone {index + 1}: payment_terms_days must be 0–365."
        )


def list_customer_milestones(db: Session, customer_id: UUID) -> list[CustomerPaymentMilestone]:
    return list(
        db.scalars(
            select(CustomerPaymentMilestone)
            .where(
                CustomerPaymentMilestone.customer_id == customer_id,
                CustomerPaymentMilestone.is_active.is_(True),
            )
            .order_by(CustomerPaymentMilestone.sequence)
        ).all()
    )


def replace_customer_milestones(
    db: Session,
    *,
    customer: Customer,
    milestones: list[dict[str, Any]],
) -> list[CustomerPaymentMilestone]:
    existing = list(
        db.scalars(
            select(CustomerPaymentMilestone).where(
                CustomerPaymentMilestone.customer_id == customer.id
            )
        ).all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    created: list[CustomerPaymentMilestone] = []
    for idx, raw in enumerate(milestones):
        item = dict(raw)
        _validate_milestone_payload(item, index=idx)
        row = CustomerPaymentMilestone(
            id=uuid4(),
            customer_id=customer.id,
            sequence=int(item.get("sequence") or idx + 1),
            name=str(item["name"]).strip(),
            percentage=_pct_d(item.get("percentage")),
            fixed_amount=_d(item["fixed_amount"]) if item.get("fixed_amount") is not None else None,
            trigger_type=str(item.get("trigger_type") or "CUSTOM_EVENT").strip().upper(),
            trigger_description=(item.get("trigger_description") or None),
            invoice_timing=str(item.get("invoice_timing") or "ON_TRIGGER").strip().upper(),
            payment_timing=str(item.get("payment_timing") or "NET_DAYS").strip().upper(),
            payment_terms_days=(
                int(item["payment_terms_days"])
                if item.get("payment_terms_days") is not None
                else None
            ),
            due_date_rule=(item.get("due_date_rule") or None),
            is_active=bool(item.get("is_active", True)),
        )
        if row.payment_timing == "DUE_ON_RECEIPT":
            row.payment_terms_days = 0
        db.add(row)
        created.append(row)
    db.flush()
    return created


def list_quote_milestones(db: Session, quote_id: UUID) -> list[QuotePaymentMilestone]:
    return list(
        db.scalars(
            select(QuotePaymentMilestone)
            .where(
                QuotePaymentMilestone.quote_id == quote_id,
                QuotePaymentMilestone.is_active.is_(True),
            )
            .order_by(QuotePaymentMilestone.sequence)
        ).all()
    )


def seed_quote_schedule_from_customer(
    db: Session,
    *,
    quote: Quote,
    customer: Customer | None = None,
    force: bool = False,
) -> list[QuotePaymentMilestone]:
    """Copy customer default milestones onto quote when quote has none."""
    existing = list_quote_milestones(db, quote.id)
    if existing and not force:
        return existing

    if customer is None:
        customer = db.get(Customer, quote.customer_id)
    if customer is None:
        return existing

    if force and existing:
        for row in existing:
            db.delete(row)
        db.flush()

    cust_rows = list_customer_milestones(db, customer.id)
    created: list[QuotePaymentMilestone] = []
    for idx, src in enumerate(cust_rows):
        row = QuotePaymentMilestone(
            id=uuid4(),
            quote_id=quote.id,
            sequence=src.sequence or idx + 1,
            name=src.name,
            percentage=src.percentage,
            fixed_amount=src.fixed_amount,
            trigger_type=src.trigger_type,
            trigger_description=src.trigger_description,
            invoice_timing=src.invoice_timing,
            payment_timing=src.payment_timing,
            payment_terms_days=src.payment_terms_days,
            due_date_rule=src.due_date_rule,
            is_active=True,
            trigger_status=STATUS_NOT_YET_TRIGGERED,
        )
        db.add(row)
        created.append(row)

    if created:
        quote.payment_schedule_source = SCHEDULE_SOURCE_CUSTOMER
        if not quote.payment_model and customer.default_payment_model:
            quote.payment_model = customer.default_payment_model
        if quote.payment_terms is None and customer.default_payment_terms:
            quote.payment_terms = customer.default_payment_terms
        if quote.payment_terms_days is None and customer.default_payment_terms_days is not None:
            quote.payment_terms_days = customer.default_payment_terms_days
        db.add(quote)
    elif not quote.payment_schedule_source:
        quote.payment_schedule_source = SCHEDULE_SOURCE_NONE
        db.add(quote)
    db.flush()
    return created


def replace_quote_schedule(
    db: Session,
    *,
    quote: Quote,
    milestones: list[dict[str, Any]],
    payment_model: str | None = None,
    payment_terms: str | None = None,
    payment_terms_days: int | None = None,
) -> list[QuotePaymentMilestone]:
    existing = list(
        db.scalars(
            select(QuotePaymentMilestone).where(QuotePaymentMilestone.quote_id == quote.id)
        ).all()
    )
    prior_by_key = {
        (row.sequence, row.name.strip().lower()): row for row in existing
    }
    for row in existing:
        db.delete(row)
    db.flush()

    created: list[QuotePaymentMilestone] = []
    for idx, raw in enumerate(milestones):
        item = dict(raw)
        _validate_milestone_payload(item, index=idx)
        seq = int(item.get("sequence") or idx + 1)
        name = str(item["name"]).strip()
        prior = prior_by_key.get((seq, name.lower()))
        row = QuotePaymentMilestone(
            id=uuid4(),
            quote_id=quote.id,
            sequence=seq,
            name=name,
            percentage=_pct_d(item.get("percentage")),
            fixed_amount=_d(item["fixed_amount"]) if item.get("fixed_amount") is not None else None,
            trigger_type=str(item.get("trigger_type") or "CUSTOM_EVENT").strip().upper(),
            trigger_description=(item.get("trigger_description") or None),
            invoice_timing=str(item.get("invoice_timing") or "ON_TRIGGER").strip().upper(),
            payment_timing=str(item.get("payment_timing") or "NET_DAYS").strip().upper(),
            payment_terms_days=(
                int(item["payment_terms_days"])
                if item.get("payment_terms_days") is not None
                else None
            ),
            due_date_rule=(item.get("due_date_rule") or None),
            is_active=bool(item.get("is_active", True)),
            trigger_status=(prior.trigger_status if prior else STATUS_NOT_YET_TRIGGERED),
            triggered_at=prior.triggered_at if prior else None,
            triggered_by_id=prior.triggered_by_id if prior else None,
            fulfilled_invoice_line_id=prior.fulfilled_invoice_line_id if prior else None,
        )
        if row.payment_timing == "DUE_ON_RECEIPT":
            row.payment_terms_days = 0
        if row.fulfilled_invoice_line_id:
            row.trigger_status = STATUS_INVOICED
        db.add(row)
        created.append(row)

    if payment_model is not None:
        model = payment_model.strip().upper() if payment_model else None
        if model and model not in PAYMENT_MODELS:
            raise ProTrackValidationError("Invalid payment_model.")
        quote.payment_model = model
    if payment_terms is not None:
        quote.payment_terms = (payment_terms or "").strip() or None
    if payment_terms_days is not None:
        quote.payment_terms_days = int(payment_terms_days)
    quote.payment_schedule_source = (
        SCHEDULE_SOURCE_QUOTE if created else SCHEDULE_SOURCE_NONE
    )
    db.add(quote)
    db.flush()
    return created


def mark_milestone_triggered(
    db: Session,
    *,
    quote: Quote,
    milestone_id: UUID | None = None,
    trigger_type: str | None = None,
    user_id: UUID | None = None,
) -> list[QuotePaymentMilestone]:
    """Mark matching milestones READY_TO_INVOICE. Does not create invoices."""
    rows = list_quote_milestones(db, quote.id)
    if not rows:
        raise ProTrackValidationError("Quote has no payment schedule.")
    updated: list[QuotePaymentMilestone] = []
    now = datetime.now(timezone.utc)
    for row in rows:
        if row.trigger_status in (STATUS_INVOICED, STATUS_WAIVED):
            continue
        match = False
        if milestone_id is not None and row.id == milestone_id:
            match = True
        if trigger_type and row.trigger_type == trigger_type.strip().upper():
            match = True
        if not match:
            continue
        row.trigger_status = STATUS_READY_TO_INVOICE
        row.triggered_at = now
        row.triggered_by_id = user_id
        db.add(row)
        updated.append(row)
    if not updated:
        raise ProTrackValidationError("No matching untriggered milestone found.")
    db.flush()
    return updated


def milestone_scheduled_amount(
    milestone: QuotePaymentMilestone | CustomerPaymentMilestone,
    awarded: Decimal,
) -> Decimal:
    if milestone.fixed_amount is not None:
        return _d(milestone.fixed_amount)
    if milestone.percentage is not None:
        return _d(awarded * Decimal(str(milestone.percentage)) / Decimal("100"))
    return Decimal("0.00")


def summarize_quote_payment_schedule(
    db: Session,
    *,
    quote: Quote,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Schedule + cash snapshot distinguishing future milestones from overdue."""
    as_of = as_of or date.today()
    cash = calculate_awarded_quote_financial_status(db, quote)
    awarded = _d(cash.get("awarded_amount"))
    invoiced = _d(cash.get("invoiced_amount"))
    paid = _d(cash.get("collected_amount", cash.get("total_paid")))
    outstanding = _d(cash.get("outstanding_amount", cash.get("balance_due")))
    remaining_to_invoice = _d(cash.get("remaining_to_invoice"))

    milestones = list_quote_milestones(db, quote.id)
    invoice_lines = list_invoice_lines(db, quote.id)
    payments = list_payment_lines(db, quote.id)
    total_paid = sum((_d(p.amount) for p in payments), Decimal("0"))

    remaining_paid = total_paid
    inv_paid: dict[UUID, tuple[Decimal, Decimal]] = {}
    for line in sorted(
        invoice_lines, key=lambda r: (r.line_date or date.min, r.sort_order or 0)
    ):
        amt = _d(line.amount)
        applied = min(amt, remaining_paid)
        remaining_paid -= applied
        inv_paid[line.id] = (applied, max(Decimal("0"), amt - applied))

    scheduled_total = Decimal("0.00")
    pct_total = Decimal("0.0000")
    future = Decimal("0.00")
    ready = Decimal("0.00")
    not_yet_due = Decimal("0.00")
    overdue = Decimal("0.00")
    lines_out: list[dict[str, Any]] = []
    warnings: list[str] = []

    for m in milestones:
        sched_amt = milestone_scheduled_amount(m, awarded)
        scheduled_total += sched_amt
        if m.percentage is not None:
            pct_total += Decimal(str(m.percentage))

        inv_line = None
        if m.fulfilled_invoice_line_id:
            inv_line = next(
                (x for x in invoice_lines if x.id == m.fulfilled_invoice_line_id), None
            )
        if inv_line is None:
            inv_line = next(
                (x for x in invoice_lines if x.payment_milestone_id == m.id), None
            )

        paid_amt = Decimal("0.00")
        out_amt = Decimal("0.00")
        invoice_status = "NOT_INVOICED"
        payment_status = "NOT_INVOICED"
        timing = None
        due = None

        if inv_line is not None:
            invoice_status = "INVOICED"
            if m.trigger_status != STATUS_INVOICED:
                m.trigger_status = STATUS_INVOICED
                m.fulfilled_invoice_line_id = inv_line.id
                db.add(m)
            paid_amt, out_amt = inv_paid.get(inv_line.id, (Decimal("0"), _d(inv_line.amount)))
            due = inv_line.due_date
            timing = payment_timing_status(
                due_date=due,
                outstanding=out_amt,
                invoiced=_d(inv_line.amount),
                paid=paid_amt,
                today=as_of,
            )
            payment_status = timing.get("payment_timing_status") or timing
            if out_amt > 0 and payment_status == TIMING_OVERDUE:
                overdue += out_amt
            elif out_amt > 0 and payment_status in (
                TIMING_NOT_YET_DUE,
                TIMING_DUE_SOON,
                TIMING_DUE_TODAY,
            ):
                not_yet_due += out_amt
            if out_amt <= 0:
                payment_status = TIMING_FULLY_PAID
            elif paid_amt > 0 and out_amt > 0:
                payment_status = TIMING_PARTIALLY_PAID
        elif m.trigger_status in (STATUS_READY_TO_INVOICE, STATUS_TRIGGERED):
            invoice_status = STATUS_READY_TO_INVOICE
            payment_status = STATUS_READY_TO_INVOICE
            ready += sched_amt
        else:
            invoice_status = STATUS_NOT_YET_TRIGGERED
            payment_status = "FUTURE_MILESTONE"
            future += sched_amt

        lines_out.append(
            {
                "id": str(m.id),
                "sequence": m.sequence,
                "name": m.name,
                "percentage": float(m.percentage) if m.percentage is not None else None,
                "fixed_amount": float(m.fixed_amount) if m.fixed_amount is not None else None,
                "scheduled_amount": float(sched_amt),
                "trigger_type": m.trigger_type,
                "trigger_description": m.trigger_description,
                "invoice_timing": m.invoice_timing,
                "payment_timing": m.payment_timing,
                "payment_terms_days": m.payment_terms_days,
                "trigger_status": m.trigger_status,
                "invoice_status": invoice_status,
                "invoice_date": inv_line.line_date.isoformat() if inv_line and inv_line.line_date else None,
                "invoice_number": inv_line.invoice_number if inv_line else None,
                "invoice_line_id": str(inv_line.id) if inv_line else None,
                "due_date": due.isoformat() if due else None,
                "paid_amount": float(paid_amt),
                "outstanding_amount": float(out_amt),
                "payment_status": payment_status,
                "timing_status": (
                    timing.get("payment_timing_status") if isinstance(timing, dict) else timing
                ),
            }
        )

    if milestones and abs(pct_total - Decimal("100")) > Decimal("0.05") and all(
        m.fixed_amount is None for m in milestones
    ):
        warnings.append(
            f"Scheduled percentages total {float(pct_total):.2f}% (expected ~100%)."
        )
    if awarded > 0 and scheduled_total > 0 and abs(scheduled_total - awarded) > Decimal("1"):
        warnings.append(
            f"Scheduled amount {float(scheduled_total)} differs from awarded {float(awarded)}."
        )

    return {
        "quote_id": str(quote.id),
        "payment_model": quote.payment_model,
        "payment_terms": quote.payment_terms,
        "payment_terms_days": quote.payment_terms_days,
        "payment_schedule_source": quote.payment_schedule_source,
        "awarded_amount": float(awarded),
        "scheduled_invoice_percent": float(pct_total),
        "scheduled_invoice_amount": float(scheduled_total),
        "amount_already_invoiced": float(invoiced),
        "remaining_to_invoice": float(remaining_to_invoice),
        "amount_collected": float(paid),
        "outstanding_amount": float(outstanding),
        "future_milestone_amount": float(future),
        "ready_to_invoice_amount": float(ready),
        "not_yet_due_amount": float(not_yet_due),
        "overdue_amount": float(overdue),
        "milestones": lines_out,
        "warnings": warnings,
        "cash": cash,
    }


def link_invoice_to_milestone(
    db: Session,
    *,
    quote: Quote,
    invoice_line: QuoteInvoiceLine,
    milestone_id: UUID | None,
) -> QuotePaymentMilestone | None:
    if milestone_id is None:
        return None
    milestone = db.get(QuotePaymentMilestone, milestone_id)
    if milestone is None or milestone.quote_id != quote.id:
        raise ProTrackValidationError("Payment milestone not found on this quote.")
    awarded = _d(summarize_quote_payment_schedule(db, quote=quote).get("awarded_amount"))
    sched = milestone_scheduled_amount(milestone, awarded)
    invoice_line.payment_milestone_id = milestone.id
    invoice_line.payment_milestone_name = milestone.name
    invoice_line.payment_milestone_percent = milestone.percentage
    invoice_line.payment_milestone_amount = sched
    invoice_line.trigger_event = milestone.trigger_type
    if invoice_line.payment_model is None:
        invoice_line.payment_model = quote.payment_model
    if invoice_line.payment_terms_days is None and milestone.payment_terms_days is not None:
        invoice_line.payment_terms_days = milestone.payment_terms_days
        if milestone.payment_timing == "DUE_ON_RECEIPT":
            invoice_line.payment_terms = invoice_line.payment_terms or "Due on Receipt"
        elif milestone.payment_terms_days:
            invoice_line.payment_terms = (
                invoice_line.payment_terms or f"Net {milestone.payment_terms_days}"
            )
        if invoice_line.due_date is None and invoice_line.line_date is not None:
            invoice_line.due_date = calculate_due_date(
                invoice_line.line_date, milestone.payment_terms_days
            )
            invoice_line.due_date_source = invoice_line.due_date_source or "PROJECT_OVERRIDE"
    milestone.fulfilled_invoice_line_id = invoice_line.id
    milestone.trigger_status = STATUS_INVOICED
    db.add(milestone)
    db.add(invoice_line)
    db.flush()
    return milestone


def commercial_snapshot_for_audit(customer: Customer, milestones: list) -> str:
    payload = {
        "default_payment_model": customer.default_payment_model,
        "default_payment_terms": customer.default_payment_terms,
        "default_payment_terms_days": customer.default_payment_terms_days,
        "default_payment_terms_description": customer.default_payment_terms_description,
        "milestones": [
            {
                "sequence": m.sequence,
                "name": m.name,
                "percentage": float(m.percentage) if m.percentage is not None else None,
                "fixed_amount": float(m.fixed_amount) if m.fixed_amount is not None else None,
                "trigger_type": m.trigger_type,
                "payment_timing": m.payment_timing,
                "payment_terms_days": m.payment_terms_days,
            }
            for m in milestones
        ],
    }
    return json.dumps(payload, sort_keys=True)
