"""Management report exports, built from the same services, filters and redaction as the screens."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.management import actions as action_service
from app.services.management import objectives as objective_service
from app.services.management import reviews as review_service
from app.services.management.access import ManagementAccess, ManagementForbidden
from app.services.management.business import build_business
from app.services.management.customers import build_customer_table
from app.services.management.efficiency import build_efficiency
from app.services.management.filters import CockpitFilters
from app.services.management.operations import build_operations, qtd_reports
from app.services.management.workforce import build_workforce
from app.services.reporting.excel.management import SheetSpec, SheetTable

REPORTS = {
    "fy-performance": ("FY Performance", "finance"),
    "customer-contribution": ("Customer Contribution", "finance"),
    "delivery": ("Delivery Performance", None),
    "efficiency": ("Engineering Efficiency", None),
    "utilisation": ("Workforce Utilisation", "workforce"),
    "objectives": ("Strategic Objectives", None),
    "review": ("Management Review", "reviews"),
    "actions": ("Outstanding Actions", None),
}


def check_export(access: ManagementAccess, report: str) -> None:
    if report not in REPORTS:
        raise LookupError("Unknown management report")
    if not access.export:
        raise ManagementForbidden("Requires the 'export_reports' permission.")
    need = REPORTS[report][1]
    if need == "finance" and not access.finance:
        raise ManagementForbidden("This report contains Finance figures and needs Finance view access.")
    if need == "workforce" and not access.workforce:
        raise ManagementForbidden("This report needs Resource Planning or HR view access.")
    if need == "reviews" and not access.reviews:
        raise ManagementForbidden("Management reviews need organisation-wide report scope or Manage strategy.")


def _lines(filters: CockpitFilters, today: date) -> list[str]:
    p = filters.period
    lines = [f"Period: {p.label} ({p.start:%d %b %Y} - {p.end:%d %b %Y})", f"Generated: {today:%d %b %Y}"]
    lines += [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in filters.labels.items() if v and k != "period"]
    return lines


def _business_sheets(db, access, filters, today) -> list[SheetSpec]:
    body = build_business(db, access, filters, today)
    return [SheetSpec(
        "FY performance", "FY Performance", _lines(filters, today), body["kpis"],
        [SheetTable("Monthly invoiced revenue and collections (INR)", ["Month", "Invoiced", "Collected", "MoM growth %"],
                    [[m["month"], m["invoiced"], m["collected"], m["mom_growth_percent"]] for m in body["monthly"]]),
         SheetTable("Customer contribution (INR)",
                    ["Customer", "Invoiced", "Share %", "Collected", "Awarded", "Outstanding", "New / repeat"],
                    [[c["customer"], c["invoiced"], c["share_percent"], c["collected"], c["awarded"], c["outstanding"],
                      c["segment"]] for c in body["customers"]])],
        body["notes"] + [body["new_vs_repeat"]["note"]],
    )]


def _customer_sheets(db, access, filters, today) -> list[SheetSpec]:
    table = build_customer_table(db, access, filters, today)
    business = build_business(db, access, filters, today)
    headers = ["Customer", "Projects", "Active", "Completed in period", "On-time %", "Hour variance %", "Invoiced",
               "Previous period invoiced", "Trend %", "Collected", "Outstanding"]
    rows = [[r["customer"], r["projects"], r["active_projects"], r["completed_in_period"], r["on_time_rate"],
             r["hour_variance_percent"], r.get("invoiced"), r.get("previous_period_invoiced"),
             r.get("revenue_trend_percent"), r.get("collected"), r.get("outstanding")] for r in table["rows"]]
    return [SheetSpec("Customers", "Customer Contribution", _lines(filters, today),
                      [k for k in business["kpis"] if k["key"] in {"invoiced_revenue", "repeat_revenue_share"}],
                      [SheetTable("Customer performance", headers, rows)], table["notes"])]


def _delivery_sheets(db, access, filters, today) -> list[SheetSpec]:
    reports = qtd_reports(db, access, filters, today)
    ops = build_operations(db, access, filters, today, reports=reports)
    completed, active = reports
    return [
        SheetSpec("Delivery", "Delivery Performance", _lines(filters, today), ops["kpis"],
                  [SheetTable("Approved hours by stage", ["Stage", "Hours", "Projects", "Share %"],
                              [[s["label"], s["hours"], s["projects"], s["share_percent"]] for s in ops["effort_by_stage"]]),
                   SheetTable("Throughput", ["Month", "Completed"], [[t["month"], t["completed"]] for t in ops["throughput"]])],
                  ops["notes"] + [w["message"] for w in ops["warnings"]]),
        SheetSpec("Completed projects", "Projects completed in the period", _lines(filters, today), [],
                  [SheetTable("Completed", ["Project", "Customer", "Completed", "Quoted h", "Approved h", "Actual h",
                                            "Delivery variance (days)"],
                              [[r.code or r.tool_number, r.customer_name, r.actual_completion_date, r.quoted_hours,
                                r.current_estimate_hours, r.actual_hours, r.delivery_variance_days]
                               for r in completed.projects.items])]),
        SheetSpec("Active projects", "Active projects (today)", [f"As of {today:%d %b %Y}"], [],
                  [SheetTable("Active", ["Project", "Customer", "Status", "Target date", "Approved h", "Actual h",
                                         "Delivery status"],
                              [[r.code or r.tool_number, r.customer_name, r.execution_status, r.current_target_date,
                                r.current_estimate_hours, r.actual_hours, r.delivery_status]
                               for r in active.projects.items])]),
    ]


def _efficiency_sheets(db, access, filters, today, compare_by: str) -> list[SheetSpec]:
    eff = build_efficiency(db, access, filters, compare_by=compare_by, today=today)
    comparison = SheetTable(f"Completed projects by {eff['dimension_label'].lower()}",
                            [eff["dimension_label"], "Completed", "On-time %", "Avg variance (days)", "Comparable",
                             "Approved h", "Actual h", "Hour variance %", "Over estimate"],
                            [[g["label"], g["completed_projects"], g["on_time_rate"], g["average_variance_days"],
                              g["comparable_projects"], g["approved_estimate_hours"], g["actual_hours"],
                              g["hour_variance_percent"], g["projects_over_estimate"]] for g in eff["comparison"]])
    effort = [SheetTable(f"Approved hours by {name.replace('_', ' ')}", ["Group", "Hours", "Projects", "Share %"],
                         [[r["label"], r["hours"], r["projects"], r["share_percent"]] for r in rows])
              for name, rows in eff["effort"].items()]
    return [SheetSpec("Efficiency", "Engineering Efficiency", _lines(filters, today), eff["kpis"],
                      [comparison, *effort], eff["notes"] + [eff["fairness_note"]])]


def _workforce_sheets(db, access, filters, today) -> list[SheetSpec]:
    body = build_workforce(db, access, filters, today)
    cap = body["capacity"]
    return [SheetSpec("Utilisation", "Workforce Utilisation", _lines(filters, today), body["kpis"],
                      [SheetTable("Capacity", ["Measure", "Value"], [[k.replace("_", " "), v] for k, v in cap.items()]),
                       SheetTable("Training assignments", ["Status", "Count"],
                                  [[k, v] for k, v in body["training"]["assignments"].items()])],
                      body["limitations"])]


def _objective_sheets(db, access, filters, today) -> list[SheetSpec]:
    rows = objective_service.list_objectives(db, access, fy_start_year=filters.period.fy_start_year, today=today)
    return [SheetSpec("Objectives", "Strategic Objectives", _lines(filters, today), [], [SheetTable(
        "Objectives", ["Objective", "Category", "Owner", "Status", "Suggested status", "Unit", "Baseline", "Target",
                       "Target state", "Actual", "Actual kind", "Progress %", "Expected %"],
        [[o["title"], o["category"], o["owner"], o["status"], o["pace"]["suggested_status"], o["unit"],
          (o["baseline"] or {}).get("value"), (o["target"] or {}).get("value"), o["target_state"],
          (o["current"] or {}).get("value"), (o["current"] or {}).get("kind"), o["progress_percent"],
          o["pace"]["expected_percent"]] if not o["restricted"] else
         [o["title"], o["category"], o["owner"], o["status"], None, o["unit"], "restricted", "restricted",
          o["target_state"], "restricted", None, None, None] for o in rows])],
        ["Status is set by the owner; suggested status is calculated from progress and elapsed time.",
         "Restricted values need Finance or workforce access."])]


def _review_sheets(db, access, review_id: UUID) -> list[SheetSpec]:
    row = review_service.get_review(db, access, review_id)
    body = review_service.serialize(db, access, row, detail=True)
    snap = body["snapshot"]
    lines = [f"Period: {body['period']['start']} - {body['period']['end']}", f"Status: {body['status']}",
             f"Generated: {body['generated_at']} by {body['generated_by']}"]
    if body["finalised_at"]:
        lines.append(f"Finalised: {body['finalised_at']} by {body['finalised_by']}")
    sheets = [SheetSpec("Summary", body["title"], lines, [], [
        SheetTable("Executive summary (human)", ["Text"], [[body["executive_summary"] or "Not written yet"]]),
        SheetTable("Generated highlights", ["Highlight"], [[h] for h in snap.get("executive_summary", {}).get(
            "generated_highlights", [])]),
        SheetTable("Decisions", ["Decision", "By", "When"], [[d["body"] or d["summary"], d["actor"], d["created_at"]]
                                                          for d in body["decisions"]]),
        SheetTable("Actions", ["Action", "Owner", "Due", "Status"], [[a["title"], a["owner"], a["due_date"], a["status"]]
                                                                   for a in body["actions"]]),
        SheetTable("Decisions required (generated)", ["Item"], [[d["text"]] for d in snap.get("decisions_required", [])]),
    ])]
    for key, title in (("financial", "Financial"), ("delivery", "Delivery"), ("efficiency", "Efficiency"),
                       ("workforce", "Workforce")):
        section = snap.get(key) or {}
        if section.get("visible") is False:
            sheets.append(SheetSpec(title, f"{title} (restricted)", [section.get("reason", "")]))
        else:
            sheets.append(SheetSpec(title, title, lines[:1], section.get("kpis", []),
                                    notes=section.get("notes") or section.get("limitations") or []))
    customer = snap.get("customer") or {}
    money = customer.get("finance_columns")
    sheets.append(SheetSpec("Customers", "Customers", lines[:1], [], [SheetTable(
        f"Top customers ({customer.get('total', 0)} in scope)",
        ["Customer", "Projects", "Completed in period", "On-time %", "Hour variance %"] + (["Invoiced", "Outstanding"] if money else []),
        [[r["customer"], r["projects"], r["completed_in_period"], r["on_time_rate"], r["hour_variance_percent"]]
         + ([r.get("invoiced"), r.get("outstanding")] if money else []) for r in customer.get("rows", [])])],
        customer.get("notes", [])))
    sheets.append(SheetSpec("Objectives", "Objectives", lines[:1], [], [SheetTable(
        "Objectives at generation", ["Objective", "Owner", "Status", "Target", "Actual", "Progress %"],
        [["{} (restricted)".format(o["title"]) if o.get("restricted") else o["title"], o.get("owner"), o.get("status"),
          (o.get("target") or {}).get("value"), (o.get("current") or {}).get("value"), o.get("progress_percent")]
         for o in snap.get("objectives", [])])]))
    forecasts = snap.get("forecasts") or {}
    sheets.append(SheetSpec("Forecasts", "Forecasts (not actuals)", [forecasts.get("note", "")], [], [SheetTable(
        "Stored predictions at generation", ["Prediction type", "Count"],
        [[k, v] for k, v in (forecasts.get("stored_predictions") or {}).items()])]))
    return sheets


def _action_sheets(db, access, today) -> list[SheetSpec]:
    rows = action_service.list_actions(db, access, open_only=True, today=today)
    return [SheetSpec("Actions", "Outstanding Actions", [f"As of {today:%d %b %Y}"], [], [SheetTable(
        "Open actions", ["Action", "Owner", "Priority", "Due", "Status", "Overdue", "Review", "Objective", "Project"],
        [[a["title"], a["owner"], a["priority"], a["due_date"], a["status"], "Yes" if a["overdue"] else "",
          (a["review"] or {}).get("title"), (a["objective"] or {}).get("title"), (a["project"] or {}).get("code")]
         for a in rows])])]


def build_export(db: Session, access: ManagementAccess, report: str, filters: CockpitFilters, *,
                 compare_by: str = "month", review_id: UUID | None = None, today: date | None = None) -> list[SheetSpec]:
    check_export(access, report)
    today = today or date.today()
    if report == "fy-performance":
        return _business_sheets(db, access, filters, today)
    if report == "customer-contribution":
        return _customer_sheets(db, access, filters, today)
    if report == "delivery":
        return _delivery_sheets(db, access, filters, today)
    if report == "efficiency":
        return _efficiency_sheets(db, access, filters, today, compare_by)
    if report == "utilisation":
        return _workforce_sheets(db, access, filters, today)
    if report == "objectives":
        return _objective_sheets(db, access, filters, today)
    if report == "review":
        if review_id is None:
            raise ValueError("review_id is required")
        return _review_sheets(db, access, review_id)
    return _action_sheets(db, access, today)
