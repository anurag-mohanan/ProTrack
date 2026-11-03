"""Business intelligence tools: company performance, customers, operations, workforce, objectives, focus.

Every figure comes from the management services (``app.services.management``), resolved with the
caller's management access: Finance figures only with Finance access, workforce figures only with
Resource Planning or HR access, projects within the caller's visibility and report scope. Each
result names its period, separates actuals, targets and forecasts, and lists its limitations.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select

from app.models.models import Customer
from app.services.assistant.context import AssistantContext
from app.services.assistant.tools.common import clip
from app.services.assistant.types import Source, Table, ToolDenied, ToolInputError, ToolResult, ToolSpec
from app.services.management import actions as action_service
from app.services.management import objectives as objective_service
from app.services.management.access import ManagementAccess, ManagementForbidden, resolve_access
from app.services.management.business import build_business
from app.services.management.customers import build_customer_profile, visible_customer_ids
from app.services.management.efficiency import build_efficiency
from app.services.management.filters import CockpitFilters, Period, resolve_period, sub_period
from app.services.management.operations import build_operations, qtd_reports
from app.services.management.workforce import build_workforce
from app.services.finance.fy_calendar_service import company_fy_start_month
from app.services.reporting.periods import financial_year_start

COCKPIT = "/management"
PERIOD_HELP = ("Financial years run April to March and are named by their start year (2025 = April 2025 to March 2026). "
               "Quarter 1 is April-June.")


def management_access(ctx: AssistantContext) -> ManagementAccess | None:
    cached = getattr(ctx, "_management_access", False)
    if cached is not False:
        return cached
    try:
        access = resolve_access(ctx.db, ctx.user) if ctx.can_view_reports else None
    except ManagementForbidden:
        access = None
    ctx._management_access = access  # type: ignore[attr-defined]
    return access


def _need(ctx: AssistantContext, what: str | None = None) -> ManagementAccess:
    access = management_access(ctx)
    if access is None:
        raise ToolDenied("Management intelligence requires Reports access.")
    if what == "finance" and not access.finance:
        raise ToolDenied("Business performance figures require Finance access.")
    if what == "workforce" and not access.workforce:
        raise ToolDenied("Workforce figures require Resource Planning or HR access.")
    return access


def _period(ctx: AssistantContext, args: dict) -> Period:
    fy_month = company_fy_start_month(ctx.db)
    year = args.get("fy_start_year") or financial_year_start(ctx.today, fy_month).year
    if args.get("month"):
        try:
            first = date.fromisoformat(f"{args['month']}-01")
        except ValueError as exc:
            raise ToolInputError("month must be YYYY-MM.") from exc
        nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
        return resolve_period(ctx.db, start=first, end=nxt - timedelta(days=1))
    try:
        if args.get("quarter"):
            return sub_period(year, fy_month, "quarterly", args["quarter"])
        return sub_period(year, fy_month, "annual", None)
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc


def _period_data(period: Period, today: date) -> dict:
    return {**period.as_dict(), "complete": period.end < today,
            "note": None if period.end < today else f"The period is still running; actuals are to {today:%d %b %Y}."}


def _kpis(section: dict) -> list[dict]:
    return [{"metric": k["label"], "value": k["value"], "unit": k["unit"], "kind": k["kind"], "status": k["status"],
             "sample": k["sample"], "note": k["note"]} for k in section.get("kpis", [])]


def _source(period: Period, tab: str = "cockpit") -> Source:
    return Source(kind="report", ref=f"management-{tab}:{period.start}:{period.end}",
                  label=f"Management {tab} - {period.label}", route=f"{COCKPIT}?tab={tab}")


def _targets(ctx: AssistantContext, access: ManagementAccess, period: Period, keys: set[str] | None = None) -> list[dict]:
    rows = objective_service.list_objectives(ctx.db, access, fy_start_year=period.fy_start_year, today=ctx.today) \
        if period.fy_start_year else []
    out = []
    for o in rows:
        if keys is not None and o["metric_key"] not in keys:
            continue
        if o["restricted"]:
            continue
        out.append({"objective": o["title"], "status": o["status"], "target": o["target"], "baseline": o["baseline"],
                    "actual": (o["current"] or {}).get("value"), "actual_kind": (o["current"] or {}).get("kind"),
                    "progress_percent": o["progress_percent"], "expected_progress_percent": o["pace"]["expected_percent"],
                    "suggested_status": o["pace"]["suggested_status"], "target_state": o["target_state"]})
    return out


def _business_performance(ctx: AssistantContext, args: dict) -> ToolResult:
    access = _need(ctx, "finance")
    period = _period(ctx, args)
    filters = CockpitFilters(period)
    if args.get("customer"):
        filters = CockpitFilters(period, customer_id=_customer(ctx, access, args["customer"], period).id)
    body = build_business(ctx.db, access, filters, ctx.today)
    targets = _targets(ctx, access, period, {"invoiced_revenue", "collections", "awarded_value", "outstanding_receivables"})
    customers = body["customers"][: args.get("top_customers", 5)]
    limitations = list(body["notes"])
    if body["new_vs_repeat"]["status"] != "available":
        limitations.append(body["new_vs_repeat"]["note"])
    if not targets:
        limitations.append("No approved financial objective covers this period, so there is no target to compare with.")
    return ToolResult(
        data={"period": _period_data(period, ctx.today), "currency": "INR", "value_kind": "actual",
              "kpis": _kpis(body), "monthly": body["monthly"], "top_customers": customers, "targets": targets,
              "targets_note": "Targets are approved goals, not results; compare them with the actuals, never add them."},
        record_count=body["quotes_in_scope"],
        sources=[_source(period)],
        tables=[Table(title=f"Customer contribution - {period.label}",
                      columns=["Customer", "Invoiced (INR)", "Share %", "Collected (INR)", "Outstanding (INR)"],
                      rows=[[c["customer"], c["invoiced"], c["share_percent"], c["collected"], c["outstanding"]]
                            for c in customers])] if customers else [],
        limitations=limitations,
    )


def _customer(ctx: AssistantContext, access: ManagementAccess, name: str, period: Period) -> Customer:
    ids = visible_customer_ids(ctx.db, access, CockpitFilters(period))
    matches = ctx.db.scalars(select(Customer).where(
        Customer.id.in_(ids), func.lower(Customer.name).like(f"%{name.strip().lower()}%"))).all() if ids else []
    if not matches:
        raise ToolInputError(f"No customer '{clip(name, 40)}' was found among the customers you can access.")
    exact = [c for c in matches if c.name.lower() == name.strip().lower()]
    if len(exact) == 1:
        return exact[0]
    if len(matches) > 1:
        raise ToolInputError(f"'{clip(name, 40)}' matches several customers: "
                             f"{', '.join(c.name for c in matches[:5])}.")
    return matches[0]


def _customer_performance(ctx: AssistantContext, args: dict) -> ToolResult:
    access = _need(ctx)
    period = _period(ctx, args)
    customer = _customer(ctx, access, args["customer"], period)
    profile = build_customer_profile(ctx.db, access, CockpitFilters(period), customer.id, ctx.today)
    limitations = [n["reason"] for n in profile["not_assessable"]] + profile["notes"]
    return ToolResult(
        data={"period": _period_data(period, ctx.today), "customer": profile["customer"]["name"],
              "projects": {k: profile["projects"][k] for k in ("total", "by_status", "by_classification")},
              "delivery_in_period": profile["delivery"]["period"], "delivery_history": profile["delivery"]["history"],
              "finance": profile["finance"], "finance_visible": profile["finance_visible"],
              "observed_signals": profile["signals"], "trend_by_financial_year": profile["trend"],
              "forecasts": profile["forecasts"],
              "kinds_note": "Signals are observed history; forecasts are predictions and are listed separately."},
        record_count=profile["projects"]["total"],
        sources=[Source(kind="report", ref=f"management-customer:{customer.id}", label=f"Customer profile - {customer.name}",
                        route=f"{COCKPIT}?tab=customers&customer={customer.id}")],
        tables=[Table(title=f"{customer.name} by financial year",
                      columns=["Financial year", "Completed", "On-time %", "Hour variance %", "Invoiced (INR)"],
                      rows=[[t["label"], t["completed_projects"], t["on_time_rate"], t["hour_variance_percent"], t["invoiced"]]
                            for t in profile["trend"]])],
        limitations=limitations,
    )


def _engineering_operations(ctx: AssistantContext, args: dict) -> ToolResult:
    access = _need(ctx)
    period = _period(ctx, args)
    filters = CockpitFilters(period)
    reports = qtd_reports(ctx.db, access, filters, ctx.today)
    ops = build_operations(ctx.db, access, filters, ctx.today, reports=reports)
    eff = build_efficiency(ctx.db, access, filters, compare_by=args.get("compare_by", "month"), today=ctx.today,
                           reports=reports)
    stages = ops["effort_by_stage"]
    limitations = [w["message"] for w in ops["warnings"]][:6] + ops["notes"] + [eff["fairness_note"]]
    return ToolResult(
        data={"period": _period_data(period, ctx.today), "kpis": _kpis(ops),
              "completed_in_period": ops["completed"], "active_today": ops["active"],
              "effort_by_stage": stages, "throughput": ops["throughput"],
              "comparison": {"by": eff["dimension_label"], "groups": eff["comparison"][:12]},
              "kinds_note": "Completed figures are historical actuals; active figures are today's position; "
                            "'projects_forecast_risk' counts predictions, not outcomes."},
        record_count=ops["completed"]["projects"] + ops["active"]["projects"],
        sources=[_source(period), _source(period, "efficiency")],
        tables=[Table(title=f"Approved hours by stage - {period.label}", columns=["Stage", "Hours", "Projects", "Share %"],
                      rows=[[s["label"], s["hours"], s["projects"], s["share_percent"]] for s in stages])] if stages else [],
        limitations=limitations,
    )


def _workforce_summary(ctx: AssistantContext, args: dict) -> ToolResult:
    access = _need(ctx, "workforce")
    period = _period(ctx, args)
    body = build_workforce(ctx.db, access, CockpitFilters(period), ctx.today)
    return ToolResult(
        data={"period": _period_data(period, ctx.today), "kpis": _kpis(body), "capacity": body["capacity"],
              "skills": body["skills"], "training": body["training"], "bottleneck_forecasts": body["bottlenecks"]},
        record_count=body["capacity"]["people"],
        sources=[_source(period)],
        limitations=body["limitations"],
    )


def _strategic_objectives(ctx: AssistantContext, args: dict) -> ToolResult:
    access = _need(ctx)
    period = _period(ctx, args)
    rows = objective_service.list_objectives(ctx.db, access, fy_start_year=period.fy_start_year, today=ctx.today)
    if args.get("behind_plan_only"):
        rows = [o for o in rows if o["pace"]["suggested_status"] in {"at_risk", "delayed"}
                or o["status"] in {"at_risk", "delayed"}]
    items = [{"objective": o["title"], "category": o["category"], "owner": o["owner"], "status": o["status"],
              "suggested_status": o["pace"]["suggested_status"], "restricted": o["restricted"],
              "target": o["target"], "baseline": o["baseline"], "actual": o["current"],
              "progress_percent": o["progress_percent"], "expected_progress_percent": o["pace"]["expected_percent"],
              "target_state": o["target_state"], "measurement": o["measurement"]} for o in rows]
    limitations = ["'status' is set by the owner; 'suggested_status' is calculated from progress against elapsed time."]
    if any(o["restricted"] for o in rows):
        limitations.append("Some objective values are hidden because they need Finance or workforce access.")
    if any(o["target_state"] == "proposed" for o in rows):
        limitations.append("Some targets are proposed and not yet approved.")
    return ToolResult(
        data={"period": _period_data(period, ctx.today), "objectives": items},
        record_count=len(items),
        sources=[Source(kind="report", ref=f"management-objectives:{period.fy_start_year}",
                        label=f"Strategic objectives - {period.label}", route=f"{COCKPIT}?tab=objectives")],
        tables=[Table(title="Objectives", columns=["Objective", "Status", "Suggested", "Progress %", "Expected %"],
                      rows=[[i["objective"], i["status"], i["suggested_status"], i["progress_percent"],
                             i["expected_progress_percent"]] for i in items])] if items else [],
        limitations=limitations,
    )


def _management_focus(ctx: AssistantContext, args: dict) -> ToolResult:
    access = _need(ctx)
    fy_month = company_fy_start_month(ctx.db)
    month_start = date(ctx.today.year, ctx.today.month, 1)
    period = resolve_period(ctx.db, start=month_start, end=ctx.today)
    fy = sub_period(financial_year_start(ctx.today, fy_month).year, fy_month, "annual", None)
    items: list[dict] = []
    for o in objective_service.list_objectives(ctx.db, access, fy_start_year=fy.fy_start_year, today=ctx.today):
        if o["pace"]["suggested_status"] in {"at_risk", "delayed"} and o["status"] not in {"completed", "cancelled"}:
            items.append({"area": "objective", "kind": "target_vs_actual", "item": o["title"],
                          "detail": f"Progress {o['progress_percent']}% against {o['pace']['expected_percent']}% expected."})
    action_rows = action_service.list_actions(ctx.db, access, open_only=True, today=ctx.today)
    for a in action_rows:
        if a["overdue"] or a["status"] == "blocked":
            items.append({"area": "action", "kind": "actual", "item": a["title"],
                          "detail": "Blocked" if a["status"] == "blocked" else f"Overdue since {a['due_date']}"})
    ops = build_operations(ctx.db, access, CockpitFilters(period), ctx.today)
    active = ops["active"]
    if active["overdue"]:
        items.append({"area": "delivery", "kind": "actual", "item": f"{active['overdue']} active project(s) past their target date",
                      "detail": None})
    if active["at_risk"]:
        items.append({"area": "delivery", "kind": "actual", "item": f"{active['at_risk']} project(s) with open risks",
                      "detail": f"By severity: {active['risk_by_severity']}"})
    if active["forecast_risk"]:
        items.append({"area": "delivery", "kind": "forecast", "item": f"{active['forecast_risk']} project(s) with predicted risks",
                      "detail": "Phase 7 predictions; not outcomes."})
    limitations = ["Items are drawn from objectives, management actions, open projects and Control Tower findings."]
    if access.finance:
        business = build_business(ctx.db, access, CockpitFilters(fy), ctx.today)
        overdue_customers = [c for c in business["customers"] if (c["outstanding"] or 0) > 0][:3]
        for c in overdue_customers:
            items.append({"area": "receivables", "kind": "actual", "item": f"{c['customer']}: INR {c['outstanding']:,.0f} outstanding",
                          "detail": "As of today."})
    else:
        limitations.append("Finance items are not included: they need Finance access.")
    if access.capacity:
        bottlenecks = build_workforce(ctx.db, access, CockpitFilters(period), ctx.today)["bottlenecks"]
        if bottlenecks.get("visible") and (bottlenecks["people_short"] or bottlenecks["teams_short"]):
            items.append({"area": "workforce", "kind": "forecast",
                          "item": f"Forecast shortage: {bottlenecks['people_short']} people, {bottlenecks['teams_short']} teams",
                          "detail": "Next four weeks; Phase 7 workload forecast."})
    return ToolResult(
        data={"period": _period_data(period, ctx.today), "financial_year": fy.as_dict(), "focus_items": items,
              "kinds_note": "'actual' items are recorded facts, 'forecast' items are predictions, "
                            "'target_vs_actual' compares an approved target with the actual."},
        record_count=len(items),
        sources=[_source(period), Source(kind="report", ref="management-actions", label="Management actions",
                                         route=f"{COCKPIT}?tab=actions")],
        tables=[Table(title="Focus items", columns=["Area", "Kind", "Item", "Detail"],
                      rows=[[i["area"], i["kind"], i["item"], i["detail"]] for i in items])] if items else [],
        limitations=limitations,
    )


_PERIOD_PROPS = {
    "fy_start_year": {"type": "integer", "minimum": 2000, "maximum": 2100,
                      "description": "Start year of the financial year. Defaults to the current one."},
    "quarter": {"type": "integer", "minimum": 1, "maximum": 4, "description": "Financial-year quarter."},
    "month": {"type": "string", "maxLength": 7, "description": "A calendar month, YYYY-MM (overrides year/quarter)."},
}
def _REPORTS(ctx: AssistantContext) -> bool:
    return management_access(ctx) is not None


def _FINANCE(ctx: AssistantContext) -> bool:
    access = management_access(ctx)
    return access is not None and access.finance


def _WORKFORCE(ctx: AssistantContext) -> bool:
    access = management_access(ctx)
    return access is not None and access.workforce

SPECS = [
    ToolSpec(
        name="get_business_performance",
        module="management",
        description=("Company business performance for a period: invoiced revenue, collections, awarded value, "
                     "outstanding receivables, month-on-month growth, customer contribution, plus any approved financial "
                     "targets with progress. " + PERIOD_HELP),
        parameters={"type": "object", "properties": {
            **_PERIOD_PROPS,
            "customer": {"type": "string", "maxLength": 80, "description": "Limit to one customer (name)."},
            "top_customers": {"type": "integer", "minimum": 1, "maximum": 15},
        }, "additionalProperties": False},
        allowed=_FINANCE, handler=_business_performance,
        denied_message="Business performance figures require Finance access.",
    ),
    ToolSpec(
        name="get_customer_performance",
        module="management",
        description=("One customer's profile: projects, delivery performance, quoted vs actual hours, revenue and "
                     "collections (Finance users only), observed signals and forecasts listed separately. " + PERIOD_HELP),
        parameters={"type": "object", "properties": {
            "customer": {"type": "string", "maxLength": 80}, **_PERIOD_PROPS,
        }, "required": ["customer"], "additionalProperties": False},
        allowed=_REPORTS, handler=_customer_performance, denied_message="Customer intelligence requires Reports access.",
    ),
    ToolSpec(
        name="get_engineering_operations",
        module="management",
        description=("Engineering operations for a period: completed vs active projects, overdue and at-risk projects, "
                     "quoted/approved/actual hours, delivery variance, approved hours by stage, throughput and a "
                     "comparison by month, quarter, customer, classification, team or project manager. " + PERIOD_HELP),
        parameters={"type": "object", "properties": {
            **_PERIOD_PROPS,
            "compare_by": {"type": "string", "enum": ["month", "quarter", "financial_year", "customer", "classification",
                                                      "team", "project_manager"]},
        }, "additionalProperties": False},
        allowed=_REPORTS, handler=_engineering_operations, denied_message="Engineering operations require Reports access.",
    ),
    ToolSpec(
        name="get_workforce_summary",
        module="management",
        description=("Workforce for a period: active employees, calendar capacity, utilisation, skills coverage, training "
                     "and forecast workload bottlenecks. " + PERIOD_HELP),
        parameters={"type": "object", "properties": {**_PERIOD_PROPS}, "additionalProperties": False},
        allowed=_WORKFORCE, handler=_workforce_summary,
        denied_message="Workforce figures require Resource Planning or HR access.",
    ),
    ToolSpec(
        name="get_strategic_objectives",
        module="management",
        description=("Strategic objectives for a financial year with target, baseline, actual, progress, expected progress "
                     "and status. Set behind_plan_only to list objectives at risk or delayed. " + PERIOD_HELP),
        parameters={"type": "object", "properties": {
            "fy_start_year": _PERIOD_PROPS["fy_start_year"], "behind_plan_only": {"type": "boolean"},
        }, "additionalProperties": False},
        allowed=_REPORTS, handler=_strategic_objectives, denied_message="Strategic objectives require Reports access.",
    ),
    ToolSpec(
        name="get_management_focus",
        module="management",
        description=("What management should look at now: objectives behind plan, overdue or blocked management actions, "
                     "overdue and at-risk projects, largest outstanding receivables (Finance users) and forecast "
                     "workload shortages, each labelled actual, forecast or target-vs-actual."),
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        allowed=_REPORTS, handler=_management_focus, denied_message="Management focus requires Reports access.",
    ),
]
