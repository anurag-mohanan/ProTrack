"""Engineering efficiency analytics: quoted, approved and actual hours, effort mix and delivery.

Completed-project comparisons come from the Quote-to-Delivery report rows (shared engineering
metrics), grouped by one dimension at a time. Effort mix is approved hours booked in the period
(official hours rule). Results describe projects and portfolios, never individual designers: raw
hours or project counts say nothing fair about a person without complexity, scope, assignment and
leave, and individual evaluation stays in the performance-review workflow.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Customer, Project, Team
from app.services.management.access import ManagementAccess
from app.services.management.customers import DeliveryStats
from app.services.management.filters import CockpitFilters
from app.services.management.metrics import metric, pct
from app.services.management.operations import REWORK_TYPES, booked_hours, qtd_reports
from app.services.reporting.periods import financial_year_label, financial_year_start

DIMENSIONS = {
    "month": "Month",
    "quarter": "Quarter",
    "financial_year": "Financial year",
    "customer": "Customer",
    "classification": "Project classification",
    "team": "Team",
    "project_manager": "Project manager (design leader)",
}
FAIRNESS_NOTE = (
    "Comparisons describe projects and portfolios. Designers are not compared: raw hours and project counts "
    "ignore complexity, scope, assignments and leave, and individual evaluation belongs to the performance-review "
    "workflow. Project-manager rows show the portfolio of projects they lead, with its classification mix."
)


def _quarter(day: date, fy_month: int) -> tuple[str, str]:
    start = financial_year_start(day, fy_month)
    months = (day.year - start.year) * 12 + day.month - start.month
    q = months // 3 + 1
    return f"{start.year}-Q{q}", f"Q{q} {financial_year_label(day, fy_month)}"


def _keyer(db: Session, dimension: str, rows, fy_month: int):
    ids = [r.project_id for r in rows]
    projects = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_(ids))).all()} if ids else {}
    team_ids = {p.team_id for p in projects.values() if p.team_id}
    teams = {t.id: t.name for t in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()} if team_ids else {}

    def key(row) -> tuple[str, str]:
        day = row.actual_completion_date
        project = projects.get(row.project_id)
        if dimension == "month":
            return day.strftime("%Y-%m"), day.strftime("%b %Y")
        if dimension == "quarter":
            return _quarter(day, fy_month)
        if dimension == "financial_year":
            start = financial_year_start(day, fy_month)
            return str(start.year), financial_year_label(day, fy_month)
        if dimension == "customer":
            return str(project.customer_id) if project else "none", row.customer_name or "No customer"
        if dimension == "classification":
            return row.classification or "unclassified", row.classification_label or "Unclassified"
        if dimension == "team":
            team_id = project.team_id if project else None
            return (str(team_id), teams.get(team_id, "Unknown team")) if team_id else ("none", "No team")
        lead = project.design_leader_id if project else None
        return (str(lead), row.design_leader_name or "Unknown") if lead else ("none", "No design leader")

    return key, projects


def _customer_labels(db: Session, rows: list[dict]) -> list[dict]:
    ids = []
    for row in rows:
        try:
            ids.append(UUID(row["key"]))
        except ValueError:
            continue
    names = {str(c.id): c.name for c in db.scalars(select(Customer).where(Customer.id.in_(ids))).all()} if ids else {}
    for row in rows:
        row["label"] = names.get(row["key"], row["label"])
    return rows


def build_efficiency(db: Session, access: ManagementAccess, filters: CockpitFilters, *, compare_by: str = "month",
                     today: date | None = None, reports=None) -> dict:
    if compare_by not in DIMENSIONS:
        raise ValueError(f"compare_by must be one of: {', '.join(DIMENSIONS)}")
    today = today or date.today()
    completed, active = reports or qtd_reports(db, access, filters, today)
    rows = [r for r in completed.projects.items if r.actual_completion_date]
    key, projects = _keyer(db, compare_by, rows, filters.period.fy_start_month)
    groups: dict[str, DeliveryStats] = defaultdict(DeliveryStats)
    labels: dict[str, str] = {}
    mix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        k, label = key(row)
        groups[k].add(row)
        labels[k] = label
        mix[k][row.classification_label or "Unclassified"] += 1
    comparison = [{"key": k, "label": labels[k], **stats.read(), "classification_mix": dict(mix[k])}
                  for k, stats in groups.items()]
    ordered = compare_by in {"month", "quarter", "financial_year"}
    comparison.sort(key=lambda r: r["key"] if ordered else (-r["completed_projects"], r["label"].lower()))

    total = DeliveryStats()
    for row in rows:
        total.add(row)
    summary = total.read()
    qa = summary["quoted_vs_actual"]
    effort = {dim: booked_hours(db, access, filters, dim)
              for dim in ("classification", "customer", "stage", "task_type", "month")}
    effort["customer"] = _customer_labels(db, effort["customer"])
    rework = [r for r in booked_hours(db, access, filters, "post_completion") if r["key"] in {t.value for t in REWORK_TYPES}]
    kpis = [
        metric("quoted_hours", qa["quoted_hours"], sample=qa["projects"],
               label="Quoted hours (completed projects with actual hours)"),
        metric("actual_hours", qa["actual_hours"], sample=qa["projects"], label="Actual hours on those projects"),
        metric("hour_variance_percent", qa["variance_percent"], sample=qa["projects"],
               label="Actual vs quoted hours", note="Positive means more hours than quoted."),
        metric("approved_estimate_hours", summary["approved_estimate_hours"], sample=summary["comparable_projects"],
               label="Approved hours (comparable completed projects)"),
        metric("hour_variance_percent", summary["hour_variance_percent"], sample=summary["comparable_projects"]),
        metric("on_time_delivery_rate", summary["on_time_rate"], sample=summary["delivery_evaluable"]),
        metric("delivery_variance_days", summary["average_variance_days"], sample=summary["delivery_evaluable"]),
        metric("projects_completed", summary["completed_projects"]),
        metric("rework_hours", sum((r["hours"] or 0 for r in rework), 0) if rework else None,
               note=None if rework else "No approved hours classified as rework or engineering change in the period."),
    ]
    for i, item in enumerate(kpis):
        item["key"] = f"{item['key']}:{i}" if any(o["key"] == item["key"] for o in kpis[:i]) else item["key"]
    return {
        "compare_by": compare_by,
        "dimension_label": DIMENSIONS[compare_by],
        "dimensions": [{"value": k, "label": v} for k, v in DIMENSIONS.items()],
        "kpis": kpis,
        "comparison": comparison,
        "effort": effort,
        "rework": rework,
        "active_consumption": {
            "projects": active.summary.eligible_projects,
            "comparable": active.summary.comparable_projects,
            "approved_estimate_hours": active.summary.comparable_estimate_hours,
            "actual_hours": active.summary.comparable_actual_hours,
            "utilisation_percent": active.summary.utilization_percent,
            "note": "Open projects: approved hours consumed to date against the approved estimate, not a forecast.",
        },
        "throughput": [{"key": r["key"], "label": r["label"], "completed": r["completed_projects"]}
                       for r in sorted(comparison, key=lambda r: r["key"])] if compare_by == "month" else None,
        "warnings": [w.model_dump() for w in completed.warnings],
        "fairness_note": FAIRNESS_NOTE,
        "notes": [
            "Effort mix is approved hours booked in the period; comparisons cover projects completed in the period.",
            "Rework and engineering-change effort is identifiable only for hours booked after completion "
            "(post-completion work types).",
            f"{len(projects)} completed project(s) in scope.",
            "Quoted hours are the original commercial figure; approved hours are the current approved estimate. "
            f"{pct(qa['projects'], summary['completed_projects']) or 0}% of completed projects have quoted and actual hours.",
        ],
    }
