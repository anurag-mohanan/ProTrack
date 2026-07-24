"""Learning plans seeded from skill-matrix gaps (R4)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enterprise import LearningPlan, LearningPlanItem
from app.models.enums import SkillProficiency
from app.models.models import StreamSkill, User, UserSkillRating

_PROF_ORDER = {
    SkillProficiency.learning.value: 0,
    SkillProficiency.developing.value: 1,
    SkillProficiency.proficient.value: 2,
    SkillProficiency.expert.value: 3,
}


def _level(value: str | None) -> int:
    if not value:
        return -1
    return _PROF_ORDER.get(value, -1)


def skill_gaps_for_user(
    db: Session,
    user_id: UUID,
    *,
    target: str = SkillProficiency.proficient.value,
) -> list[dict]:
    ratings = {
        row.stream_skill_id: row
        for row in db.scalars(
            select(UserSkillRating).where(UserSkillRating.user_id == user_id)
        ).all()
    }
    skills = list(db.scalars(select(StreamSkill).order_by(StreamSkill.name)).all())
    gaps: list[dict] = []
    for skill in skills:
        rating = ratings.get(skill.id)
        current = rating.proficiency.value if rating and hasattr(rating.proficiency, "value") else (
            str(rating.proficiency) if rating else None
        )
        if _level(current) < _level(target):
            gaps.append(
                {
                    "stream_skill_id": skill.id,
                    "skill_name": skill.name,
                    "current_proficiency": current or SkillProficiency.learning.value,
                    "target_proficiency": target,
                }
            )
    return gaps


def create_plan_from_gaps(
    db: Session,
    *,
    user_id: UUID,
    created_by: User | None,
    title: str | None = None,
    target: str = SkillProficiency.proficient.value,
) -> LearningPlan:
    gaps = skill_gaps_for_user(db, user_id, target=target)
    user = db.get(User, user_id)
    label = title or "Skill development plan"
    if user is not None:
        name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        if name:
            label = title or f"Skill development — {name}"
    plan = LearningPlan(
        user_id=user_id,
        title=label,
        status="active",
        created_by_id=created_by.id if created_by else None,
    )
    db.add(plan)
    db.flush()
    for index, gap in enumerate(gaps):
        db.add(
            LearningPlanItem(
                plan_id=plan.id,
                stream_skill_id=gap["stream_skill_id"],
                current_proficiency=gap["current_proficiency"],
                target_proficiency=gap["target_proficiency"],
                status="open",
                sort_order=index,
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def list_plans_for_user(db: Session, user_id: UUID) -> list[LearningPlan]:
    return list(
        db.scalars(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id)
            .options(selectinload(LearningPlan.items))
            .order_by(LearningPlan.created_at.desc())
        ).all()
    )


def update_plan_item_status(
    db: Session,
    *,
    item_id: UUID,
    status: str,
) -> LearningPlanItem | None:
    item = db.get(LearningPlanItem, item_id)
    if item is None:
        return None
    item.status = status
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
