"""Quote billing readiness checklist (R3)."""

from __future__ import annotations

from app.models.finance import Quote


def quote_billing_gaps(quote: Quote) -> list[str]:
    gaps: list[str] = []
    if quote.team_id is None:
        gaps.append("team")
    if quote.project_id is None:
        gaps.append("project_link")
    if not (quote.currency_code or "").strip():
        gaps.append("currency")
    if quote.quoted_date is None:
        gaps.append("quoted_date")
    if quote.is_invoiced and quote.invoiced_date is None:
        gaps.append("invoiced_date")
    return gaps


def quote_billing_ready(quote: Quote) -> bool:
    return len(quote_billing_gaps(quote)) == 0
