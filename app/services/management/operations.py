"""Engineering operations: active and completed projects, hours, delivery and risk.

Built on the Quote-to-Delivery report (the shared engineering metrics) for both populations, which
are never mixed: *completed in the period* is historical, *active* is the position today. Risk comes
from open Control Tower findings. Hours booked in the period use the official approved-hours rule.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.control_tower import OPEN_FINDING_STATUSES, ProjectRiskFinding
from app.models.enums import PostCompletionWorkType
from app.models.models import Milestone, Project, TaskType, TimesheetEntry
from app.services.actual_hours import official_entry_clause
from app.services.control_tower_service import TRIAGE_DISMISSED
from app.services.delivery_variance_service import stage_label
from app.services.management.access import ManagementAccess
from app.services.management.filters import CockpitFilters, performance_filters, project_conditions
from app.services.management.metrics import FORECAST, LIMITED, metric, number, pct
from app.services.reporting.quote_to_delivery import QtdFilters, QtdTableOptions, build_quote_to_delivery

ZERO = Decimal("0")
REWORK_TYPES = (
    PostCompletionWorkType.rework,
    PostCompletionWorkType.customer_change,
    PostCompletionWorkType.internal_correction,
)
BULK_DATE_SHARE = 0.8
BULK_DATE_MIN = 5


def qtd_reports(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date):
    base = performance_filters(db, filters, access)
    options = QtdTableOptions(page_size=None)
    completed = build_quote_to_delivery(db, QtdFilters(base, "completed", filters.classification), options, today=today)
    active = build_quote_to_delivery(db, QtdFilters(base, "active", filters.classification), options, today=today)
    return completed, active


def booked_hours(db: Session, access: ManagementAccess, filters: CockpitFilters, dimension: str) -> list[dict]:
    """Approved hours with an entry date in the period on in-scope projects, grouped by one dimension."""
    columns = {
        "stage": Milestone.project_stage,
        "task_type": TaskType.name,
        "customer": Project.customer_id,
        "classification": Project.project_classification,
        "month": TimesheetEntry.entry_date,
        "post_completion": TimesheetEntry.post_completion_type,
    }
    key = columns[dimension]
    stmt = (
        select(key, TimesheetEntry.project_id, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .select_from(TimesheetEntry)
        .join(Project, Project.id == TimesheetEntry.project_id)
    )
    if dimension == "stage":
        stmt = stmt.outerjoin(Milestone, and_(Milestone.id == TimesheetEntry.milestone_id,
                                              Milestone.project_id == TimesheetEntry.project_id))
    elif dimension == "task_type":
        stmt = stmt.outerjoin(TaskType, TaskType.id == TimesheetEntry.task_type_id)
    stmt = stmt.where(
        official_entry_clause(),
        TimesheetEntry.entry_date >= filters.period.start,
        TimesheetEntry.entry_date <= filters.period.end,
        *project_conditions(db, filters, access),
    ).group_by(key, TimesheetEntry.project_id)
    hours_by: dict[object, Decimal] = defaultdict(lambda: ZERO)
    projects_by: dict[object, set] = defaultdict(set)
    for value, project_id, hours in db.execute(stmt).all():
        if dimension == "month":
            value = value.strftime("%Y-%m")
        hours_by[value] += Decimal(str(hours or 0))
        projects_by[value].add(project_id)
    total = sum(hours_by.values(), ZERO)
    out = [
        {"key": getattr(value, "value", None) or (str(value) if value is not None else "none"),
         "label": _label(dimension, value), "hours": number(hours), "projects": len(projects_by[value]),
         "share_percent": pct(hours, total)}
        for value, hours in hours_by.items()
    ]
    out.sort(key=lambda row: (row["key"] if dimension == "month" else -(row["hours"] or 0), row["label"]))
    return out


def _label(dimension: str, value) -> str:
    if value is None:
        return {"stage": "Not linked to a staged milestone", "task_type": "No task type",
                "post_completion": "Original contracted work", "customer": "No customer"}.get(dimension, "Not set")
    if dimension == "stage":
        return stage_label(value) or str(getattr(value, "value", value))
    if dimension in {"classification", "post_completion"}:
        return str(getattr(value, "value", value)).replace("_", " ").capitalize()
    return str(value)


def risk_projects(db: Session, project_ids: list[UUID]) -> dict[str, dict[UUID, Counter]]:
    """Open, not dismissed findings per project: operational risks and predictive findings, separately."""
    out: dict[str, dict[UUID, Counter]] = {"operational": defaultdict(Counter), "predictive": defaultdict(Counter)}
    if not project_ids:
        return out
    rows = db.execute(
        select(ProjectRiskFinding.project_id, ProjectRiskFinding.source, ProjectRiskFinding.severity)
        .where(
            ProjectRiskFinding.project_id.in_(project_ids),
            ProjectRiskFinding.status.in_(OPEN_FINDING_STATUSES),
            ProjectRiskFinding.category != "data_quality",
            or_(ProjectRiskFinding.triage_status.is_(None), ProjectRiskFinding.triage_status != TRIAGE_DISMISSED),
        )
    ).all()
    for project_id, source, severity in rows:
        out["predictive" if source == "predictive" else "operational"][project_id][severity] += 1
    return out


def bulk_completion_warning(rows) -> dict | None:
    """Completion dates shared by most completed projects look like a bulk data update, not delivery."""
    dates = [r.actual_completion_date for r in rows if r.actual_completion_date]
    if len(dates) < BULK_DATE_MIN:
        return None
    day, count = Counter(dates).most_common(1)[0]
    if count / len(dates) < BULK_DATE_SHARE:
        return None
    return {"code": "bulk_completion_dates",
            "message": f"{count} of {len(dates)} completed projects share the completion date {day:%d %b %Y}. "
                       "These look like a bulk data update rather than delivery dates, so throughput and "
                       "delivery comparisons for this period are limited."}


def build_operations(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date | None = None,
                     reports=None) -> dict:
    today = today or date.today()
    completed, active = reports or qtd_reports(db, access, filters, today)
    cs, as_ = completed.summary, active.summary
    hist, oper = completed.delivery.historical, active.delivery.operational
    active_ids = [row.project_id for row in active.projects.items]
    risks = risk_projects(db, active_ids)
    at_risk = risks["operational"]
    forecast_risk = risks["predictive"]
    bulk = bulk_completion_warning(completed.projects.items)
    limited = LIMITED if bulk else None

    throughput: dict[str, int] = defaultdict(int)
    for row in completed.projects.items:
        if row.actual_completion_date:
            throughput[row.actual_completion_date.strftime("%Y-%m")] += 1
    variance_pct = pct(cs.variance_hours, cs.comparable_estimate_hours) if cs.variance_hours is not None else None
    on_time = pct(hist.on_or_before_baseline, hist.eligible_projects) if hist.eligible_projects else None

    def hours_block(summary) -> dict:
        return {
            "quoted_hours": metric("quoted_hours", summary.quoted_hours_total if summary.projects_with_quoted_hours else None,
                                   sample=summary.projects_with_quoted_hours),
            "approved_estimate_hours": metric("approved_estimate_hours",
                                              summary.current_estimate_total if summary.projects_with_current_estimate else None,
                                              sample=summary.projects_with_current_estimate),
            "actual_hours": metric("actual_hours", summary.actual_hours_total if summary.projects_with_actual_hours else None,
                                   sample=summary.projects_with_actual_hours),
            "comparable_projects": summary.comparable_projects,
            "projects_over_estimate": summary.projects_over_estimate,
            "projects_not_comparable": summary.projects_not_comparable,
        }

    rework = [r for r in booked_hours(db, access, filters, "post_completion") if r["key"] in {t.value for t in REWORK_TYPES}]
    kpis = [
        metric("active_projects", as_.eligible_projects, note="Today; the period does not apply."),
        metric("projects_completed", cs.eligible_projects, status=limited, note=bulk["message"] if bulk else None),
        metric("projects_overdue", oper.projects_past_current_target,
               note=f"{oper.projects_without_current_target} active project(s) have no target date."
               if oper.projects_without_current_target else None),
        metric("projects_at_risk", len(at_risk),
               note=f"{sum(1 for c in at_risk.values() if c['critical'] or c['high'])} with a high or critical risk."),
        metric("projects_over_approved_hours", as_.projects_over_estimate, sample=as_.comparable_projects,
               note=f"{as_.projects_not_comparable} active project(s) have no approved estimate or known hours."),
        metric("delivery_variance_days", hist.average_variance_days, sample=hist.eligible_projects, status=limited if hist.eligible_projects else None,
               note=None if hist.eligible_projects else "No completed project in the period has an original baseline."),
        metric("hour_variance_percent", variance_pct, sample=cs.comparable_projects,
               note=None if cs.comparable_projects else "No completed project has both an approved estimate and actual hours."),
        metric("on_time_delivery_rate", on_time, sample=hist.eligible_projects, status=limited if on_time is not None else None),
        metric("rework_hours", sum((r["hours"] or 0 for r in rework), 0) if rework else None,
               note=None if rework else "No approved hours are classified as rework or engineering change in the period."),
        metric("projects_forecast_risk", len(forecast_risk), kind=FORECAST),
    ]
    return {
        "kpis": kpis,
        "completed": {
            "population": completed.population.date_basis,
            "projects": cs.eligible_projects,
            "hours": hours_block(cs),
            "delivery": {
                "eligible_projects": hist.eligible_projects,
                "on_or_before_baseline": hist.on_or_before_baseline,
                "after_baseline": hist.after_baseline,
                "average_variance_days": hist.average_variance_days,
                "median_variance_days": hist.median_variance_days,
                "excluded_without_original_baseline": hist.excluded_baseline_unverified + hist.excluded_due_date_only
                + hist.excluded_no_reference,
                "completed_without_completion_date": hist.completed_without_completion_date,
            },
        },
        "active": {
            "population": active.population.date_basis,
            "projects": as_.eligible_projects,
            "hours": hours_block(as_),
            "overdue": oper.projects_past_current_target,
            "with_overdue_milestones": oper.projects_with_overdue_milestones,
            "without_target": oper.projects_without_current_target,
            "at_risk": len(at_risk),
            "risk_by_severity": dict(sum((c for c in at_risk.values()), Counter())),
            "forecast_risk": len(forecast_risk),
        },
        "effort_by_stage": booked_hours(db, access, filters, "stage"),
        "throughput": [{"month": k, "completed": v} for k, v in sorted(throughput.items())],
        "warnings": [w.model_dump() for w in completed.warnings + active.warnings] + ([bulk] if bulk else []),
        "notes": [
            "Completed figures cover projects completed in the period; active figures are today's open projects.",
            "Active-project hours are consumption to date against the approved estimate, not a forecast.",
            "Project manager filter uses the project's design leader.",
        ],
    }
