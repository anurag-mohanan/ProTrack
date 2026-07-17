"""Performance review engine — templates, workflow stages, dashboard aggregate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.models import (
    PerformanceReviewCycle,
    PerformanceReviewSheet,
    PerformanceReviewTemplate,
    TeamMember,
    User,
    UserSkillRating,
)
from app.services.performance_review_service import (
    DEFAULT_REVIEW_TEMPLATE,
    FORM_CODE,
    FORM_TITLE,
    RATING_SCALE,
    format_tenure,
)

STAGE_SELF = "self"
STAGE_MANAGER = "manager"
STAGE_CALIBRATION = "calibration"
STAGE_FINAL = "final"
STAGE_ACKNOWLEDGED = "acknowledged"

VALID_STAGES = (
    STAGE_SELF,
    STAGE_MANAGER,
    STAGE_CALIBRATION,
    STAGE_FINAL,
    STAGE_ACKNOWLEDGED,
)

KIND_ANNUAL = "annual"
KIND_QUARTERLY = "quarterly"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def ensure_default_annual_template(db: Session) -> PerformanceReviewTemplate:
    existing = db.scalar(
        select(PerformanceReviewTemplate).where(
            PerformanceReviewTemplate.code == FORM_CODE,
            PerformanceReviewTemplate.version == 1,
        )
    )
    if existing is not None:
        return existing
    row = PerformanceReviewTemplate(
        code=FORM_CODE,
        name=FORM_TITLE,
        version=1,
        kind=KIND_ANNUAL,
        is_active=True,
        rating_scale_json=json.dumps(RATING_SCALE),
        structure_json=json.dumps(DEFAULT_REVIEW_TEMPLATE),
    )
    db.add(row)
    db.flush()
    return row


def ensure_default_quarterly_template(db: Session) -> PerformanceReviewTemplate:
    code = "PP-HRD-Q-01"
    existing = db.scalar(
        select(PerformanceReviewTemplate).where(
            PerformanceReviewTemplate.code == code,
            PerformanceReviewTemplate.version == 1,
        )
    )
    if existing is not None:
        return existing
    # Lean quarterly structure — subset of annual competencies
    structure = [
        {
            "title": "Quarterly Focus",
            "description": "Delivery and collaboration for this quarter.",
            "employee_notes_label": "Key accomplishments this quarter",
            "items": [
                {"prompt": "Delivery against plan", "guidance": "On-time, on-quality delivery."},
                {"prompt": "Collaboration", "guidance": "Team and customer collaboration."},
                {"prompt": "Quality / rework", "guidance": "Quality of output and rework volume."},
                {"prompt": "Growth / learning", "guidance": "Skills built this quarter."},
            ],
        }
    ]
    row = PerformanceReviewTemplate(
        code=code,
        name="Quarterly Performance Check-in",
        version=1,
        kind=KIND_QUARTERLY,
        is_active=True,
        rating_scale_json=json.dumps(RATING_SCALE),
        structure_json=json.dumps(structure),
    )
    db.add(row)
    db.flush()
    return row


def get_active_template(
    db: Session, *, kind: str | None = None, template_id: UUID | None = None
) -> PerformanceReviewTemplate | None:
    if template_id is not None:
        return db.get(PerformanceReviewTemplate, template_id)
    stmt = select(PerformanceReviewTemplate).where(
        PerformanceReviewTemplate.is_active.is_(True)
    )
    if kind:
        stmt = stmt.where(PerformanceReviewTemplate.kind == kind)
    stmt = stmt.order_by(PerformanceReviewTemplate.version.desc())
    return db.scalar(stmt)


def template_to_dict(row: PerformanceReviewTemplate) -> dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "version": row.version,
        "kind": row.kind,
        "is_active": row.is_active,
        "rating_scale": parse_json_list(row.rating_scale_json),
        "structure": parse_json_list(row.structure_json),
        "form_code": row.code,
        "form_title": row.name,
        "form_revision": f"v{row.version}",
    }


def advance_sheet_stage(
    sheet: PerformanceReviewSheet,
    *,
    action: str,
    actor: User,
    calibration_notes: str | None = None,
    acknowledgement_signature: str | None = None,
    skip_calibration: bool = False,
) -> PerformanceReviewSheet:
    """Apply a workflow transition. Raises ValueError on illegal moves."""
    now = _now()
    stage = sheet.stage or STAGE_SELF
    cycle = sheet.cycle
    needs_calibration = bool(cycle and cycle.calibration_required) and not skip_calibration

    if action == "submit-self":
        if stage != STAGE_SELF:
            raise ValueError("Sheet is not in self-review stage.")
        sheet.self_submitted_at = now
        sheet.stage = STAGE_MANAGER
        sheet.status = "draft"
    elif action == "submit-manager":
        if stage != STAGE_MANAGER:
            raise ValueError("Sheet is not in manager-review stage.")
        sheet.manager_submitted_at = now
        sheet.submitted_at = now
        if needs_calibration:
            sheet.stage = STAGE_CALIBRATION
            sheet.status = "submitted"
            if cycle is not None and cycle.status == "open":
                cycle.status = "in_calibration"
        else:
            sheet.stage = STAGE_FINAL
            sheet.finalized_at = now
            sheet.status = "submitted"
    elif action == "calibrate":
        if stage != STAGE_CALIBRATION:
            raise ValueError("Sheet is not in calibration stage.")
        sheet.calibrator_id = actor.id
        sheet.calibrated_at = now
        if calibration_notes is not None:
            sheet.calibration_notes = calibration_notes
        sheet.stage = STAGE_FINAL
        sheet.finalized_at = now
        sheet.status = "submitted"
    elif action == "finalize":
        if stage not in (STAGE_MANAGER, STAGE_CALIBRATION, STAGE_FINAL):
            raise ValueError("Sheet cannot be finalized from the current stage.")
        sheet.stage = STAGE_FINAL
        sheet.finalized_at = now
        sheet.submitted_at = sheet.submitted_at or now
        sheet.status = "submitted"
    elif action == "acknowledge":
        if stage not in (STAGE_FINAL, STAGE_ACKNOWLEDGED):
            raise ValueError("Sheet must be finalized before acknowledgement.")
        sheet.acknowledged_at = now
        sheet.stage = STAGE_ACKNOWLEDGED
        sheet.status = "acknowledged"
        if acknowledgement_signature:
            sheet.acknowledgement_signature = acknowledgement_signature.strip()[:200]
    elif action == "reopen":
        sheet.stage = STAGE_MANAGER
        sheet.status = "draft"
        sheet.acknowledged_at = None
        sheet.acknowledgement_signature = None
        sheet.finalized_at = None
    else:
        raise ValueError(f"Unknown workflow action: {action}")

    return sheet


def build_performance_dashboard(
    db: Session,
    *,
    subject: User,
    viewer: User,
    team_id: UUID | None = None,
) -> dict[str, Any]:
    sheets = list(
        db.scalars(
            select(PerformanceReviewSheet)
            .where(
                PerformanceReviewSheet.employee_id == subject.id,
                PerformanceReviewSheet.is_active.is_(True),
            )
            .options(selectinload(PerformanceReviewSheet.cycle))
            .order_by(PerformanceReviewSheet.created_at.desc())
        ).all()
    )
    if team_id is not None:
        sheets = [row for row in sheets if row.team_id == team_id]

    open_reviews = [
        row for row in sheets if row.stage not in (STAGE_ACKNOWLEDGED,) and row.status != "acknowledged"
    ]
    completed = [row for row in sheets if row.stage == STAGE_ACKNOWLEDGED or row.acknowledged_at]
    latest = completed[0] if completed else (sheets[0] if sheets else None)
    prior = completed[1] if len(completed) > 1 else None

    memberships = db.scalars(
        select(TeamMember).where(TeamMember.user_id == subject.id)
    ).all()
    primary = next((m for m in memberships if m.is_primary), memberships[0] if memberships else None)

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

    def _sheet_summary(row: PerformanceReviewSheet | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": str(row.id),
            "period_label": row.period_label,
            "stage": row.stage,
            "status": row.status,
            "overall_score": float(row.overall_score) if row.overall_score is not None else None,
            "kind": row.cycle.kind if row.cycle else "annual",
            "manager_summary": row.manager_summary,
        }

    return {
        "employee": {
            "id": str(subject.id),
            "name": f"{subject.first_name} {subject.last_name}".strip(),
            "email": subject.email,
            "role": subject.designation or (subject.role.name if subject.role else None),
            "joining_date": subject.joining_date.isoformat() if subject.joining_date else None,
            "company_experience": format_tenure(subject.joining_date),
            "primary_team_id": str(primary.team_id) if primary else None,
            "team_count": len(memberships),
        },
        "current_rating": _sheet_summary(latest),
        "prior_rating": _sheet_summary(prior),
        "open_reviews": [_sheet_summary(row) for row in open_reviews[:10]],
        "completed_reviews": [_sheet_summary(row) for row in completed[:10]],
        "skills": {
            "rated_count": int(skill_count),
            "proficient_or_expert": proficient,
        },
        "manager_notes": latest.manager_summary if latest else None,
        "viewer_is_subject": viewer.id == subject.id,
        "utilization": _utilization_snapshot(db, subject.id),
    }


def _utilization_snapshot(db: Session, user_id: UUID) -> dict[str, Any]:
    """Lightweight timesheet compliance signal for the performance dashboard."""
    from datetime import date, timedelta

    from app.models.models import Timesheet, TimesheetEntry
    from app.services.holiday_service import load_holiday_dates
    from app.services.timesheet_compliance_service import _consecutive_missing_working_days

    today = date.today()
    holidays = load_holiday_dates(db, today - timedelta(days=45), today)
    last_entry = db.scalar(
        select(func.max(TimesheetEntry.entry_date))
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.user_id == user_id,
            TimesheetEntry.is_deleted.is_(False),
        )
    )
    missing_days = _consecutive_missing_working_days(
        last_entry=last_entry,
        today=today,
        holidays=holidays,
    )
    hours_90d = db.scalar(
        select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .where(
            Timesheet.user_id == user_id,
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.entry_date >= today - timedelta(days=90),
        )
    )
    return {
        "missing_working_days": int(missing_days),
        "hours_logged_90d": float(hours_90d or 0),
        "last_entry_date": last_entry.isoformat() if last_entry else None,
    }


def list_templates(db: Session, *, kind: str | None = None) -> list[PerformanceReviewTemplate]:
    ensure_default_annual_template(db)
    ensure_default_quarterly_template(db)
    stmt = select(PerformanceReviewTemplate).where(
        PerformanceReviewTemplate.is_active.is_(True)
    )
    if kind:
        stmt = stmt.where(PerformanceReviewTemplate.kind == kind)
    return list(db.scalars(stmt.order_by(PerformanceReviewTemplate.kind, PerformanceReviewTemplate.code)).all())
