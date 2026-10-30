"""Skill development, training and knowledge-transfer plans.

A plan records intent and progress. Completing it never changes a skill record:
the verification outcome shown on a plan is read live from the employee's record,
which only the assessment workflow can change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import Skill, UserSkill
from app.models.models import User
from app.models.skills import (
    OPEN_PLAN_STATUSES,
    PLAN_CANCELLED,
    PLAN_COMPLETED,
    PLAN_PLANNED,
    PLAN_STATUSES,
    STATUS_ARCHIVED,
    SkillDevelopmentPlan,
)
from app.services.skills.access import SkillAccess
from app.services.skills.errors import (
    SkillNotFoundError,
    SkillPermissionError,
    SkillValidationError,
)
from app.services.skills.profiles import display_state, is_current_verified
from app.services.skills.taxonomy import validate_level


@dataclass
class PlanInput:
    skill_id: UUID
    target_level: int
    objective: str | None = None
    training_required: bool = False
    training_requirement: str | None = None
    is_knowledge_transfer: bool = False
    mentor_id: UUID | None = None
    target_review_date: date | None = None
    status: str = PLAN_PLANNED
    progress_note: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _current_verified_level(db: Session, user_id: UUID, skill: Skill) -> int | None:
    record = db.scalar(select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.skill_id == skill.id))
    if record is None or not is_current_verified(record, skill, date.today()):
        return None
    return record.verified_level


def _validate(db: Session, subject_id: UUID, data: PlanInput) -> Skill:
    skill = db.get(Skill, data.skill_id)
    if skill is None:
        raise SkillNotFoundError("Skill not found.")
    validate_level(data.target_level, field_name="target_level")
    if data.status not in PLAN_STATUSES:
        raise SkillValidationError(f"Unknown plan status '{data.status}'.")
    if data.mentor_id is not None:
        if data.mentor_id == subject_id:
            raise SkillValidationError("An employee cannot mentor themselves.")
        mentor = db.get(User, data.mentor_id)
        if mentor is None or not mentor.is_active or mentor.is_deleted:
            raise SkillValidationError("Mentor must be an active employee.")
    return skill


def create_plan(db: Session, access: SkillAccess, *, subject_id: UUID, data: PlanInput) -> SkillDevelopmentPlan:
    if not access.can_review(db, subject_id):
        raise SkillPermissionError("Only an authorised manager or reviewer can create development plans for this employee.")
    skill = _validate(db, subject_id, data)
    if not skill.is_active:
        raise SkillValidationError(f"'{skill.name}' is inactive.")
    baseline = _current_verified_level(db, subject_id, skill)
    if baseline is not None and data.target_level <= baseline:
        raise SkillValidationError(f"Target level must be above the current verified level ({baseline}).")
    plan = SkillDevelopmentPlan(
        user_id=subject_id,
        skill_id=skill.id,
        baseline_verified_level=baseline,
        target_level=data.target_level,
        objective=(data.objective or "").strip() or None,
        training_required=bool(data.training_required),
        training_requirement=(data.training_requirement or "").strip() or None,
        is_knowledge_transfer=bool(data.is_knowledge_transfer),
        mentor_id=data.mentor_id,
        target_review_date=data.target_review_date,
        status=data.status,
        progress_note=(data.progress_note or "").strip() or None,
        completed_at=_now() if data.status == PLAN_COMPLETED else None,
        created_by_id=access.user.id,
        updated_by_id=access.user.id,
    )
    db.add(plan)
    db.flush()
    return plan


def update_plan(db: Session, access: SkillAccess, plan: SkillDevelopmentPlan, data: PlanInput) -> SkillDevelopmentPlan:
    if not access.can_review(db, plan.user_id):
        raise SkillPermissionError("Only an authorised manager or reviewer can update this plan.")
    if data.skill_id != plan.skill_id:
        raise SkillValidationError("A plan's skill cannot be changed; create a new plan instead.")
    _validate(db, plan.user_id, data)
    if plan.status in (PLAN_COMPLETED, PLAN_CANCELLED) and data.status in OPEN_PLAN_STATUSES:
        plan.completed_at = None
    if data.status == PLAN_COMPLETED and plan.status != PLAN_COMPLETED:
        plan.completed_at = _now()
    plan.target_level = data.target_level
    plan.objective = (data.objective or "").strip() or None
    plan.training_required = bool(data.training_required)
    plan.training_requirement = (data.training_requirement or "").strip() or None
    plan.is_knowledge_transfer = bool(data.is_knowledge_transfer)
    plan.mentor_id = data.mentor_id
    plan.target_review_date = data.target_review_date
    plan.status = data.status
    plan.progress_note = (data.progress_note or "").strip() or None
    plan.updated_by_id = access.user.id
    db.flush()
    return plan


def get_plan(db: Session, plan_id: UUID) -> SkillDevelopmentPlan:
    plan = db.get(SkillDevelopmentPlan, plan_id)
    if plan is None:
        raise SkillNotFoundError("Development plan not found.")
    return plan


def list_plans(db: Session, *, user_ids: set[UUID] | None, include_closed: bool) -> list[SkillDevelopmentPlan]:
    stmt = select(SkillDevelopmentPlan)
    if user_ids is not None:
        if not user_ids:
            return []
        stmt = stmt.where(SkillDevelopmentPlan.user_id.in_(user_ids))
    if not include_closed:
        stmt = stmt.where(SkillDevelopmentPlan.status.in_(OPEN_PLAN_STATUSES))
    return list(db.scalars(stmt.order_by(SkillDevelopmentPlan.target_review_date, SkillDevelopmentPlan.created_at)).all())


def plan_reads(db: Session, plans: list[SkillDevelopmentPlan]) -> list[dict]:
    if not plans:
        return []
    user_ids = {p.user_id for p in plans} | {p.mentor_id for p in plans if p.mentor_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
    skills = {s.id: s for s in db.scalars(select(Skill).where(Skill.id.in_({p.skill_id for p in plans}))).all()}
    records = {
        (r.user_id, r.skill_id): r
        for r in db.scalars(
            select(UserSkill).where(
                UserSkill.user_id.in_({p.user_id for p in plans}),
                UserSkill.skill_id.in_({p.skill_id for p in plans}),
                UserSkill.status != STATUS_ARCHIVED,
            )
        ).all()
    }
    mentor_records = {
        (r.user_id, r.skill_id): r
        for r in db.scalars(
            select(UserSkill).where(
                UserSkill.user_id.in_({p.mentor_id for p in plans if p.mentor_id} or {UUID(int=0)}),
                UserSkill.skill_id.in_({p.skill_id for p in plans}),
            )
        ).all()
    }
    today = date.today()

    def name(uid: UUID | None) -> str | None:
        u = users.get(uid) if uid else None
        return (f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email) if u else None

    out = []
    for p in plans:
        skill = skills.get(p.skill_id)
        record = records.get((p.user_id, p.skill_id))
        mentor_record = mentor_records.get((p.mentor_id, p.skill_id)) if p.mentor_id else None
        out.append(
            {
                "id": p.id,
                "user_id": p.user_id,
                "user_name": name(p.user_id),
                "skill_id": p.skill_id,
                "skill_name": skill.name if skill else None,
                "baseline_verified_level": p.baseline_verified_level,
                "current_verified_level": record.verified_level if (record and skill and is_current_verified(record, skill, today)) else None,
                "verification_outcome": display_state(record, skill, today) if skill else "no_record",
                "target_level": p.target_level,
                "objective": p.objective,
                "training_required": bool(p.training_required),
                "training_requirement": p.training_requirement,
                "is_knowledge_transfer": bool(p.is_knowledge_transfer),
                "mentor_id": p.mentor_id,
                "mentor_name": name(p.mentor_id),
                "mentor_verified_level": mentor_record.verified_level
                if (mentor_record and skill and is_current_verified(mentor_record, skill, today))
                else None,
                "target_review_date": p.target_review_date,
                "status": p.status,
                "progress_note": p.progress_note,
                "completed_at": p.completed_at,
                "updated_at": p.updated_at,
            }
        )
    return out
