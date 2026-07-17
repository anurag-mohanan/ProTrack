"""Skill matrix vs project complexity — assignment fit checks for resource allocation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import SkillProficiency
from app.models.models import StreamSkill, User, UserSkillRating

# Ordered weakest → strongest
PROFICIENCY_RANK: dict[str, int] = {
    SkillProficiency.learning.value: 1,
    SkillProficiency.developing.value: 2,
    SkillProficiency.proficient.value: 3,
    SkillProficiency.expert.value: 4,
}

# Minimum Complex Design (or role skill) proficiency required by project complexity.
COMPLEXITY_MIN_PROFICIENCY: dict[str, str] = {
    "low": SkillProficiency.learning.value,
    "medium": SkillProficiency.developing.value,
    "high": SkillProficiency.proficient.value,
    "expert": SkillProficiency.expert.value,
}

# Preferred skill names to evaluate, first match wins.
ROLE_SKILL_CANDIDATES: dict[str, list[str]] = {
    "designer": ["Complex Design", "Design"],
    "surfacer": ["Surfacing", "Complex Design", "Design"],
    "design_leader": ["Complex Design", "Checking", "Design"],
}

PROFICIENCY_LABELS: dict[str, str] = {
    SkillProficiency.learning.value: "Learning",
    SkillProficiency.developing.value: "Developing",
    SkillProficiency.proficient.value: "Proficient",
    SkillProficiency.expert.value: "Expert",
}

COMPLEXITY_LABELS: dict[str, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "expert": "Expert",
}


def _rank(value: str | None) -> int:
    if not value:
        return 0
    return PROFICIENCY_RANK.get(str(value).strip().lower(), 0)


def evaluate_assignment_skill_fit(
    db: Session,
    *,
    user_id: UUID,
    complexity: str | None,
    role: str = "designer",
) -> dict[str, Any]:
    """
    Compare a person's skill-matrix ratings to project complexity.

    Example rule (locked for Phase 1 of this feature):
    High complexity + Complex Design at Developing (or lower / missing) → warning.
    """
    complexity_key = (complexity or "medium").strip().lower()
    if complexity_key not in COMPLEXITY_MIN_PROFICIENCY:
        complexity_key = "medium"
    role_key = (role or "designer").strip().lower()
    if role_key not in ROLE_SKILL_CANDIDATES:
        role_key = "designer"

    required = COMPLEXITY_MIN_PROFICIENCY[complexity_key]
    required_rank = _rank(required)
    skill_names = ROLE_SKILL_CANDIDATES[role_key]

    user = db.get(User, user_id)
    if user is None:
        return {
            "ok": False,
            "requires_confirmation": True,
            "severity": [],
            "message": "Assignee not found.",
            "user_id": str(user_id),
            "complexity": complexity_key,
            "role": role_key,
        }

    ratings = list(
        db.scalars(
            select(UserSkillRating)
            .options(selectinload(UserSkillRating.stream_skill))
            .where(UserSkillRating.user_id == user_id)
        ).all()
    )
    by_name: dict[str, UserSkillRating] = {}
    for row in ratings:
        skill = row.stream_skill
        if skill is None:
            continue
        by_name[skill.name.strip().lower()] = row

    matched_skill_name: str | None = None
    matched_proficiency: str | None = None
    for name in skill_names:
        hit = by_name.get(name.strip().lower())
        if hit is not None:
            matched_skill_name = name
            matched_proficiency = hit.proficiency.value if hit.proficiency else None
            break

    person = f"{user.first_name} {user.last_name}".strip() or user.email
    complexity_label = COMPLEXITY_LABELS.get(complexity_key, complexity_key)
    required_label = PROFICIENCY_LABELS.get(required, required)

    warnings: list[str] = []
    requires_confirmation = False

    if matched_skill_name is None:
        requires_confirmation = required_rank >= _rank(SkillProficiency.proficient.value)
        if requires_confirmation:
            warnings.append(
                f"{person} has no skill-matrix rating for "
                f"{' / '.join(skill_names)} on this stream. "
                f"Project complexity is {complexity_label}, which normally needs at least "
                f"{required_label}."
            )
    else:
        actual_rank = _rank(matched_proficiency)
        actual_label = PROFICIENCY_LABELS.get(matched_proficiency or "", matched_proficiency or "Unrated")
        if actual_rank < required_rank:
            requires_confirmation = True
            warnings.append(
                f"{person}'s {matched_skill_name} skill is {actual_label}, but this "
                f"{complexity_label}-complexity project expects at least {required_label}. "
                f"Assigning may increase delivery risk."
            )

    message = "\n\n".join(warnings) if warnings else "Skill fit looks adequate for this complexity."
    return {
        "ok": not requires_confirmation,
        "requires_confirmation": requires_confirmation,
        "warnings": warnings,
        "message": message,
        "user_id": str(user_id),
        "user_name": person,
        "complexity": complexity_key,
        "complexity_label": complexity_label,
        "role": role_key,
        "skill_name": matched_skill_name,
        "proficiency": matched_proficiency,
        "proficiency_label": (
            PROFICIENCY_LABELS.get(matched_proficiency or "", None) if matched_proficiency else None
        ),
        "required_proficiency": required,
        "required_proficiency_label": required_label,
    }


def evaluate_multi_role_fit(
    db: Session,
    *,
    complexity: str | None,
    designer_id: UUID | None = None,
    surfacer_id: UUID | None = None,
    design_leader_id: UUID | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for role, uid in (
        ("designer", designer_id),
        ("surfacer", surfacer_id),
        ("design_leader", design_leader_id),
    ):
        if uid is None:
            continue
        checks.append(
            evaluate_assignment_skill_fit(db, user_id=uid, complexity=complexity, role=role)
        )
    warnings = [w for row in checks for w in row.get("warnings", [])]
    requires = any(row.get("requires_confirmation") for row in checks)
    return {
        "ok": not requires,
        "requires_confirmation": requires,
        "warnings": warnings,
        "message": "\n\n".join(warnings) if warnings else "All assignees fit this complexity.",
        "checks": checks,
        "complexity": (complexity or "medium").strip().lower(),
    }
