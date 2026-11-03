"""Metric values and KPI definitions shared by the cockpit, objectives, reviews, exports and the Assistant.

Every figure is returned as a ``metric`` dict that states what kind of number it is. Actuals,
approved plans, forecasts, targets and manual values are never interchangeable, and a figure without
reliable data is returned as ``unavailable`` with the reason instead of a zero.
"""

from __future__ import annotations

from decimal import Decimal

ACTUAL = "actual"
APPROVED_PLAN = "approved_plan"
FORECAST = "forecast"
TARGET = "target"
MANUAL = "manual"

AVAILABLE = "available"
LIMITED = "limited"
UNAVAILABLE = "unavailable"

CURRENCY = "currency"
PERCENTAGE = "percentage"
COUNT = "count"
HOURS = "hours"
DAYS = "days"
RATIO = "ratio"
UNITS = (CURRENCY, PERCENTAGE, COUNT, HOURS, DAYS, RATIO)


def number(value) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return round(float(Decimal(str(value))), 2)


def metric(
    key: str,
    value,
    *,
    unit: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    note: str | None = None,
    sample: int | None = None,
    label: str | None = None,
) -> dict:
    definition = KPI_DEFINITIONS.get(key, {})
    resolved = status or (UNAVAILABLE if value is None else AVAILABLE)
    return {
        "key": key,
        "label": label or definition.get("label", key.replace("_", " ").capitalize()),
        "value": None if resolved == UNAVAILABLE else number(value),
        "unit": unit or definition.get("unit", COUNT),
        "kind": kind or definition.get("kind", ACTUAL),
        "status": resolved,
        "note": note,
        "sample": sample,
        "source": definition.get("source"),
    }


def pct(numerator, denominator) -> float | None:
    if not denominator:
        return None
    return round(float(Decimal(str(numerator)) / Decimal(str(denominator)) * 100), 2)


FINANCE_SOURCE = "Finance ledger: quote invoice and payment lines (fy_turnover_service.quote_ledger_inr)"
QTD_SOURCE = "Quote-to-Delivery report (reporting/quote_to_delivery.py, shared engineering metrics)"
HOURS_SOURCE = "Approved timesheet hours (services/actual_hours.py official rule)"
CT_SOURCE = "Control Tower open findings (control_tower_service)"
CAPACITY_SOURCE = "Capacity calendar: shifts, holidays, working days, employment dates (forecasting/capacity.day_capacity)"

KPI_DEFINITIONS: dict[str, dict] = {
    # --- Business performance (Finance view access) ---
    "invoiced_revenue": {
        "label": "Invoiced revenue", "unit": CURRENCY, "finance": True, "source": FINANCE_SOURCE,
        "definition": "Sum of invoice lines dated in the period (legacy invoiced-only quotes on their invoiced date), "
                      "in INR at each quote's locked revision rate. The FY turnover rule; payment date never moves it.",
    },
    "fy_invoiced_revenue": {
        "label": "Financial-year invoiced revenue", "unit": CURRENCY, "finance": True, "source": FINANCE_SOURCE,
        "definition": "Invoiced revenue from the start of the financial year containing the period end, to the "
                      "earlier of the period end and today.",
    },
    "collections": {
        "label": "Collections received", "unit": CURRENCY, "finance": True, "source": FINANCE_SOURCE,
        "definition": "Sum of payment lines dated in the period (legacy paid-only quotes on their paid date), in INR.",
    },
    "awarded_value": {
        "label": "Awarded project value", "unit": CURRENCY, "finance": True, "source": FINANCE_SOURCE,
        "definition": "Current revision value (INR) of active quotes whose effective quoted date falls in the period, "
                      "as the Finance dashboard counts awarded value. ProTrack records no award status, so every "
                      "active quote counts as awarded and a separate quoted (pipeline) value does not exist.",
    },
    "outstanding_receivables": {
        "label": "Outstanding receivables", "unit": CURRENCY, "finance": True, "source": FINANCE_SOURCE,
        "definition": "Invoiced minus paid, per active quote, in INR, as of today. A position, not a period total.",
    },
    "mom_growth": {
        "label": "Month-on-month growth", "unit": PERCENTAGE, "finance": True, "source": FINANCE_SOURCE,
        "definition": "Invoiced revenue of the latest month in the period against the month before it. Not shown "
                      "when the earlier month had no invoices.",
    },
    "repeat_revenue_share": {
        "label": "Repeat-business share of invoiced revenue", "unit": PERCENTAGE, "finance": True,
        "source": FINANCE_SOURCE,
        "definition": "Share of the period's invoiced revenue from customers first invoiced before the period. "
                      "Limited while recorded invoice history is shorter than a year before the period.",
    },
    "payment_lead_days": {
        "label": "Average payment lead time", "unit": DAYS, "finance": True, "source": FINANCE_SOURCE,
        "definition": "Days from invoice date to full payment for invoice lines fully paid in the period, using the "
                      "dated FIFO payment allocation (predictive/finance.paid_allocations).",
    },
    # --- Engineering operations ---
    "active_projects": {
        "label": "Active projects", "unit": COUNT, "source": QTD_SOURCE,
        "definition": "Projects in Planning, In progress or On hold today. The period does not apply.",
    },
    "projects_completed": {
        "label": "Projects completed in the period", "unit": COUNT, "source": QTD_SOURCE,
        "definition": "Status Completed with an actual completion date in the period.",
    },
    "projects_overdue": {
        "label": "Projects overdue", "unit": COUNT, "source": QTD_SOURCE,
        "definition": "Active projects past their current target date (due date, else current baseline), today.",
    },
    "projects_at_risk": {
        "label": "Projects at risk", "unit": COUNT, "source": CT_SOURCE,
        "definition": "Active projects with at least one open, not dismissed operational Control Tower risk "
                      "(schedule, effort or delivery; data-quality and predictive findings excluded).",
    },
    "projects_forecast_risk": {
        "label": "Projects with forecast risk", "unit": COUNT, "kind": FORECAST, "source": CT_SOURCE,
        "definition": "Active projects with an open predictive Control Tower finding (a Phase 7 forecast of a future "
                      "problem). Shown separately from current risks; a forecast, not an outcome.",
    },
    "projects_over_approved_hours": {
        "label": "Projects exceeding approved hours", "unit": COUNT, "source": QTD_SOURCE,
        "definition": "Active projects whose approved hours to date exceed their current approved estimate.",
    },
    "quoted_hours": {
        "label": "Original quoted hours", "unit": HOURS, "source": QTD_SOURCE,
        "definition": "Sum of quoted hours over projects that have them. Never added to approved estimates.",
    },
    "approved_estimate_hours": {
        "label": "Current approved hours", "unit": HOURS, "kind": APPROVED_PLAN, "source": QTD_SOURCE,
        "definition": "Current approved estimate (approved stage estimates with approved revisions, else milestone "
                      "planned hours). Projects with only quoted hours are excluded.",
    },
    "actual_hours": {
        "label": "Actual engineering hours", "unit": HOURS, "source": HOURS_SOURCE,
        "definition": "Approved timesheet hours. Submitted hours are provisional and excluded; draft and rejected "
                      "hours never count.",
    },
    "delivery_variance_days": {
        "label": "Average delivery variance", "unit": DAYS, "source": QTD_SOURCE,
        "definition": "Actual completion − original approved baseline, averaged over completed projects that have "
                      "an original baseline. Positive means late.",
    },
    "hour_variance_percent": {
        "label": "Engineering-hour variance", "unit": PERCENTAGE, "source": QTD_SOURCE,
        "definition": "(Σ actual − Σ current approved estimate) ÷ Σ current approved estimate over comparable "
                      "completed projects. Positive means over estimate.",
    },
    "on_time_delivery_rate": {
        "label": "On-time delivery", "unit": PERCENTAGE, "source": QTD_SOURCE,
        "definition": "Completed projects delivered on or before their original approved baseline ÷ completed "
                      "projects that have one.",
    },
    "hours_booked": {
        "label": "Approved hours booked in the period", "unit": HOURS, "source": HOURS_SOURCE,
        "definition": "Approved timesheet hours with an entry date in the period on projects in scope.",
    },
    "rework_hours": {
        "label": "Rework and engineering-change hours", "unit": HOURS, "source": HOURS_SOURCE,
        "definition": "Approved hours in the period classified as Rework, Customer Change or Internal Correction "
                      "(post-completion work types). Work before completion is not separately identifiable.",
    },
    "active_customers": {
        "label": "Active customers", "unit": COUNT, "source": QTD_SOURCE,
        "definition": "Customers with an active project today or a project completed in the period.",
    },
    # --- Workforce and capacity ---
    "active_employees": {
        "label": "Active employees", "unit": COUNT,
        "source": "HR employee records (virtual accounts excluded, hr_dashboard_service.is_active_employee)",
        "definition": "Active, not archived or deleted, not past their leaving date; virtual/system users excluded.",
    },
    "available_capacity": {
        "label": "Available engineering capacity", "unit": HOURS, "source": CAPACITY_SOURCE,
        "definition": "Hours on working days for capacity-planning users, from shift hours (else each person's "
                      "working hours per day), minus holidays, days outside employment and unavailable status.",
    },
    "allocatable_capacity": {
        "label": "Allocatable capacity", "unit": HOURS, "source": CAPACITY_SOURCE,
        "definition": "Available capacity × each person's maximum allocation percentage.",
    },
    "allocated_capacity": {
        "label": "Allocated capacity", "unit": HOURS,
        "source": "None: ProTrack has no person-to-project allocation model",
        "definition": "Not available. Approved remaining work and Phase 7 workload forecasts are shown instead.",
    },
    "approved_remaining_hours": {
        "label": "Approved remaining work", "unit": HOURS, "kind": APPROVED_PLAN,
        "source": "Shared engineering metrics (forecasting/capacity approved demand)",
        "definition": "Current approved estimate − approved hours, over open projects with an approved estimate. "
                      "Unphased; a commitment, not a schedule.",
    },
    "capacity_utilisation": {
        "label": "Recorded capacity utilisation", "unit": PERCENTAGE, "source": HOURS_SOURCE,
        "definition": "Approved project hours booked by capacity-planning users ÷ their available hours, over the "
                      "elapsed part of the period.",
    },
    "verified_skill_pool": {
        "label": "Verified skill pool", "unit": COUNT, "source": "Engineering Skills (current verified records)",
        "definition": "Active employees with at least one current verified skill.",
    },
    "skill_verified_holders": {
        "label": "Verified holders of a skill", "unit": COUNT, "source": "Engineering Skills (current verified records)",
        "definition": "Active employees with a current verified record for the chosen skill at or above the chosen "
                      "level (default 1).",
    },
    "training_completion_rate": {
        "label": "Training completion", "unit": PERCENTAGE, "source": "HR training assignments",
        "definition": "Completed training assignments ÷ all non-cancelled assignments for people in scope.",
    },
}


def definitions(keys: list[str] | None = None) -> list[dict]:
    selected = keys or list(KPI_DEFINITIONS)
    return [
        {"key": k, "label": KPI_DEFINITIONS[k]["label"], "unit": KPI_DEFINITIONS[k]["unit"],
         "kind": KPI_DEFINITIONS[k].get("kind", ACTUAL), "definition": KPI_DEFINITIONS[k]["definition"],
         "source": KPI_DEFINITIONS[k]["source"], "finance": bool(KPI_DEFINITIONS[k].get("finance"))}
        for k in selected if k in KPI_DEFINITIONS
    ]
