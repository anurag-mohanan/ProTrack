"""Single definition of verified coverage, used by matching, gap reports and the Control Tower.

Only current verified records count as coverage (status ``verified``, a
verified level, not past the skill's reassessment interval). Self-declared,
pending, legacy, rejected and reassessment records are reported separately and
never counted. A missing record means "unknown", not "lacks the skill".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.user_types import employee_user_clause
from app.models.foundation import Skill, UserSkill
from app.models.models import User
from app.models.skills import STATUS_ARCHIVED, STATUS_PENDING, STATUS_SELF_DECLARED
from app.services.skills.profiles import display_state, is_current_verified
from app.services.skills.taxonomy import DEFAULT_SPECIALIST_LEVEL

REQUIREMENT_STATES = {
    "verified_meets": "Verified at or above the required level",
    "verified_below": "Verified below the required level",
    "claimed_meets": "Claims the required level (not verified)",
    "claimed_below": "Claims a lower level (not verified)",
    "reassessment_due": "Verification needs reassessment",
    "not_confirmed": "Claim reviewed and not confirmed",
    "no_record": "No skill record (unknown, not a confirmed lack)",
}


def specialist_level(skill: Skill) -> int:
    return int(skill.specialist_level or DEFAULT_SPECIALIST_LEVEL)


def requirement_state(record: UserSkill | None, skill: Skill, min_level: int, today: date) -> str:
    state = display_state(record, skill, today)
    if state in ("no_record", "archived"):
        return "no_record"
    if state == "rejected":
        return "not_confirmed"
    if state == "reassessment":
        return "reassessment_due"
    if state == "verified":
        return "verified_meets" if (record.verified_level or 0) >= min_level else "verified_below"
    return "claimed_meets" if (record.declared_level or 0) >= min_level else "claimed_below"


def active_employee_ids(db: Session, within: set[UUID] | None = None) -> set[UUID]:
    stmt = select(User.id).where(User.is_active.is_(True), User.is_deleted.is_(False), employee_user_clause())
    if within is not None:
        if not within:
            return set()
        stmt = stmt.where(User.id.in_(within))
    return set(db.scalars(stmt).all())


def load_records(db: Session, user_ids: set[UUID] | None, skill_ids: set[UUID] | None = None) -> dict[UUID, dict[UUID, UserSkill]]:
    """Non-archived records keyed by user then skill."""
    stmt = select(UserSkill).where(UserSkill.status != STATUS_ARCHIVED)
    if user_ids is not None:
        if not user_ids:
            return {}
        stmt = stmt.where(UserSkill.user_id.in_(user_ids))
    if skill_ids is not None:
        if not skill_ids:
            return {}
        stmt = stmt.where(UserSkill.skill_id.in_(skill_ids))
    out: dict[UUID, dict[UUID, UserSkill]] = defaultdict(dict)
    for row in db.scalars(stmt).all():
        out[row.user_id][row.skill_id] = row
    return dict(out)


@dataclass
class SkillCoverage:
    skill_id: UUID
    verified_user_levels: dict[UUID, int]
    claimed_user_ids: set[UUID]
    reassessment_user_ids: set[UUID]
    rejected_user_ids: set[UUID]
    recorded_user_ids: set[UUID]

    def verified_at_or_above(self, level: int) -> set[UUID]:
        return {uid for uid, lvl in self.verified_user_levels.items() if lvl >= level}


def coverage_for_skills(db: Session, skills: list[Skill], population: set[UUID], today: date) -> dict[UUID, SkillCoverage]:
    records = load_records(db, population, {s.id for s in skills})
    by_skill = {s.id: s for s in skills}
    out = {
        s.id: SkillCoverage(s.id, {}, set(), set(), set(), set())
        for s in skills
    }
    for user_id, per_skill in records.items():
        for skill_id, record in per_skill.items():
            skill = by_skill.get(skill_id)
            if skill is None:
                continue
            cov = out[skill_id]
            cov.recorded_user_ids.add(user_id)
            state = display_state(record, skill, today)
            if is_current_verified(record, skill, today):
                cov.verified_user_levels[user_id] = int(record.verified_level)
            elif state == "reassessment":
                cov.reassessment_user_ids.add(user_id)
            elif state == "rejected":
                cov.rejected_user_ids.add(user_id)
            elif record.status in (STATUS_SELF_DECLARED, STATUS_PENDING):
                cov.claimed_user_ids.add(user_id)
    return out
