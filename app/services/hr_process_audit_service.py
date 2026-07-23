"""HR Process Audit — incomplete onboarding, missing exit, orphan placement."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.models import ExitInterview, OnboardingChecklist, User

# Days after joining_date (or checklist created_at) before incomplete onboarding is late.
INCOMPLETE_ONBOARDING_SLA_DAYS = 14

AuditFlagCode = Literal[
    "incomplete_onboarding",
    "missing_exit",
    "orphan_placement",
    "exit_done_still_active",
]


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def incomplete_onboarding_rows(
    db: Session,
    *,
    as_of: date | None = None,
    sla_days: int = INCOMPLETE_ONBOARDING_SLA_DAYS,
) -> list[dict[str, Any]]:
    today = as_of or date.today()
    rows = db.scalars(
        select(OnboardingChecklist)
        .options(selectinload(OnboardingChecklist.items))
        .where(OnboardingChecklist.status == "in_progress")
        .order_by(OnboardingChecklist.created_at.desc())
    ).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        anchor = _as_date(row.joining_date) or _as_date(row.created_at)
        if anchor is None:
            continue
        if today < anchor + timedelta(days=sla_days):
            continue
        days_late = (today - anchor).days - sla_days
        result.append(
            {
                "flag": "incomplete_onboarding",
                "title": "Incomplete onboarding past SLA",
                "severity": "high" if days_late >= 7 else "medium",
                "subject_name": row.employee_name,
                "subject_user_id": str(row.employee_user_id) if row.employee_user_id else None,
                "checklist_id": str(row.id),
                "exit_interview_id": None,
                "detail": (
                    f"In progress since {anchor.isoformat()}; "
                    f"SLA {sla_days} days exceeded by {max(days_late, 0)} day(s)."
                ),
                "deep_link": f"/hr/onboarding?id={row.id}",
                "anchor_date": anchor.isoformat(),
            }
        )
    return result


def orphan_placement_rows(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(OnboardingChecklist)
        .where(OnboardingChecklist.status == "in_progress")
        .order_by(OnboardingChecklist.created_at.desc())
    ).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        missing: list[str] = []
        if row.team_id is None:
            missing.append("team")
        if row.reporting_manager_id is None:
            missing.append("manager")
        if not missing:
            continue
        result.append(
            {
                "flag": "orphan_placement",
                "title": "Onboarding without team or manager",
                "severity": "medium",
                "subject_name": row.employee_name,
                "subject_user_id": str(row.employee_user_id) if row.employee_user_id else None,
                "checklist_id": str(row.id),
                "exit_interview_id": None,
                "detail": f"Missing: {', '.join(missing)}.",
                "deep_link": f"/hr/onboarding?id={row.id}",
                "anchor_date": _as_date(row.joining_date or row.created_at),
            }
        )
    # Normalize anchor_date to iso string
    for item in result:
        anchor = item.get("anchor_date")
        item["anchor_date"] = anchor.isoformat() if isinstance(anchor, date) else None
    return result


def _completed_exit_user_ids(db: Session) -> set[UUID]:
    rows = db.scalars(
        select(ExitInterview.employee_user_id).where(
            ExitInterview.status == "completed",
            ExitInterview.employee_user_id.is_not(None),
        )
    ).all()
    return {uid for uid in rows if uid is not None}


def missing_exit_rows(db: Session, *, as_of: date | None = None) -> list[dict[str, Any]]:
    today = as_of or date.today()
    completed_ids = _completed_exit_user_ids(db)
    users = db.scalars(
        select(User).where(
            User.is_deleted.is_(False),
        )
    ).all()
    result: list[dict[str, Any]] = []
    for user in users:
        needs_exit = False
        reason_bits: list[str] = []
        if user.leaving_date is not None:
            needs_exit = True
            reason_bits.append(f"leaving_date={user.leaving_date.isoformat()}")
        if not user.is_active:
            needs_exit = True
            reason_bits.append("inactive")
        if not needs_exit:
            continue
        if user.id in completed_ids:
            continue
        name = f"{user.first_name} {user.last_name}".strip()
        result.append(
            {
                "flag": "missing_exit",
                "title": "Missing completed exit process",
                "severity": "high",
                "subject_name": name,
                "subject_user_id": str(user.id),
                "checklist_id": None,
                "exit_interview_id": None,
                "detail": (
                    f"User flagged ({', '.join(reason_bits)}) as of {today.isoformat()} "
                    "with no completed exit interview."
                ),
                "deep_link": "/hr/exit-process",
                "anchor_date": user.leaving_date.isoformat() if user.leaving_date else None,
            }
        )
    return result


def exit_done_still_active_rows(db: Session, *, as_of: date | None = None) -> list[dict[str, Any]]:
    today = as_of or date.today()
    exits = db.scalars(
        select(ExitInterview)
        .where(
            ExitInterview.status == "completed",
            ExitInterview.employee_user_id.is_not(None),
        )
        .order_by(ExitInterview.completed_at.desc())
    ).all()
    result: list[dict[str, Any]] = []
    for row in exits:
        user = db.get(User, row.employee_user_id) if row.employee_user_id else None
        if user is None or user.is_deleted:
            continue
        leaving = user.leaving_date
        still_active = user.is_active and (leaving is None or leaving > today)
        if not still_active:
            continue
        name = f"{user.first_name} {user.last_name}".strip() or row.employee_name
        result.append(
            {
                "flag": "exit_done_still_active",
                "title": "Exit completed but user still active",
                "severity": "high",
                "subject_name": name,
                "subject_user_id": str(user.id),
                "checklist_id": None,
                "exit_interview_id": str(row.id),
                "detail": (
                    "Exit interview completed while the user account remains active"
                    + (f" (leaving_date={leaving.isoformat()})" if leaving else "")
                    + "."
                ),
                "deep_link": f"/hr/exit-process?id={row.id}",
                "anchor_date": _as_date(row.completed_at),
            }
        )
    for item in result:
        anchor = item.get("anchor_date")
        item["anchor_date"] = anchor.isoformat() if isinstance(anchor, date) else None
    return result


def build_process_audit(
    db: Session,
    *,
    as_of: date | None = None,
    sla_days: int = INCOMPLETE_ONBOARDING_SLA_DAYS,
) -> dict[str, Any]:
    items = (
        incomplete_onboarding_rows(db, as_of=as_of, sla_days=sla_days)
        + orphan_placement_rows(db)
        + missing_exit_rows(db, as_of=as_of)
        + exit_done_still_active_rows(db, as_of=as_of)
    )
    by_flag: dict[str, int] = {}
    for item in items:
        by_flag[item["flag"]] = by_flag.get(item["flag"], 0) + 1
    return {
        "as_of": (as_of or date.today()).isoformat(),
        "sla_days": sla_days,
        "total": len(items),
        "counts": by_flag,
        "items": items,
    }
