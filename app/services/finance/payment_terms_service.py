"""Payment terms normalization, due-date calculation, and invoice timing status.

Authoritative helpers for invoice-level payment timing. Does not create payments.
Balance Due on a PDF is informational only.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

SOURCE_DOCUMENT = "DOCUMENT"
SOURCE_CUSTOMER_DEFAULT = "CUSTOMER_DEFAULT"
SOURCE_USER_OVERRIDE = "USER_OVERRIDE"
SOURCE_SYSTEM_CALCULATED = "SYSTEM_CALCULATED"
SOURCE_NONE = "NONE"

TIMING_NOT_YET_DUE = "NOT_YET_DUE"
TIMING_DUE_SOON = "DUE_SOON"
TIMING_DUE_TODAY = "DUE_TODAY"
TIMING_OVERDUE = "OVERDUE"
TIMING_PARTIALLY_PAID = "PARTIALLY_PAID"
TIMING_FULLY_PAID = "FULLY_PAID"
TIMING_AGING_UNAVAILABLE = "AGING_NOT_AVAILABLE"

DEFAULT_DUE_SOON_DAYS = 7

_TERM_PATTERNS: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"due\s+on\s+receipt|upon\s+receipt|immediate", re.I), 0, "Due on Receipt"),
    (re.compile(r"\bnet\s*90\b|\b90\s*days?\b", re.I), 90, "Net 90"),
    (re.compile(r"\bnet\s*60\b|\b60\s*days?\b", re.I), 60, "Net 60"),
    (re.compile(r"\bnet\s*45\b|\b45\s*days?\b", re.I), 45, "Net 45"),
    (re.compile(r"\bnet\s*30\b|\b30\s*days?\b", re.I), 30, "Net 30"),
    (re.compile(r"\bnet\s*15\b|\b15\s*days?\b", re.I), 15, "Net 15"),
    (re.compile(r"\bnet\s*(\d{1,3})\b", re.I), -1, "Net {n}"),  # dynamic
    (re.compile(r"\b(\d{1,3})\s*days?\b", re.I), -1, "{n} Days"),
]


def normalize_payment_terms(raw: str | None) -> tuple[str | None, int | None]:
    """Return (canonical label, days) from free-text terms. Unknown → (stripped, None)."""
    if raw is None:
        return None, None
    text = " ".join(str(raw).strip().split())
    if not text:
        return None, None
    for pattern, days, label in _TERM_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        if days >= 0:
            return label, days
        # Dynamic day capture
        try:
            n = int(m.group(1))
        except (IndexError, ValueError, TypeError):
            continue
        if n < 0 or n > 365:
            continue
        pretty = label.format(n=n)
        return pretty, n
    return text, None


def calculate_due_date(invoice_date: date | None, terms_days: int | None) -> date | None:
    if invoice_date is None or terms_days is None:
        return None
    return invoice_date + timedelta(days=int(terms_days))


def resolve_invoice_payment_terms(
    *,
    document_terms: str | None = None,
    document_due_date: date | None = None,
    invoice_date: date | None = None,
    customer_default_terms: str | None = None,
    customer_default_days: int | None = None,
    user_terms: str | None = None,
    user_terms_days: int | None = None,
    user_due_date: date | None = None,
) -> dict[str, Any]:
    """
    Resolve payment terms + due date with priority:

    1. User override (when provided)
    2. Explicit document due date / terms
    3. Customer default
    4. None

    Never invent terms. Preserve document due date when present.
    """
    warnings: list[str] = []

    # User override wins when any user field is set
    if user_terms is not None or user_terms_days is not None or user_due_date is not None:
        label, days = normalize_payment_terms(user_terms) if user_terms else (None, None)
        if user_terms_days is not None:
            days = int(user_terms_days)
            if label is None:
                label = "Due on Receipt" if days == 0 else f"Net {days}"
        due = user_due_date
        if due is None and invoice_date is not None and days is not None:
            due = calculate_due_date(invoice_date, days)
        return {
            "payment_terms": label or (user_terms.strip() if user_terms else None),
            "payment_terms_days": days,
            "due_date": due,
            "payment_terms_source": SOURCE_USER_OVERRIDE,
            "calculated_due_date": calculate_due_date(invoice_date, days),
            "warnings": warnings,
        }

    doc_label, doc_days = normalize_payment_terms(document_terms)
    calc_from_doc = calculate_due_date(invoice_date, doc_days)

    if document_due_date is not None:
        if calc_from_doc is not None and calc_from_doc != document_due_date:
            warnings.append(
                f"Invoice states Due Date {document_due_date.isoformat()}, "
                f"while payment terms calculate to {calc_from_doc.isoformat()}."
            )
        return {
            "payment_terms": doc_label or document_terms,
            "payment_terms_days": doc_days,
            "due_date": document_due_date,
            "payment_terms_source": SOURCE_DOCUMENT,
            "calculated_due_date": calc_from_doc,
            "warnings": warnings,
        }

    if doc_label is not None or doc_days is not None:
        return {
            "payment_terms": doc_label or document_terms,
            "payment_terms_days": doc_days,
            "due_date": calc_from_doc,
            "payment_terms_source": SOURCE_DOCUMENT
            if doc_days is not None
            else SOURCE_NONE,
            "calculated_due_date": calc_from_doc,
            "warnings": warnings,
        }

    # Customer default fallback
    cust_label, cust_days = normalize_payment_terms(customer_default_terms)
    if customer_default_days is not None:
        cust_days = int(customer_default_days)
        if cust_label is None:
            cust_label = "Due on Receipt" if cust_days == 0 else f"Net {cust_days}"
    if cust_days is not None:
        calc = calculate_due_date(invoice_date, cust_days)
        warnings.append(
            f"Payment terms were not found in the invoice. "
            f"Customer default of {cust_days} days has been suggested."
        )
        return {
            "payment_terms": cust_label,
            "payment_terms_days": cust_days,
            "due_date": calc,
            "payment_terms_source": SOURCE_CUSTOMER_DEFAULT,
            "calculated_due_date": calc,
            "warnings": warnings,
        }

    return {
        "payment_terms": None,
        "payment_terms_days": None,
        "due_date": None,
        "payment_terms_source": SOURCE_NONE,
        "calculated_due_date": None,
        "warnings": warnings,
    }


def aging_bucket_for_due_date(
    *,
    due_date: date | None,
    outstanding: Decimal,
    today: date | None = None,
) -> str:
    """Due-date based aging bucket. Fully settled → not aged."""
    if outstanding <= 0:
        return "paid"
    if due_date is None:
        return "aging_unavailable"
    today = today or date.today()
    delta = (today - due_date).days
    if delta < 0:
        return "not_yet_due"
    if delta == 0:
        return "due_today"
    if delta <= 30:
        return "1_30_overdue"
    if delta <= 60:
        return "31_60_overdue"
    if delta <= 90:
        return "61_90_overdue"
    return "90_plus_overdue"


def payment_timing_status(
    *,
    due_date: date | None,
    outstanding: Decimal,
    invoiced: Decimal,
    paid: Decimal,
    today: date | None = None,
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS,
) -> dict[str, Any]:
    """Invoice-level payment timing (independent of quote invoice %)."""
    today = today or date.today()
    invoiced_d = Decimal(str(invoiced or 0))
    paid_d = Decimal(str(paid or 0))
    outstanding_d = Decimal(str(outstanding or 0))

    if invoiced_d > 0 and outstanding_d <= Decimal("0.01"):
        timing = TIMING_FULLY_PAID
    elif paid_d > 0 and outstanding_d > Decimal("0.01"):
        timing = TIMING_PARTIALLY_PAID
    elif due_date is None:
        timing = TIMING_AGING_UNAVAILABLE
    else:
        delta = (due_date - today).days
        if delta < 0:
            timing = TIMING_OVERDUE
        elif delta == 0:
            timing = TIMING_DUE_TODAY
        elif delta <= max(0, int(due_soon_days)):
            timing = TIMING_DUE_SOON
        else:
            timing = TIMING_NOT_YET_DUE

    days_until_due = None
    days_overdue = None
    days_since_invoice = None
    if due_date is not None:
        days_until_due = max(0, (due_date - today).days) if due_date >= today else 0
        days_overdue = max(0, (today - due_date).days) if today > due_date else 0
        if outstanding_d <= Decimal("0.01"):
            days_overdue = 0

    return {
        "payment_timing_status": timing,
        "days_until_due": days_until_due,
        "days_overdue": days_overdue if outstanding_d > Decimal("0.01") else 0,
        "days_since_invoice": days_since_invoice,
        "aging_bucket": aging_bucket_for_due_date(
            due_date=due_date, outstanding=outstanding_d, today=today
        ),
    }


__all__ = [
    "DEFAULT_DUE_SOON_DAYS",
    "SOURCE_CUSTOMER_DEFAULT",
    "SOURCE_DOCUMENT",
    "SOURCE_NONE",
    "SOURCE_SYSTEM_CALCULATED",
    "SOURCE_USER_OVERRIDE",
    "TIMING_AGING_UNAVAILABLE",
    "TIMING_DUE_SOON",
    "TIMING_DUE_TODAY",
    "TIMING_FULLY_PAID",
    "TIMING_NOT_YET_DUE",
    "TIMING_OVERDUE",
    "TIMING_PARTIALLY_PAID",
    "aging_bucket_for_due_date",
    "calculate_due_date",
    "normalize_payment_terms",
    "payment_timing_status",
    "resolve_invoice_payment_terms",
]
