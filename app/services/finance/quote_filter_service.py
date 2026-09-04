"""Quote list filters using cash-ledger-derived invoice/payment status."""

from __future__ import annotations

from typing import Any, Mapping


def normalize_invoice_status(status: str | None) -> str | None:
    if status is None:
        return None
    key = str(status).strip().lower()
    aliases = {
        "none": "none",
        "not_invoiced": "none",
        "uninvoiced": "none",
        "partial": "partial",
        "partially_invoiced": "partial",
        "full": "full",
        "invoiced": "full",
        "fully_invoiced": "full",
    }
    return aliases.get(key)


def normalize_payment_status(status: str | None) -> str | None:
    if status is None:
        return None
    key = str(status).strip().lower()
    aliases = {
        "none": "none",
        "unpaid": "none",
        "partial": "partial",
        "partially_paid": "partial",
        "full": "full",
        "paid": "full",
        "settled": "full",
    }
    return aliases.get(key)


def quote_matches_list_filter(row: Mapping[str, Any], list_filter: str | None) -> bool:
    """Apply Finance Quotes panel list-filter semantics to a QuoteRead-like mapping."""
    if not list_filter or list_filter in {"all", ""}:
        return True

    invoice_status = str(row.get("invoice_status") or "none").lower()
    payment_status = str(row.get("payment_status") or "none").lower()
    balance_due = float(row.get("balance_due") or 0)
    key = list_filter.strip().lower()

    if key in {"not_invoiced", "none"}:
        return invoice_status == "none"
    if key in {"partially_invoiced", "partial"}:
        return invoice_status == "partial"
    if key in {"invoiced", "full", "fully_invoiced"}:
        # Fully invoiced only — partials are a separate chip.
        return invoice_status == "full"
    if key == "awaiting_payment":
        return balance_due > 0
    if key in {"partially_paid"}:
        return payment_status == "partial" or bool(row.get("is_partially_paid"))
    if key == "follow_up":
        return bool(row.get("payment_follow_up_due"))
    if key == "missing_date":
        return not row.get("quoted_date")
    if key == "unlinked":
        return not bool(row.get("project_linked"))
    return True


def quote_matches_search(row: Mapping[str, Any], q: str | None) -> bool:
    if not q or not str(q).strip():
        return True
    needle = str(q).strip().lower()
    blob = " ".join(
        str(part)
        for part in (
            row.get("external_quote_number"),
            row.get("tool_number"),
            row.get("customer_name"),
            row.get("team_name"),
            row.get("currency_code"),
            row.get("customer_po_number"),
        )
        if part
    ).lower()
    return needle in blob


def quote_matches_filters(
    row: Mapping[str, Any],
    *,
    invoice_status: str | None = None,
    payment_status: str | None = None,
    list_filter: str | None = None,
    q: str | None = None,
    project_linked: bool | None = None,
    missing_quoted_date: bool | None = None,
    payment_follow_up_due: bool | None = None,
) -> bool:
    if list_filter and not quote_matches_list_filter(row, list_filter):
        return False

    wanted_invoice = normalize_invoice_status(invoice_status)
    if wanted_invoice is not None:
        actual = str(row.get("invoice_status") or "none").lower()
        if actual != wanted_invoice:
            return False

    wanted_payment = normalize_payment_status(payment_status)
    if wanted_payment is not None:
        actual = str(row.get("payment_status") or "none").lower()
        if actual != wanted_payment:
            return False

    if project_linked is not None and bool(row.get("project_linked")) != project_linked:
        return False
    if missing_quoted_date is True and row.get("quoted_date"):
        return False
    if missing_quoted_date is False and not row.get("quoted_date"):
        return False
    if payment_follow_up_due is not None and bool(row.get("payment_follow_up_due")) != payment_follow_up_due:
        return False
    if not quote_matches_search(row, q):
        return False
    return True
