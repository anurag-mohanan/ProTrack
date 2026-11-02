"""Finance tools. Read-only wrappers over the Finance services; amounts are never re-derived here."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.models.finance import Quote
from app.models.models import Customer, Project
from app.services.assistant.context import AssistantContext
from app.services.assistant.tools.common import clip, num
from app.services.assistant.types import Source, Table, ToolResult, ToolSpec
from app.services.finance.customer_financial_service import list_quote_financial_snapshots
from app.services.finance.fy_turnover_service import build_fy_turnover_control
from app.services.finance.receivables_service import build_receivables_aging
from app.services.forecasting.finance import build_finance_forecast

FINANCE_DENIED = "Finance information requires the Financial Planning module (view)."

VALUE_TERMS = (
    "Awarded value is the quoted revenue of the quote's current revision (Finance treats active quotes as awarded). "
    "Invoiced is the sum of invoice lines, collected the sum of payment lines, outstanding = invoiced − collected, "
    "remaining to invoice = awarded − invoiced − explicitly closed balance."
)

_STATUS_FILTERS = {
    "not_invoiced": {"not_invoiced"},
    "partially_invoiced": {"partially_invoiced_paid", "partially_invoiced_payment_pending"},
    "payment_pending": {"partially_invoiced_payment_pending", "fully_invoiced_payment_pending"},
    "over_invoiced": {"over_invoiced_requires_review"},
}


def _customers(ctx: AssistantContext, ids: set) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(ctx.db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(ids))).all())


def _billing_status(ctx: AssistantContext, args: dict) -> ToolResult:
    which = args.get("status", "open")
    snapshots = list_quote_financial_snapshots(ctx.db)
    if which == "open":
        snapshots = [s for s in snapshots if not s.get("is_financially_closed")]
    elif which in _STATUS_FILTERS:
        snapshots = [s for s in snapshots if s.get("financial_status") in _STATUS_FILTERS[which]]
    customers = _customers(ctx, {s.get("customer_id") for s in snapshots})
    if args.get("customer"):
        needle = args["customer"].lower()
        snapshots = [s for s in snapshots if needle in (customers.get(s.get("customer_id")) or "").lower()]
    projects = {}
    project_ids = {s.get("project_id") for s in snapshots if s.get("project_id")}
    if project_ids:
        projects = dict(ctx.db.execute(select(Project.id, Project.code).where(Project.id.in_(project_ids))).all())
    snapshots.sort(key=lambda s: -float(s.get("remaining_to_invoice") or 0) - float(s.get("outstanding_amount") or 0))
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    for s in snapshots:
        cur = s.get("currency_code") or "?"
        for key in ("awarded_amount", "invoiced_amount", "paid_amount", "outstanding_amount", "remaining_to_invoice"):
            totals[cur][key] += Decimal(str(s.get(key) or 0))
    shown = snapshots[: args.get("limit", 20)]
    rows = [{
        "quote": s.get("external_quote_number") or s.get("tool_number"), "tool_number": s.get("tool_number"),
        "project": projects.get(s.get("project_id")), "customer": clip(customers.get(s.get("customer_id")), 80),
        "currency": s.get("currency_code"), "financial_status": s.get("financial_status"),
        "awarded": num(s.get("awarded_amount")), "invoiced": num(s.get("invoiced_amount")),
        "collected": num(s.get("paid_amount")), "outstanding": num(s.get("outstanding_amount")),
        "remaining_to_invoice": num(s.get("remaining_to_invoice")), "last_invoice_date": s.get("last_invoice_date"),
        "last_payment_date": s.get("last_payment_date"),
    } for s in shown]
    limitations = [VALUE_TERMS]
    if len(totals) > 1:
        limitations.append("Several currencies are in use; totals are given per currency and are not added together.")
    if len(snapshots) > len(shown):
        limitations.append(f"{len(snapshots)} quotes matched; the {len(shown)} with the largest open amounts are shown.")
    return ToolResult(
        data={"filter": which, "matched": len(snapshots), "quotes": rows,
              "totals_by_currency": {c: {k: num(v) for k, v in t.items()} for c, t in totals.items()}},
        record_count=len(snapshots),
        sources=[Source(kind="quote", ref=str(s["quote_id"]), label=f"Quote {s.get('external_quote_number') or s.get('tool_number')}",
                        detail=s.get("financial_status"), route="/finance") for s in shown],
        tables=[Table(title="Billing status by quote",
                      columns=["Quote", "Customer", "Currency", "Status", "Awarded", "Invoiced", "Collected", "Outstanding", "To invoice"],
                      rows=[[r["quote"], r["customer"], r["currency"], r["financial_status"], r["awarded"], r["invoiced"],
                             r["collected"], r["outstanding"], r["remaining_to_invoice"]] for r in rows])] if rows else [],
        limitations=limitations,
    )


def _receivables(ctx: AssistantContext, args: dict) -> ToolResult:
    aging = build_receivables_aging(ctx.db, today=ctx.today)
    rows = aging["rows"]
    if args.get("overdue_only", True):
        rows = [r for r in rows if (r.get("days_overdue") or 0) > 0]
    if args.get("customer"):
        needle = args["customer"].lower()
        rows = [r for r in rows if needle in (r.get("customer_name") or "").lower()]
    currencies = dict(ctx.db.execute(
        select(Quote.id, Quote.currency_code).where(Quote.id.in_({_uuid(r["quote_id"]) for r in rows}))
    ).all()) if rows else {}
    by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in rows:
        by_currency[currencies.get(_uuid(r["quote_id"])) or "?"] += Decimal(str(r["outstanding"]))
    shown = rows[: args.get("limit", 20)]
    data_rows = [{
        "customer": clip(r.get("customer_name"), 80), "tool_number": r.get("tool_number"), "invoice": r.get("invoice_number"),
        "invoice_date": r.get("invoice_date"), "due_date": r.get("due_date"), "days_overdue": r.get("days_overdue"),
        "outstanding": num(r["outstanding"]), "currency": currencies.get(_uuid(r["quote_id"])),
        "aging_bucket": r.get("aging_bucket"),
    } for r in shown]
    limitations = [aging["method_notes"]["aging"]]
    if len(by_currency) > 1:
        limitations.append("Outstanding amounts are in several currencies; they are listed per currency, not added together.")
    if len(rows) > len(shown):
        limitations.append(f"{len(rows)} invoice lines matched; the {len(shown)} most overdue are shown.")
    return ToolResult(
        data={"as_of": aging["as_of"], "matched": len(rows), "outstanding_by_currency": {c: num(v) for c, v in by_currency.items()},
              "invoices": data_rows},
        record_count=len(rows),
        sources=[Source(kind="invoice", ref=str(r.get("invoice_line_id") or r["quote_id"]),
                        label=f"Invoice {r.get('invoice_number') or '(no number)'} — {r.get('tool_number')}",
                        detail=f"Due {r.get('due_date') or 'not set'}", route="/finance") for r in shown],
        tables=[Table(title="Outstanding invoices",
                      columns=["Customer", "Tool", "Invoice", "Due date", "Days overdue", "Outstanding", "Currency"],
                      rows=[[r["customer"], r["tool_number"], r["invoice"], r["due_date"], r["days_overdue"],
                             r["outstanding"], r["currency"]] for r in data_rows])] if data_rows else [],
        limitations=limitations,
    )


def _uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _fy_billing(ctx: AssistantContext, args: dict) -> ToolResult:
    fy = build_fy_turnover_control(ctx.db, today=ctx.today, fy_start_year=args.get("fy_start_year"))
    months = [{"month": m["label"], "turnover_inr": num(m["turnover_inr"]), "cash_collected_inr": num(m["cash_collected_inr"]),
               "elapsed": m["is_elapsed"]} for m in fy["months"]]
    data = {k: fy[k] for k in ("fy_label", "fy_start", "fy_end", "as_of", "elapsed_months", "months_with_billing",
                                "zero_billing_months", "mom_change_percent", "highest_billing_month", "lowest_billing_month")}
    for key in ("fytd_turnover_inr", "fytd_cash_collected_inr", "average_monthly_billing_inr",
                "current_month_turnover_inr", "previous_month_turnover_inr", "outstanding_receivables_inr"):
        data[key] = num(fy[key])
    data["months"] = months
    return ToolResult(
        data=data,
        record_count=len([m for m in months if m["elapsed"]]),
        sources=[Source(kind="report", ref=f"fy-turnover:{fy['fy_start']}", label=f"{fy['fy_label']} turnover", route="/finance")],
        tables=[Table(title=f"{fy['fy_label']} billing by month (INR)", columns=["Month", "Turnover (INR)", "Cash collected (INR)"],
                      rows=[[m["month"], m["turnover_inr"], m["cash_collected_inr"]] for m in months if m["elapsed"]])],
        limitations=[*fy["method_notes"].values(), "Amounts are converted to INR with each quote revision's exchange rate."],
    )


def _finance_forecast(ctx: AssistantContext, args: dict) -> ToolResult:
    fc = build_finance_forecast(ctx.db, as_of=ctx.today, granularity=args.get("granularity", "month"),
                                periods=args.get("periods", 6), team_id=None, customer_id=None)
    meta = fc.metadata
    totals = [{"currency": t.currency, "quotes": t.quotes, "outstanding": num(t.outstanding),
               "outstanding_overdue": num(t.outstanding_overdue), "remaining_to_invoice": num(t.remaining_to_invoice),
               "billing_ready": num(t.billing_ready), "billing_dated": num(t.billing_dated), "billing_undated": num(t.billing_undated),
               "collections_by_period": {k: num(v) for k, v in t.collections_by_period.items()},
               "billing_by_period": {k: num(v) for k, v in t.billing_by_period.items()}} for t in fc.totals]
    return ToolResult(
        data={"value_kind": "forecast", "as_of": meta.as_of, "status": meta.status, "assumptions": meta.assumptions,
              "periods": [p.label for p in fc.periods], "totals_by_currency": totals, "warnings": fc.warnings[:10]},
        record_count=fc.reconciliation.quotes_considered,
        sources=[Source(kind="forecast", ref="finance", label="Billing and collection forecast", route="/analytics")],
        tables=[Table(title="Forecast by currency (not actuals)",
                      columns=["Currency", "Outstanding", "Overdue", "Remaining to invoice", "Ready to invoice", "Undated"],
                      rows=[[t["currency"], t["outstanding"], t["outstanding_overdue"], t["remaining_to_invoice"],
                             t["billing_ready"], t["billing_undated"]] for t in totals])] if totals else [],
        limitations=[*meta.assumptions, *meta.limitations],
    )


_FINANCE = lambda ctx: ctx.finance_visible  # noqa: E731

SPECS = [
    ToolSpec(
        name="list_billing_status",
        module="finance",
        description=(
            "Awarded, invoiced, collected, outstanding and remaining-to-invoice amounts per quote. Use for "
            "uninvoiced, partially invoiced, unpaid or over-invoiced work."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "not_invoiced", "partially_invoiced", "payment_pending", "over_invoiced", "all"]},
                "customer": {"type": "string", "maxLength": 100},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "additionalProperties": False,
        },
        allowed=_FINANCE, handler=_billing_status, denied_message=FINANCE_DENIED,
    ),
    ToolSpec(
        name="get_receivables_aging",
        module="finance",
        description="Outstanding invoice lines aged by due date (overdue receivables), with days overdue.",
        parameters={
            "type": "object",
            "properties": {
                "overdue_only": {"type": "boolean"},
                "customer": {"type": "string", "maxLength": 100},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "additionalProperties": False,
        },
        allowed=_FINANCE, handler=_receivables, denied_message=FINANCE_DENIED,
    ),
    ToolSpec(
        name="get_fy_billing",
        module="finance",
        description="Financial-year billing (turnover by invoice date) and cash collected by month, with FY-to-date totals.",
        parameters={
            "type": "object",
            "properties": {"fy_start_year": {"type": "integer", "minimum": 2000, "maximum": 2100}},
            "additionalProperties": False,
        },
        allowed=_FINANCE, handler=_fy_billing, denied_message=FINANCE_DENIED,
    ),
    ToolSpec(
        name="get_finance_forecast",
        module="finance",
        description="Forecast of collections and billing by period, with its stated assumptions. Forecast values are not actuals.",
        parameters={
            "type": "object",
            "properties": {
                "granularity": {"type": "string", "enum": ["week", "month"]},
                "periods": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "additionalProperties": False,
        },
        allowed=_FINANCE, handler=_finance_forecast, denied_message=FINANCE_DENIED,
    ),
]
