"""HR Dashboard aggregates computed from employee, onboarding, exit, shift and review records.

Every count is backed by a named *segment* (a set of user ids), and the drilldown
endpoint returns exactly the users in that segment — so a card number always
matches the list it opens. Metrics without a reliable source field (birthdays,
probation, contract end, work location) are intentionally not produced.
"""

from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.it_operations import (
    PROVISIONING_TERMINAL,
    ItProvisioningRequest,
    WorkstationPackage,
    WorkstationPackageAssignment,
)
from app.core.user_types import employee_user_clause
from app.models.models import (
    ExitInterview,
    OnboardingChecklist,
    OnboardingChecklistItem,
    OrgDepartment,
    PerformanceReviewCycle,
    PerformanceReviewSheet,
    User,
)
from app.models.resource_shifts import ResourceShift
from app.services import onboarding_task_service as onboarding_tasks
from app.services import resource_shift_service
from app.services.hr_process_audit_service import INCOMPLETE_ONBOARDING_SLA_DAYS
from app.services.performance_review_service import current_review_year
from app.services.review_engine_service import STAGE_ACKNOWLEDGED, STAGE_FINAL

STATUS_OPTIONS = ("active", "inactive", "all")
TENURE_BUCKETS = (
    ("lt_6m", "< 6 months", 0, 6),
    ("6_12m", "6–12 months", 6, 12),
    ("1_2y", "1–2 years", 12, 24),
    ("2_5y", "2–5 years", 24, 60),
    ("5y_plus", "5+ years", 60, None),
)
REVIEW_STAGE_LABELS = {
    "self": "Self review",
    "manager": "Manager review",
    "calibration": "Calibration",
    "final": "Finalized",
    "acknowledged": "Acknowledged",
}
EMPLOYMENT_TYPE_LABELS = {
    "full_time": "Full time",
    "part_time": "Part time",
    "contract": "Contract",
    "intern": "Intern",
}
NONE_KEY = "none"


@dataclass
class HrDashboardFilters:
    start_date: date | None = None
    end_date: date | None = None
    org_department_id: UUID | None = None
    designation: str | None = None
    manager_id: UUID | None = None
    shift_id: UUID | None = None
    employment_type: str | None = None
    team_id: UUID | None = None
    status: str = "active"
    horizon_days: int = 30

    def period(self, today: date) -> tuple[date, date]:
        start = self.start_date or today.replace(day=1)
        end = self.end_date or start.replace(day=calendar.monthrange(start.year, start.month)[1])
        if end < start:
            start, end = end, start
        return start, end

    def has_dimension_filter(self) -> bool:
        return any(
            (
                self.org_department_id,
                self.designation,
                self.manager_id,
                self.shift_id,
                self.employment_type,
                self.team_id,
            )
        )


@dataclass
class _Context:
    today: date
    period_start: date
    period_end: date
    base: list[User]
    shifts_today: dict[UUID, ResourceShift]
    segments: dict[str, set[UUID]] = field(default_factory=dict)

    def add(self, key: str, user_id: UUID) -> None:
        self.segments.setdefault(key, set()).add(user_id)

    def count(self, key: str) -> int:
        return len(self.segments.get(key, set()))


def _full_name(user: User | None) -> str:
    if user is None:
        return ""
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or "")


def is_active_employee(user: User, today: date) -> bool:
    if not user.is_active or user.is_archived or user.is_deleted:
        return False
    return user.leaving_date is None or user.leaving_date >= today


def _employment_type_key(user: User) -> str:
    value = getattr(user.employment_type, "value", user.employment_type)
    return str(value) if value else NONE_KEY


def _months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _shift_label(shift: ResourceShift | None) -> str:
    if shift is None:
        return "No shift assigned"
    return resource_shift_service.format_shift_label(shift)


def _load_base(
    db: Session,
    filters: HrDashboardFilters,
    *,
    scoped_user_ids: set[UUID] | None,
    today: date,
) -> tuple[list[User], dict[UUID, ResourceShift]]:
    stmt = (
        select(User)
        .options(selectinload(User.manager), selectinload(User.org_department))
        .where(User.is_deleted.is_(False), employee_user_clause())
    )
    if scoped_user_ids is not None:
        stmt = stmt.where(User.id.in_(scoped_user_ids or {UUID(int=0)}))
    if filters.org_department_id:
        stmt = stmt.where(User.org_department_id == filters.org_department_id)
    if filters.designation:
        stmt = stmt.where(User.designation == filters.designation)
    if filters.manager_id:
        stmt = stmt.where(User.manager_id == filters.manager_id)
    if filters.employment_type:
        stmt = stmt.where(User.employment_type == filters.employment_type)
    if filters.team_id:
        from app.core.team_access import team_member_user_ids

        member_ids = team_member_user_ids(db, [filters.team_id]) or {UUID(int=0)}
        stmt = stmt.where(User.id.in_(member_ids))
    users = list(db.scalars(stmt.order_by(User.first_name, User.last_name)).all())
    resolved = resource_shift_service.resolve_shifts_for_range(
        db, [u.id for u in users], today, today
    )
    shifts_today = {
        uid: per_day[today] for uid, per_day in resolved.items() if today in per_day
    }
    if filters.shift_id:
        users = [
            u
            for u in users
            if (shifts_today.get(u.id) is not None and shifts_today[u.id].id == filters.shift_id)
        ]
    return users, shifts_today


def _population(ctx: _Context, status: str) -> list[User]:
    if status == "all":
        return list(ctx.base)
    if status == "inactive":
        return [u for u in ctx.base if not is_active_employee(u, ctx.today)]
    return [u for u in ctx.base if is_active_employee(u, ctx.today)]


def _breakdown(
    ctx: _Context,
    users: list[User],
    *,
    prefix: str,
    key_fn,
    label_fn,
) -> list[dict[str, Any]]:
    labels: dict[str, str] = {}
    for user in users:
        key = key_fn(user)
        labels.setdefault(key, label_fn(user))
        ctx.add(f"{prefix}:{key}", user.id)
    rows = [
        {
            "key": key,
            "label": labels[key],
            "count": ctx.count(f"{prefix}:{key}"),
            "segment": f"{prefix}:{key}",
        }
        for key in labels
    ]
    rows.sort(key=lambda row: (-row["count"], row["label"]))
    return rows


def _monthly_trend(ctx: _Context, *, months: int = 12) -> list[dict[str, Any]]:
    end_month = ctx.period_end.replace(day=1)
    anchors: list[tuple[int, int]] = []
    year, month = end_month.year, end_month.month
    for _ in range(months):
        anchors.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    anchors.reverse()
    rows: list[dict[str, Any]] = []
    for year, month in anchors:
        m_start, m_end = _month_bounds(year, month)
        key = f"{year:04d}-{month:02d}"
        opening = joiners = exits = 0
        for user in ctx.base:
            joined = user.joining_date
            left = user.leaving_date
            employed_at_start = (joined is None or joined < m_start) and (
                left is None or left >= m_start
            )
            if employed_at_start:
                opening += 1
            if joined is not None and m_start <= joined <= m_end:
                joiners += 1
                ctx.add(f"trend_join:{key}", user.id)
            if left is not None and m_start <= left <= m_end:
                exits += 1
                ctx.add(f"trend_exit:{key}", user.id)
        rows.append(
            {
                "month": key,
                "label": m_start.strftime("%b %Y"),
                "opening": opening,
                "joiners": joiners,
                "exits": exits,
                "closing": opening + joiners - exits,
                "joiners_segment": f"trend_join:{key}",
                "exits_segment": f"trend_exit:{key}",
            }
        )
    return rows


def _onboarding(db: Session, ctx: _Context, base_ids: set[UUID]) -> dict[UUID, dict[str, Any]]:
    checklists = list(
        db.scalars(
            select(OnboardingChecklist).where(
                OnboardingChecklist.employee_user_id.in_(base_ids or {UUID(int=0)})
            )
        ).all()
    )
    latest: dict[UUID, OnboardingChecklist] = {}
    for row in checklists:
        prev = latest.get(row.employee_user_id)
        if prev is None or (row.created_at or 0) > (prev.created_at or 0):
            latest[row.employee_user_id] = row
    checklist_ids = [row.id for row in latest.values()]
    progress: dict[UUID, Counter] = defaultdict(Counter)
    if checklist_ids:
        for checklist_id, status, count in db.execute(
            select(
                OnboardingChecklistItem.checklist_id,
                OnboardingChecklistItem.status,
                func.count(),
            )
            .where(OnboardingChecklistItem.checklist_id.in_(checklist_ids))
            .group_by(OnboardingChecklistItem.checklist_id, OnboardingChecklistItem.status)
        ).all():
            progress[checklist_id][str(status)] += int(count)
    out: dict[UUID, dict[str, Any]] = {}
    for user_id, row in latest.items():
        counts = progress.get(row.id, Counter())
        total = sum(counts.values())
        resolved = sum(
            count for status, count in counts.items() if onboarding_tasks.is_resolved(status)
        )
        unresolved = total - resolved
        percent = round(100 * resolved / total) if total else 0
        anchor = row.joining_date or (row.created_at.date() if row.created_at else None)
        overdue = bool(
            row.status == "in_progress"
            and anchor is not None
            and ctx.today >= anchor + timedelta(days=INCOMPLETE_ONBOARDING_SLA_DAYS)
        )
        if row.status == "in_progress":
            ctx.add("onboarding_in_progress", user_id)
        if overdue:
            ctx.add("onboarding_overdue", user_id)
        out[user_id] = {
            "checklist_id": str(row.id),
            "status": row.status,
            "percent_complete": percent,
            "pending_items": unresolved,
            "overdue": overdue,
        }
    return out


def _it_readiness(db: Session, ctx: _Context, user_ids: set[UUID]) -> dict[UUID, dict[str, Any]]:
    if not user_ids:
        return {}
    latest: dict[UUID, ItProvisioningRequest] = {}
    for row in db.scalars(
        select(ItProvisioningRequest).where(ItProvisioningRequest.user_id.in_(user_ids))
    ).all():
        prev = latest.get(row.user_id)
        if prev is None or (row.created_at or 0) > (prev.created_at or 0):
            latest[row.user_id] = row
    seats: dict[UUID, str] = {}
    for user_id, code in db.execute(
        select(WorkstationPackageAssignment.user_id, WorkstationPackage.code)
        .join(WorkstationPackage, WorkstationPackage.id == WorkstationPackageAssignment.package_id)
        .where(
            WorkstationPackageAssignment.user_id.in_(user_ids),
            WorkstationPackageAssignment.status == "ACTIVE",
        )
    ).all():
        seats[user_id] = code
    out: dict[UUID, dict[str, Any]] = {}
    for user_id in user_ids:
        req = latest.get(user_id)
        overdue = bool(
            req is not None
            and req.status not in PROVISIONING_TERMINAL
            and req.status != "READY"
            and req.required_by is not None
            and req.required_by < ctx.today
        )
        if overdue:
            ctx.add("it_provisioning_overdue", user_id)
        out[user_id] = {
            "request_id": str(req.id) if req else None,
            "status": req.status if req else None,
            "required_by": req.required_by.isoformat() if req and req.required_by else None,
            "overdue": overdue,
            "seat_code": seats.get(user_id),
        }
    return out


def _performance(db: Session, ctx: _Context, active_users: list[User]) -> dict[str, Any]:
    year = current_review_year()
    active_ids = {u.id for u in active_users}
    sheets = list(
        db.execute(
            select(PerformanceReviewSheet)
            .join(PerformanceReviewCycle, PerformanceReviewCycle.id == PerformanceReviewSheet.cycle_id)
            .where(
                PerformanceReviewCycle.review_year == year,
                PerformanceReviewSheet.employee_id.in_(active_ids or {UUID(int=0)}),
            )
        ).scalars().all()
    )
    sheets = [s for s in sheets if getattr(s, "is_active", True)]
    reviewed: set[UUID] = set()
    for sheet in sheets:
        reviewed.add(sheet.employee_id)
        stage = sheet.stage or "self"
        ctx.add(f"review:{stage}", sheet.employee_id)
        done = stage in (STAGE_FINAL, STAGE_ACKNOWLEDGED)
        if not done and sheet.due_date is not None and sheet.due_date < ctx.today:
            ctx.add("review_overdue", sheet.employee_id)
    for uid in active_ids - reviewed:
        ctx.add("review_missing", uid)
    stages = [
        {
            "key": key,
            "label": label,
            "count": ctx.count(f"review:{key}"),
            "segment": f"review:{key}",
        }
        for key, label in REVIEW_STAGE_LABELS.items()
    ]
    return {
        "review_year": year,
        "review_year_label": f"{year}-{str(year + 1)[-2:]}",
        "sheets": len(sheets),
        "stages": stages,
        "overdue": ctx.count("review_overdue"),
        "missing": ctx.count("review_missing"),
    }


def _exit_process_user_ids(db: Session, user_ids: set[UUID]) -> set[UUID]:
    if not user_ids:
        return set()
    return {
        uid
        for uid in db.scalars(
            select(ExitInterview.employee_user_id).where(
                ExitInterview.employee_user_id.in_(user_ids),
                ExitInterview.status != "cancelled",
            )
        ).all()
        if uid is not None
    }


def _build(
    db: Session,
    filters: HrDashboardFilters,
    *,
    scoped_user_ids: set[UUID] | None,
    today: date | None = None,
) -> tuple[_Context, dict[str, Any]]:
    today = today or date.today()
    status = filters.status if filters.status in STATUS_OPTIONS else "active"
    period_start, period_end = filters.period(today)
    base, shifts_today = _load_base(db, filters, scoped_user_ids=scoped_user_ids, today=today)
    ctx = _Context(
        today=today,
        period_start=period_start,
        period_end=period_end,
        base=base,
        shifts_today=shifts_today,
    )
    horizon = today + timedelta(days=max(filters.horizon_days, 1))

    for user in base:
        ctx.add("all", user.id)
        active = is_active_employee(user, today)
        if active:
            ctx.add("active", user.id)
        else:
            ctx.add("inactive", user.id)
        if user.joining_date and period_start <= user.joining_date <= period_end:
            ctx.add("joiners", user.id)
        if user.joining_date and today < user.joining_date <= horizon:
            ctx.add("upcoming_joiners", user.id)
        if user.leaving_date and period_start <= user.leaving_date <= period_end:
            ctx.add("exits", user.id)
        if user.leaving_date and today <= user.leaving_date <= horizon:
            ctx.add("upcoming_exits", user.id)

    population = _population(ctx, status)
    for user in population:
        ctx.add("population", user.id)
        if user.manager_id is None:
            ctx.add("missing_manager", user.id)
        if user.org_department_id is None:
            ctx.add("missing_department", user.id)
        if not (user.designation or "").strip():
            ctx.add("missing_designation", user.id)
        if user.joining_date is None:
            ctx.add("missing_joining_date", user.id)
        if user.id not in shifts_today and is_active_employee(user, today):
            ctx.add("missing_shift", user.id)

    breakdowns = {
        "department": _breakdown(
            ctx,
            population,
            prefix="dept",
            key_fn=lambda u: str(u.org_department_id) if u.org_department_id else NONE_KEY,
            label_fn=lambda u: u.org_department.name if u.org_department else "No department",
        ),
        "designation": _breakdown(
            ctx,
            population,
            prefix="designation",
            key_fn=lambda u: (u.designation or "").strip() or NONE_KEY,
            label_fn=lambda u: (u.designation or "").strip() or "No designation",
        ),
        "employment_type": _breakdown(
            ctx,
            population,
            prefix="emp_type",
            key_fn=_employment_type_key,
            label_fn=lambda u: EMPLOYMENT_TYPE_LABELS.get(_employment_type_key(u), "Not set"),
        ),
        "shift": _breakdown(
            ctx,
            population,
            prefix="shift",
            key_fn=lambda u: str(shifts_today[u.id].id) if u.id in shifts_today else NONE_KEY,
            label_fn=lambda u: _shift_label(shifts_today.get(u.id)),
        ),
        "manager": _breakdown(
            ctx,
            population,
            prefix="manager",
            key_fn=lambda u: str(u.manager_id) if u.manager_id else NONE_KEY,
            label_fn=lambda u: _full_name(u.manager) if u.manager else "No manager",
        ),
    }

    tenure_rows = []
    for user in population:
        if user.joining_date is None or user.joining_date > today:
            ctx.add("tenure:unknown", user.id)
            continue
        months = _months_between(user.joining_date, today)
        for key, _label, lo, hi in TENURE_BUCKETS:
            if months >= lo and (hi is None or months < hi):
                ctx.add(f"tenure:{key}", user.id)
                break
    for key, label, _lo, _hi in TENURE_BUCKETS:
        tenure_rows.append(
            {"key": key, "label": label, "count": ctx.count(f"tenure:{key}"), "segment": f"tenure:{key}"}
        )
    if ctx.count("tenure:unknown"):
        tenure_rows.append(
            {
                "key": "unknown",
                "label": "No joining date",
                "count": ctx.count("tenure:unknown"),
                "segment": "tenure:unknown",
            }
        )

    milestones: list[dict[str, Any]] = []
    for user in population:
        joined = user.joining_date
        if joined is None or not is_active_employee(user, today):
            continue
        for year in (today.year, today.year + 1):
            try:
                anniversary = joined.replace(year=year)
            except ValueError:
                anniversary = date(year, 3, 1)
            years = year - joined.year
            if years >= 1 and today <= anniversary <= horizon:
                ctx.add("anniversaries", user.id)
                milestones.append(
                    {
                        "user_id": str(user.id),
                        "name": _full_name(user),
                        "date": anniversary.isoformat(),
                        "years": years,
                        "kind": "work_anniversary",
                    }
                )
                break
    milestones.sort(key=lambda row: row["date"])

    trend = _monthly_trend(ctx)

    base_ids = {u.id for u in base}
    onboarding = _onboarding(db, ctx, base_ids)
    joiner_ids = ctx.segments.get("joiners", set()) | ctx.segments.get("upcoming_joiners", set())
    readiness = _it_readiness(db, ctx, joiner_ids)
    for uid in joiner_ids:
        if readiness.get(uid, {}).get("status") is None:
            ctx.add("joiners_without_it_request", uid)

    exit_candidates = ctx.segments.get("exits", set()) | ctx.segments.get("upcoming_exits", set())
    with_exit = _exit_process_user_ids(db, exit_candidates)
    for uid in exit_candidates - with_exit:
        ctx.add("exits_without_exit_process", uid)

    active_users = [u for u in base if is_active_employee(u, today)]
    performance = _performance(db, ctx, active_users)

    by_id = {u.id: u for u in base}
    joiners_table = []
    for uid in sorted(joiner_ids, key=lambda i: (by_id[i].joining_date or today, _full_name(by_id[i]))):
        user = by_id[uid]
        joiners_table.append(
            {
                "user_id": str(uid),
                "name": _full_name(user),
                "designation": user.designation,
                "department": user.org_department.name if user.org_department else None,
                "manager": _full_name(user.manager) if user.manager else None,
                "joining_date": user.joining_date.isoformat() if user.joining_date else None,
                "shift": _shift_label(shifts_today.get(uid)) if uid in shifts_today else None,
                "onboarding": onboarding.get(uid),
                "it": readiness.get(uid),
            }
        )

    actions_spec = [
        ("onboarding_overdue", "Onboarding past 14-day SLA", "high", "/hr/onboarding"),
        ("joiners_without_it_request", "Joiners with no IT provisioning request", "high", "/it/requests"),
        ("it_provisioning_overdue", "Joiners with overdue IT provisioning", "high", "/it/requests?overdue=1"),
        ("exits_without_exit_process", "Exits with no exit process started", "high", "/hr/exit-process"),
        ("review_overdue", "Performance reviews past due date", "medium", "/performance/reviews"),
        ("missing_manager", "Employees without a reporting manager", "medium", None),
        ("missing_department", "Employees without a department", "medium", None),
        ("missing_shift", "Active employees with no shift today", "medium", "/resource-planning"),
        ("missing_joining_date", "Employees with no joining date", "low", None),
        ("missing_designation", "Employees with no designation", "low", None),
    ]
    actions = [
        {
            "code": code,
            "title": title,
            "severity": severity,
            "count": ctx.count(code),
            "segment": code,
            "module_link": link,
        }
        for code, title, severity, link in actions_spec
        if ctx.count(code) > 0
    ]

    result = {
        "as_of": today.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "horizon_days": filters.horizon_days,
        "status": status,
        "cards": {
            "total_employees": ctx.count("all"),
            "active_employees": ctx.count("active"),
            "new_joiners": ctx.count("joiners"),
            "upcoming_joiners": ctx.count("upcoming_joiners"),
            "exits": ctx.count("exits"),
            "upcoming_exits": ctx.count("upcoming_exits"),
            "open_hr_actions": sum(row["count"] for row in actions),
            "onboarding_in_progress": ctx.count("onboarding_in_progress"),
            "onboarding_overdue": ctx.count("onboarding_overdue"),
        },
        "breakdowns": breakdowns,
        "trend": trend,
        "tenure": tenure_rows,
        "joiners": joiners_table,
        "performance": performance,
        "milestones": milestones[:25],
        "actions": actions,
    }
    return ctx, result


def build_overview(
    db: Session,
    filters: HrDashboardFilters,
    *,
    scoped_user_ids: set[UUID] | None,
    today: date | None = None,
) -> dict[str, Any]:
    _ctx, result = _build(db, filters, scoped_user_ids=scoped_user_ids, today=today)
    result["filter_options"] = filter_options(db, scoped_user_ids=scoped_user_ids)
    return result


def segment_employees(
    db: Session,
    filters: HrDashboardFilters,
    segment: str,
    *,
    scoped_user_ids: set[UUID] | None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    ctx, _result = _build(db, filters, scoped_user_ids=scoped_user_ids, today=today)
    ids = ctx.segments.get(segment, set())
    rows = []
    for user in ctx.base:
        if user.id not in ids:
            continue
        shift = ctx.shifts_today.get(user.id)
        rows.append(
            {
                "user_id": str(user.id),
                "name": _full_name(user),
                "email": user.email,
                "designation": user.designation,
                "department": user.org_department.name if user.org_department else None,
                "manager": _full_name(user.manager) if user.manager else None,
                "employment_type": EMPLOYMENT_TYPE_LABELS.get(_employment_type_key(user)),
                "joining_date": user.joining_date.isoformat() if user.joining_date else None,
                "leaving_date": user.leaving_date.isoformat() if user.leaving_date else None,
                "status": "active" if is_active_employee(user, ctx.today) else "inactive",
                "shift": _shift_label(shift) if shift else None,
            }
        )
    return rows


def filter_options(db: Session, *, scoped_user_ids: set[UUID] | None) -> dict[str, Any]:
    user_filter = [User.is_deleted.is_(False), employee_user_clause()]
    if scoped_user_ids is not None:
        user_filter.append(User.id.in_(scoped_user_ids or {UUID(int=0)}))
    departments = db.execute(
        select(OrgDepartment.id, OrgDepartment.name).order_by(OrgDepartment.name)
    ).all()
    designations = db.scalars(
        select(User.designation)
        .where(*user_filter, User.designation.is_not(None), User.designation != "")
        .distinct()
        .order_by(User.designation)
    ).all()
    manager_ids = set(
        db.scalars(select(User.manager_id).where(*user_filter, User.manager_id.is_not(None))).all()
    )
    managers = (
        db.execute(
            select(User.id, User.first_name, User.last_name)
            .where(User.id.in_(manager_ids))
            .order_by(User.first_name, User.last_name)
        ).all()
        if manager_ids
        else []
    )
    shifts = db.scalars(
        select(ResourceShift).where(ResourceShift.is_active.is_(True)).order_by(ResourceShift.start_time)
    ).all()
    return {
        "departments": [{"value": str(i), "label": n} for i, n in departments],
        "designations": [{"value": d, "label": d} for d in designations],
        "managers": [{"value": str(i), "label": f"{f} {l}".strip()} for i, f, l in managers],
        "shifts": [{"value": str(s.id), "label": resource_shift_service.format_shift_label(s)} for s in shifts],
        "employment_types": [{"value": k, "label": v} for k, v in EMPLOYMENT_TYPE_LABELS.items()],
    }
