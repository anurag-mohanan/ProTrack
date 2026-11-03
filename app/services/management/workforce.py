"""Workforce and capacity: headcount, calendar capacity, recorded utilisation, skills and training.

Virtual/system accounts and non-capacity roles are excluded through the shared helpers
(``employee_user_clause``, ``capacity_planning_users``). Capacity is calculated per person-day with
``forecasting.capacity.day_capacity`` (shift hours, else each person's working hours per day; working
days, holidays, employment dates, availability status), so nobody is assumed to work eight hours.
Approved leave recorded in timesheets is deducted for the elapsed part of the period. Workload
forecasts are the stored Phase 7 predictions and are labelled as forecasts.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.non_productive_categories import leave_entry_clause
from app.core.team_access import resolve_team_scope, team_member_user_ids
from app.core.user_types import employee_user_clause
from app.models.models import Timesheet, TimesheetEntry, User
from app.models.skills import OPEN_PLAN_STATUSES, SkillDevelopmentPlan
from app.models.training import TrainingAssignment
from app.services.actual_hours import official_entry_clause
from app.services.forecasting.capacity import build_capacity_forecast, day_capacity
from app.services.holiday_service import load_holiday_dates
from app.services.hr_dashboard_service import is_active_employee
from app.services.kpi_participation import capacity_planning_users
from app.services.management.access import ManagementAccess
from app.services.management.filters import CockpitFilters, effective_team_ids
from app.services.management.metrics import APPROVED_PLAN, FORECAST, LIMITED, metric, number, pct
from app.services.predictive import read as predictions
from app.services.resource_shift_service import shift_hours_for_range
from app.services.skills.access import resolve_skill_access
from app.services.skills.gaps import build_gap_report

ZERO = Decimal("0")
WORKFORCE_DENIED = "Workforce figures need Resource Planning or HR view access."


def scoped_user_ids(db: Session, filters: CockpitFilters, access: ManagementAccess) -> set[UUID] | None:
    teams = effective_team_ids(db, filters, access)
    return None if teams is None else team_member_user_ids(db, list(teams))


def capacity_totals(db: Session, users: list[User], start: date, end: date, today: date) -> dict:
    """Calendar capacity for ``users`` over the window, with the elapsed part (to today) split out."""
    holidays = load_holiday_dates(db, start, end)
    shifts = shift_hours_for_range(db, [u.id for u in users], start, end)
    totals = Counter()
    sources: Counter = Counter()
    for user in users:
        used: set[str] = set()
        day = start
        while day <= end:
            values, source = day_capacity(user, day, holidays, shifts)
            if source:
                used.add(source)
            totals["available"] += values["available_hours"]
            totals["allocatable"] += values["allocatable_hours"]
            totals["holiday"] += values["holiday_hours"]
            if day <= today:
                totals["elapsed_available"] += values["available_hours"]
            day += timedelta(days=1)
        sources["mixed" if len(used) > 1 else next(iter(used)) if used else "none"] += 1
    return {"totals": totals, "sources": dict(sources), "holidays_recorded": len(holidays)}


def _hours(db: Session, user_ids: list[UUID], start: date, end: date, *conditions) -> Decimal:
    if not user_ids or end < start:
        return ZERO
    value = db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .where(Timesheet.user_id.in_(user_ids), TimesheetEntry.entry_date >= start, TimesheetEntry.entry_date <= end,
               official_entry_clause(), *conditions)
    )
    return Decimal(str(value or 0))


def _skills(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date) -> dict:
    skill_access = resolve_skill_access(db, access.user)
    if not skill_access.can_view_others:
        return {"visible": False, "reason": "Skill data needs HR or Resource Planning access to other people."}
    report = build_gap_report(db, skill_access, team_id=filters.team_id, today=today)
    rows = report["skills"]
    by_category: dict[str, dict] = {}
    for row in rows:
        cat = by_category.setdefault(row["category"] or "Uncategorised", {"skills": 0, "verified_records": 0,
                                                                        "skills_without_verified": 0})
        cat["skills"] += 1
        cat["verified_records"] += row["verified_count"]
        cat["skills_without_verified"] += int(row["verified_count"] == 0)
    return {
        "visible": True,
        "population": report["population"],
        "skills_tracked": len(rows),
        "skills_with_verified_coverage": sum(1 for r in rows if r["verified_count"]),
        "critical_gaps": [f for f in report["findings"] if f["severity"] in {"high", "medium"}][:10],
        "single_specialist_skills": sum(1 for r in rows if "single_verified_specialist" in r["flags"]),
        "distribution": [{"category": k, **v} for k, v in sorted(by_category.items())],
        "rules": report["rules"][:3],
    }


def _training(db: Session, user_ids: set[UUID] | None) -> dict:
    stmt = select(TrainingAssignment.status, func.count()).group_by(TrainingAssignment.status)
    plans = select(SkillDevelopmentPlan.status, func.count()).group_by(SkillDevelopmentPlan.status)
    if user_ids is not None:
        stmt = stmt.where(TrainingAssignment.user_id.in_(user_ids or {None}))
        plans = plans.where(SkillDevelopmentPlan.user_id.in_(user_ids or {None}))
    assignments = {status: count for status, count in db.execute(stmt).all()}
    plan_counts = {status: count for status, count in db.execute(plans).all()}
    counted = sum(c for s, c in assignments.items() if s != "cancelled")
    return {
        "assignments": assignments,
        "completion_rate": metric("training_completion_rate", pct(assignments.get("completed", 0), counted),
                                  sample=counted, note=None if counted else "No training assignments recorded."),
        "development_plans": plan_counts,
        "open_development_plans": sum(c for s, c in plan_counts.items() if s in OPEN_PLAN_STATUSES),
    }


def _bottlenecks(db: Session, access: ManagementAccess, today: date) -> dict:
    if not access.capacity:
        return {"visible": False, "reason": "Workload forecasts need Resource Planning access."}
    teams = resolve_team_scope(db, access.user)
    scope = predictions.PredictionScope(
        visibility_clause=access.visibility_clause, can_view_capacity=True,
        capacity_team_ids=None if teams is None else frozenset(teams), finance_visible=access.finance,
    )
    rows = [p for p in predictions.latest(db, scope, prediction_types=["resource_demand"])
            if p.subject_key.endswith(":4w")]
    shortage = [p for p in rows if json.loads(p.data_used_json or "{}").get("shortage")]
    by_subject = Counter(p.subject_type for p in shortage)
    return {
        "visible": True, "kind": FORECAST, "horizon_weeks": 4,
        "people_short": by_subject.get("person", 0), "teams_short": by_subject.get("team", 0),
        "skills_short": by_subject.get("skill", 0), "forecasts_considered": len(rows),
        "freshness": predictions.freshness(db, today),
        "note": "Phase 7 workload forecasts (demand against calendar capacity); forecasts, not commitments.",
    }


def build_workforce(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date | None = None) -> dict:
    if not access.workforce:
        return {"visible": False, "reason": WORKFORCE_DENIED}
    today = today or date.today()
    period = filters.period
    scope = scoped_user_ids(db, filters, access)

    employees = [u for u in db.scalars(select(User).where(User.is_deleted.is_(False), employee_user_clause())).all()
                 if is_active_employee(u, today) and (scope is None or u.id in scope)]
    capacity_users = [u for u in capacity_planning_users(db) if scope is None or u.id in scope]
    ids = [u.id for u in capacity_users]
    cap = capacity_totals(db, capacity_users, period.start, period.end, today)
    totals = cap["totals"]
    elapsed_end = min(period.end, today)
    leave = _hours(db, ids, period.start, elapsed_end, leave_entry_clause())
    project_hours = _hours(db, ids, period.start, elapsed_end, TimesheetEntry.project_id.is_not(None))
    elapsed_capacity = max(totals["elapsed_available"] - leave, ZERO)
    utilisation = pct(project_hours, elapsed_capacity) if elapsed_capacity > 0 and period.start <= today else None

    demand = None
    if access.capacity:
        teams = effective_team_ids(db, filters, access)
        demand = build_capacity_forecast(db, start=today, granularity="week", periods=1,
                                         team_ids=None if teams is None else set(teams),
                                         project_visibility_clause=access.visibility_clause, as_of=today).demand
    baseline_only = cap["sources"].get("baseline", 0) == len(capacity_users) and capacity_users
    limitations = [
        "Planned (future) leave is not recorded in ProTrack, so it is not deducted from future capacity.",
        "Non-project commitments are not recorded; utilisation counts approved project hours only.",
    ]
    if baseline_only:
        limitations.insert(0, "No shift assignments apply: every person's capacity uses their own working hours per day.")
    if not cap["holidays_recorded"]:
        limitations.insert(0, "No holidays are recorded for this period, so none are deducted.")
    kpis = [
        metric("active_employees", len(employees), note="Virtual and system accounts excluded."),
        metric("available_capacity", totals["available"] if capacity_users else None, sample=len(capacity_users),
               status=LIMITED if capacity_users and (baseline_only or not cap["holidays_recorded"]) else None),
        metric("allocatable_capacity", totals["allocatable"] if capacity_users else None, sample=len(capacity_users)),
        metric("allocated_capacity", None, note="ProTrack has no allocation model; see approved remaining work."),
        metric("approved_remaining_hours", demand.approved_remaining_hours if demand else None, kind=APPROVED_PLAN,
               sample=demand.projects_with_approved_estimate if demand else None,
               note=(f"{demand.projects_without_approved_estimate} open project(s) have no approved estimate."
                     if demand else "Needs Resource Planning access.")),
        metric("capacity_utilisation", utilisation, sample=len(capacity_users),
               note=(f"{number(project_hours)} approved project hours ÷ {number(elapsed_capacity)} available hours "
                     f"(after {number(leave)} h recorded leave), {period.start:%d %b} – {elapsed_end:%d %b %Y}.")
               if utilisation is not None else "No elapsed capacity in this period."),
    ]
    return {
        "visible": True,
        "kpis": kpis,
        "capacity": {
            "people": len(capacity_users), "hours_sources": cap["sources"], "holidays_recorded": cap["holidays_recorded"],
            "available_hours": number(totals["available"]), "allocatable_hours": number(totals["allocatable"]),
            "elapsed_available_hours": number(totals["elapsed_available"]), "recorded_leave_hours": number(leave),
            "approved_project_hours": number(project_hours),
        },
        "skills": _skills(db, access, filters, today),
        "training": _training(db, None if scope is None else scope),
        "bottlenecks": _bottlenecks(db, access, today),
        "limitations": limitations,
    }
