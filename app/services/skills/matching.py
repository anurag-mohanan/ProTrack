"""Project skill requirements and candidate recommendations.

Skill suitability and availability are reported side by side and never combined
into one score:

* Suitability uses verified records only for a confirmed match; claims,
  reassessments and missing records make a candidate *unconfirmed*.
* Availability reuses the Phase 3 capacity supply forecast (preliminary) and the
  shared engineering metrics for current commitments. Nobody is ever described as
  "immediately available".

Recommendations are read-only. Assignment stays a manager decision in the
existing project and resource-planning screens.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import Skill
from app.models.models import Project, User
from app.models.skills import ProjectSkillRequirement
from app.services.engineering_metrics_service import build_engineering_metrics_batch
from app.services.forecasting.capacity import build_capacity_forecast
from app.services.forecasting.effort import open_projects
from app.services.reporting.quote_to_delivery import APPROVED_ESTIMATE_SOURCES
from app.services.skills.coverage import (
    REQUIREMENT_STATES,
    load_records,
    requirement_state,
)
from app.services.skills.errors import SkillNotFoundError, SkillValidationError
from app.services.skills.taxonomy import level_names, validate_level

MATCHING_VERSION = "skills-match-1"

SUITABILITY_LABELS = {
    "confirmed": "Confirmed match — verified at the required level for every mandatory skill",
    "unconfirmed": "Unconfirmed — relies on claims, reassessments or missing records",
    "below_requirement": "Below requirement — verified below the required level for a mandatory skill",
}
AVAILABILITY_LABELS = {
    "capacity_indicated": "Capacity indicated (preliminary)",
    "uncertain": "Capacity uncertain — some current work has no approved estimate",
    "committed": "Committed — approved remaining work meets or exceeds capacity in the horizon",
    "unavailable": "No allocatable hours in the horizon",
}
_SUIT_RANK = {"confirmed": 0, "unconfirmed": 1, "below_requirement": 2}
_AVAIL_RANK = {"capacity_indicated": 0, "uncertain": 1, "committed": 2, "unavailable": 3}


# --- Requirements ----------------------------------------------------------


def project_requirements(db: Session, project_id: UUID) -> list[ProjectSkillRequirement]:
    return list(
        db.scalars(
            select(ProjectSkillRequirement)
            .where(ProjectSkillRequirement.project_id == project_id)
            .order_by(ProjectSkillRequirement.is_mandatory.desc(), ProjectSkillRequirement.created_at)
        ).all()
    )


def set_requirement(
    db: Session, *, project: Project, skill_id: UUID, min_level: int, is_mandatory: bool, note: str | None, actor: User
) -> ProjectSkillRequirement:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise SkillNotFoundError("Skill not found.")
    level = validate_level(min_level, field_name="min_level")
    row = db.scalar(
        select(ProjectSkillRequirement).where(
            ProjectSkillRequirement.project_id == project.id, ProjectSkillRequirement.skill_id == skill_id
        )
    )
    if row is None:
        if not skill.is_active:
            raise SkillValidationError(f"'{skill.name}' is inactive.")
        row = ProjectSkillRequirement(project_id=project.id, skill_id=skill_id, created_by_id=actor.id)
        db.add(row)
    row.min_level = level
    row.is_mandatory = bool(is_mandatory)
    row.note = (note or "").strip() or None
    db.flush()
    return row


def remove_requirement(db: Session, *, project: Project, requirement_id: UUID) -> None:
    row = db.get(ProjectSkillRequirement, requirement_id)
    if row is None or row.project_id != project.id:
        raise SkillNotFoundError("Requirement not found.")
    db.delete(row)
    db.flush()


# --- Matching --------------------------------------------------------------


@dataclass
class RequirementSpec:
    skill_id: UUID
    min_level: int
    is_mandatory: bool = True


def _commitments(db: Session, user_ids: set[UUID], today: date) -> dict[UUID, dict]:
    projects = open_projects(db)
    relevant = [
        p for p in projects if {p.designer_id, p.surfacer_id, p.design_leader_id} & user_ids
    ]
    metrics = build_engineering_metrics_batch(db, relevant, finance_details_visible=False, today=today) if relevant else {}
    out: dict[UUID, dict] = defaultdict(lambda: {"open": 0, "unknown": 0, "approved_remaining": Decimal("0.00")})
    for p in relevant:
        m = metrics[p.id]
        approved = m.estimate.estimate_source in APPROVED_ESTIMATE_SOURCES and m.remaining_hours.value is not None
        for uid in {p.designer_id, p.surfacer_id, p.design_leader_id} & user_ids:
            row = out[uid]
            row["open"] += 1
            if not approved:
                row["unknown"] += 1
            elif uid == p.designer_id:
                row["approved_remaining"] += max(m.remaining_hours.value, Decimal("0"))
    return dict(out)


def _availability(allocatable: Decimal, commitment: dict) -> tuple[str, str]:
    remaining = commitment["approved_remaining"]
    if allocatable <= 0:
        return "unavailable", (
            "No allocatable hours in the horizon (on-leave or unavailable status, outside employment dates, "
            "no working days or 0% allocation)."
        )
    if remaining >= allocatable:
        return "committed", (
            f"Approved remaining hours as designer on open projects ({remaining} h) meet or exceed allocatable "
            f"hours in the horizon ({allocatable} h). Remaining work is not phased, so this is indicative."
        )
    if commitment["unknown"]:
        return "uncertain", (
            f"{allocatable} h allocatable against {remaining} h approved remaining, but {commitment['unknown']} "
            "open project(s) have no approved estimate, so the real load is unknown."
        )
    return "capacity_indicated", (
        f"{allocatable} h allocatable against {remaining} h approved remaining as designer. Preliminary: planned "
        "leave and non-project work are not recorded."
    )


def recommend_candidates(
    db: Session,
    *,
    requirements: list[RequirementSpec],
    team_ids: set[UUID] | None,
    start: date | None = None,
    granularity: str = "week",
    periods: int = 4,
    today: date | None = None,
    exclude_user_ids: set[UUID] | None = None,
) -> dict:
    today = today or date.today()
    if not requirements:
        raise SkillValidationError("At least one skill requirement is needed.")
    skills = {s.id: s for s in db.scalars(select(Skill).where(Skill.id.in_([r.skill_id for r in requirements]))).all()}
    missing = [r.skill_id for r in requirements if r.skill_id not in skills]
    if missing:
        raise SkillNotFoundError("Skill not found.")
    for r in requirements:
        validate_level(r.min_level, field_name="min_level")

    capacity = build_capacity_forecast(
        db, start=start or today, granularity=granularity, periods=periods, team_ids=team_ids, as_of=today
    )
    people = [p for p in capacity.people if not exclude_user_ids or p.user_id not in exclude_user_ids]
    user_ids = {p.user_id for p in people}
    records = load_records(db, user_ids, set(skills))
    commitments = _commitments(db, user_ids, today)
    names = level_names(db)

    candidates = []
    for person in people:
        per_req = []
        for r in requirements:
            skill = skills[r.skill_id]
            record = records.get(person.user_id, {}).get(r.skill_id)
            state = requirement_state(record, skill, r.min_level, today)
            per_req.append(
                {
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                    "min_level": r.min_level,
                    "is_mandatory": r.is_mandatory,
                    "state": state,
                    "state_label": REQUIREMENT_STATES[state],
                    "verified_level": record.verified_level if record is not None else None,
                    "declared_level": record.declared_level if record is not None else None,
                }
            )
        mandatory = [x for x in per_req if x["is_mandatory"]] or per_req
        if all(x["state"] == "verified_meets" for x in mandatory):
            suitability = "confirmed"
        elif any(x["state"] == "verified_below" for x in mandatory):
            suitability = "below_requirement"
        else:
            suitability = "unconfirmed"
        allocatable = person.total.allocatable_hours
        commitment = commitments.get(person.user_id, {"open": 0, "unknown": 0, "approved_remaining": Decimal("0.00")})
        availability, availability_reason = _availability(allocatable, commitment)
        explanation = []
        for x in per_req:
            tag = "" if x["is_mandatory"] else " (optional)"
            level_text = f" — verified L{x['verified_level']}" if x["state"] in ("verified_meets", "verified_below", "reassessment_due") and x["verified_level"] else ""
            claim_text = f" — claims L{x['declared_level']}" if x["state"] in ("claimed_meets", "claimed_below") and x["declared_level"] else ""
            explanation.append(f"{x['skill_name']} ≥ L{x['min_level']}{tag}: {x['state_label']}{level_text}{claim_text}.")
        candidates.append(
            {
                "user_id": person.user_id,
                "name": person.name,
                "team_name": person.team_name,
                "suitability": suitability,
                "suitability_label": SUITABILITY_LABELS[suitability],
                "requirements": per_req,
                "verified_matches": sum(1 for x in per_req if x["state"] == "verified_meets"),
                "availability": availability,
                "availability_label": AVAILABILITY_LABELS[availability],
                "availability_reason": availability_reason,
                "allocatable_hours": allocatable,
                "approved_remaining_hours": commitment["approved_remaining"],
                "open_assignments": commitment["open"],
                "open_assignments_without_estimate": commitment["unknown"],
                "explanation": explanation,
            }
        )
    candidates.sort(
        key=lambda c: (_SUIT_RANK[c["suitability"]], _AVAIL_RANK[c["availability"]], -c["verified_matches"], c["name"])
    )
    return {
        "method_version": MATCHING_VERSION,
        "generated_for": today,
        "horizon_start": capacity.metadata.period_start,
        "horizon_end": capacity.metadata.period_end,
        "requirements": [
            {
                "skill_id": r.skill_id,
                "skill_name": skills[r.skill_id].name,
                "min_level": r.min_level,
                "min_level_name": names.get(r.min_level),
                "is_mandatory": r.is_mandatory,
            }
            for r in requirements
        ],
        "candidates": candidates,
        "summary": {
            "candidates": len(candidates),
            "confirmed": sum(1 for c in candidates if c["suitability"] == "confirmed"),
            "confirmed_with_capacity_indicated": sum(
                1 for c in candidates if c["suitability"] == "confirmed" and c["availability"] == "capacity_indicated"
            ),
            "unconfirmed": sum(1 for c in candidates if c["suitability"] == "unconfirmed"),
            "below_requirement": sum(1 for c in candidates if c["suitability"] == "below_requirement"),
        },
        "capacity_status": capacity.metadata.status,
        "capacity_limitations": capacity.metadata.limitations,
        "rules": [
            "Confirmed match needs a current verified record at or above the minimum level for every mandatory skill.",
            "Self-declared, pending, legacy and reassessment records never make a confirmed match.",
            "A missing record is unknown, not a confirmed lack of the skill.",
            "Suitability and availability are shown separately; there is no combined score.",
            "Availability comes from the Phase 3 capacity forecast (preliminary) and current open-project commitments.",
            "Recommendations never change assignments.",
        ],
    }
