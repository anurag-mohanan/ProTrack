"""July–June performance cycle dossier — quantified year view for individuals & leaders."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.models import (
    PerformanceReviewSheet,
    Project,
    TaskType,
    Timesheet,
    TimesheetEntry,
    User,
    UserSkillRating,
)
from app.services.holiday_service import load_holiday_dates
from app.services.performance_review_service import (
    current_review_year,
    default_period_label,
    discover_employee_projects,
    format_tenure,
    review_period_bounds,
)
from app.services.reporting.periods import count_working_days
from app.services.timesheet_reconciliation_service import (
    compute_month_summary,
    month_bounds,
)
from app.services.review_engine_service import STAGE_ACKNOWLEDGED


def _iter_months(period_start: date, period_end: date) -> list[tuple[int, int]]:
    months: list[tuple[int, int]] = []
    y, m = period_start.year, period_start.month
    while (y, m) <= (period_end.year, period_end.month):
        months.append((y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return months


def _month_expected_hours(
    db: Session,
    *,
    user: User,
    year: int,
    month: int,
    holidays: set[date],
) -> float:
    start, end = month_bounds(year, month)
    days = count_working_days(start, end, holidays)
    daily = float(user.working_hours_per_day or 8)
    return round(days * daily, 2)


def _is_checking_task_name(name: str | None) -> bool:
    if not name:
        return False
    lower = name.lower()
    return any(token in lower for token in ("check", "review", "qa"))


def _checking_hours(
    db: Session,
    *,
    user_id: UUID,
    period_start: date,
    period_end: date,
) -> float:
    rows = db.execute(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0), TaskType.name)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .outerjoin(TaskType, TaskType.id == TimesheetEntry.task_type_id)
        .where(
            Timesheet.user_id == user_id,
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.entry_date >= period_start,
            TimesheetEntry.entry_date <= period_end,
            TimesheetEntry.project_id.is_not(None),
        )
        .group_by(TaskType.name)
    ).all()
    total = Decimal("0")
    for hours, name in rows:
        if _is_checking_task_name(name):
            total += Decimal(str(hours or 0))
    return float(total)


def _prior_acknowledged_annual(
    db: Session,
    *,
    employee_id: UUID,
    period_end: date,
) -> PerformanceReviewSheet | None:
    sheets = list(
        db.scalars(
            select(PerformanceReviewSheet)
            .options(selectinload(PerformanceReviewSheet.cycle))
            .where(
                PerformanceReviewSheet.employee_id == employee_id,
                PerformanceReviewSheet.is_active.is_(True),
                or_(
                    PerformanceReviewSheet.stage == STAGE_ACKNOWLEDGED,
                    PerformanceReviewSheet.acknowledged_at.is_not(None),
                ),
            )
            .order_by(PerformanceReviewSheet.created_at.desc())
        ).all()
    )
    annual = [
        row
        for row in sheets
        if (row.cycle.kind if row.cycle is not None else "annual") == "annual"
    ]
    for row in annual:
        end = row.review_period_end
        if end is not None and end <= period_end:
            return row
        if end is None:
            return row
    return annual[0] if annual else None


def _sheet_narrative(row: PerformanceReviewSheet | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "period_label": row.period_label,
        "overall_score": float(row.overall_score) if row.overall_score is not None else None,
        "stage": row.stage,
        "status": row.status,
        "career_goals": row.career_goals,
        "strengths_summary": row.strengths_summary,
        "improvement_summary": row.improvement_summary,
        "manager_summary": row.manager_summary,
        "employee_summary": row.employee_summary,
        "review_period_start": row.review_period_start.isoformat()
        if row.review_period_start
        else None,
        "review_period_end": row.review_period_end.isoformat()
        if row.review_period_end
        else None,
    }


def _enrich_projects(db: Session, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in projects:
        pid = row.get("project_id")
        project = db.get(Project, pid) if pid is not None else None
        quoted = float(project.quoted_hours) if project and project.quoted_hours is not None else None
        actual = float(project.actual_hours) if project and project.actual_hours is not None else None
        person_hours = float(row.get("hours_logged") or 0)
        variance = None
        if quoted is not None and quoted > 0 and actual is not None:
            variance = round(((actual - quoted) / quoted) * 100, 1)
        enriched.append(
            {
                "project_id": str(pid) if pid else None,
                "tool_number": row.get("tool_number"),
                "part_description": row.get("part_description"),
                "customer_name": row.get("customer_name"),
                "assignment_role": row.get("assignment_role"),
                "ownership_type": row.get("ownership_type"),
                "hours_logged": person_hours,
                "quoted_hours": quoted,
                "actual_hours": actual,
                "project_avq_variance_percent": variance,
                "tasks_summary": row.get("tasks_summary"),
                "complexity": row.get("complexity"),
                "execution_status": row.get("execution_status"),
            }
        )
    return enriched


def build_performance_dossier(
    db: Session,
    *,
    subject: User,
    viewer: User,
    review_year: int | None = None,
) -> dict[str, Any]:
    year = review_year or current_review_year()
    period_start, period_end = review_period_bounds(year)
    holidays = load_holiday_dates(db, period_start, period_end)

    months_out: list[dict[str, Any]] = []
    leave_days = 0.0
    worked_total = 0.0
    expected_total = 0.0
    productive_total = 0.0
    np_total = 0.0
    months_over_expected = 0

    for y, m in _iter_months(period_start, period_end):
        expected = _month_expected_hours(
            db, user=subject, year=y, month=m, holidays=holidays
        )
        summary = compute_month_summary(
            db,
            user_id=subject.id,
            year=y,
            month=m,
            expected_hours=expected,
        )
        pct = summary.get("monthly_percent")
        if pct is not None and pct > 100:
            months_over_expected += 1
        leave_days += float(summary.get("leave_days") or 0)
        worked_total += float(summary.get("worked_hours") or 0)
        expected_total += float(summary.get("expected_hours") or 0)
        productive_total += float(summary.get("productive_hours") or 0)
        np_total += float(summary.get("non_productive_hours") or 0)
        months_out.append(
            {
                "year": y,
                "month": m,
                "label": date(y, m, 1).strftime("%b %Y"),
                "worked_hours": summary.get("worked_hours"),
                "expected_hours": summary.get("expected_hours"),
                "monthly_percent": pct,
                "leave_days": summary.get("leave_days"),
                "productive_hours": summary.get("productive_hours"),
                "non_productive_hours": summary.get("non_productive_hours"),
            }
        )

    projects_raw = discover_employee_projects(
        db,
        subject.id,
        period_start=period_start,
        period_end=period_end,
    )
    projects = _enrich_projects(db, projects_raw)
    owned = [p for p in projects if p.get("ownership_type") == "owned"]
    supported = [p for p in projects if p.get("ownership_type") == "supported"]
    checking_hours = _checking_hours(
        db, user_id=subject.id, period_start=period_start, period_end=period_end
    )

    prior = _prior_acknowledged_annual(
        db, employee_id=subject.id, period_end=period_end
    )

    skill_count = db.scalar(
        select(func.count()).select_from(UserSkillRating).where(
            UserSkillRating.user_id == subject.id
        )
    ) or 0
    rated_skills = db.scalars(
        select(UserSkillRating).where(UserSkillRating.user_id == subject.id)
    ).all()
    proficient = sum(
        1
        for row in rated_skills
        if row.proficiency and row.proficiency.value in ("proficient", "expert")
    )

    capacity_percent = (
        round((worked_total / expected_total) * 100) if expected_total > 0 else None
    )

    return {
        "review_year": year,
        "period_label": default_period_label(year),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "viewer_is_subject": viewer.id == subject.id,
        "leave_source_note": (
            "Leave days are from ProTrack timesheets. GreytHR remains the system of "
            "record for leave balances and approvals."
        ),
        "employee": {
            "id": str(subject.id),
            "name": f"{subject.first_name} {subject.last_name}".strip(),
            "email": subject.email,
            "role": subject.designation or (subject.role.name if subject.role else None),
            "joining_date": subject.joining_date.isoformat() if subject.joining_date else None,
            "company_experience": format_tenure(subject.joining_date),
        },
        "capacity": {
            "worked_hours": round(worked_total, 2),
            "expected_hours": round(expected_total, 2),
            "capacity_percent": capacity_percent,
            "productive_hours": round(productive_total, 2),
            "non_productive_hours": round(np_total, 2),
            "leave_days": round(leave_days, 2),
            "months_over_expected": months_over_expected,
            "months_in_period": len(months_out),
        },
        "months": months_out,
        "projects": {
            "owned_count": len(owned),
            "supported_count": len(supported),
            "checking_hours": checking_hours,
            "owned": owned,
            "supported": supported,
        },
        "prior_review": _sheet_narrative(prior),
        "skills": {
            "rated_count": int(skill_count),
            "proficient_or_expert": proficient,
        },
    }


def build_dossier_roster(
    db: Session,
    *,
    member_ids: list[UUID],
    review_year: int | None = None,
) -> list[dict[str, Any]]:
    """Headline KPIs for each member (lighter than full dossier)."""
    year = review_year or current_review_year()
    period_start, period_end = review_period_bounds(year)
    holidays = load_holiday_dates(db, period_start, period_end)
    users = (
        list(
            db.scalars(
                select(User)
                .options(selectinload(User.role))
                .where(User.id.in_(member_ids), User.is_deleted.is_(False), User.is_active.is_(True))
                .order_by(User.last_name, User.first_name)
            ).all()
        )
        if member_ids
        else []
    )
    rows: list[dict[str, Any]] = []
    for user in users:
        worked = 0.0
        expected = 0.0
        leave_days = 0.0
        months_over = 0
        for y, m in _iter_months(period_start, period_end):
            exp = _month_expected_hours(db, user=user, year=y, month=m, holidays=holidays)
            summary = compute_month_summary(
                db, user_id=user.id, year=y, month=m, expected_hours=exp
            )
            worked += float(summary.get("worked_hours") or 0)
            expected += float(summary.get("expected_hours") or 0)
            leave_days += float(summary.get("leave_days") or 0)
            pct = summary.get("monthly_percent")
            if pct is not None and pct > 100:
                months_over += 1
        project_count = len(
            discover_employee_projects(
                db, user.id, period_start=period_start, period_end=period_end
            )
        )
        prior = _prior_acknowledged_annual(
            db, employee_id=user.id, period_end=period_end
        )
        rows.append(
            {
                "user_id": str(user.id),
                "name": f"{user.first_name} {user.last_name}".strip(),
                "email": user.email,
                "role": user.designation or (user.role.name if user.role else None),
                "worked_hours": round(worked, 2),
                "expected_hours": round(expected, 2),
                "capacity_percent": round((worked / expected) * 100) if expected > 0 else None,
                "leave_days": round(leave_days, 2),
                "months_over_expected": months_over,
                "project_count": project_count,
                "prior_score": float(prior.overall_score)
                if prior is not None and prior.overall_score is not None
                else None,
                "prior_period_label": prior.period_label if prior else None,
            }
        )
    return rows
