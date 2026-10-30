"""Read models for the skills API. Confidential notes are only included for authorised reviewers."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.foundation import EngineeringDiscipline, Skill, UserSkill
from app.models.models import Customer, Team, User
from app.models.skills import (
    OPEN_PLAN_STATUSES,
    STATUS_ARCHIVED,
    STATUS_NEEDS_REASSESSMENT,
    STATUS_PENDING,
    STATUS_VERIFIED,
    SkillDevelopmentPlan,
    SkillRelationship,
)
from app.services.skills.access import SkillAccess
from app.services.skills.coverage import active_employee_ids
from app.services.skills.experience import evidence_for_records
from app.services.skills.naming import parse_aliases
from app.services.skills.profiles import (
    ORIGIN_LABELS,
    VERIFICATION_METHODS,
    claim_pending,
    display_state,
    events_for_record,
    reassessment_due,
    records_for_user,
)
from app.services.skills.taxonomy import (
    RELATION_TYPES,
    SKILL_KINDS,
    holder_counts,
    level_names,
    proficiency_framework,
)
from app.services.user_team_service import get_user_team_ids

STATE_LABELS = {
    "no_record": "No record",
    "claimed": "Self-declared / unverified",
    "verified": "Verified",
    "reassessment": "Needs reassessment",
    "rejected": "Not confirmed",
    "archived": "Archived",
}


def _name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def _users(db: Session, ids: set[UUID]) -> dict[UUID, User]:
    ids = {i for i in ids if i}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}


def skill_read(skill: Skill, *, disciplines: dict, customers: dict, holders: dict | None = None) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "category": skill.category,
        "kind": skill.kind,
        "kind_label": SKILL_KINDS.get(skill.kind) if skill.kind else None,
        "description": skill.description,
        "aliases": parse_aliases(skill.aliases),
        "discipline_id": skill.discipline_id,
        "discipline_name": disciplines.get(skill.discipline_id),
        "customer_id": skill.customer_id,
        "customer_name": customers.get(skill.customer_id),
        "is_critical": bool(skill.is_critical),
        "min_verified_coverage": skill.min_verified_coverage,
        "specialist_level": skill.specialist_level,
        "reassessment_months": skill.reassessment_months,
        "sort_order": skill.sort_order or 0,
        "is_active": bool(skill.is_active),
        "holder_count": (holders or {}).get(skill.id, 0),
    }


def taxonomy_read(db: Session, *, include_inactive: bool) -> dict:
    stmt = select(Skill)
    if not include_inactive:
        stmt = stmt.where(Skill.is_active.is_(True))
    skills = list(db.scalars(stmt.order_by(Skill.category, Skill.sort_order, Skill.name)).all())
    disciplines = {d.id: d.name for d in db.scalars(select(EngineeringDiscipline)).all()}
    customer_ids = {s.customer_id for s in skills if s.customer_id}
    customers = {c.id: c.name for c in db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()} if customer_ids else {}
    holders = holder_counts(db)
    skill_ids = {s.id for s in skills}
    names = {s.id: s.name for s in skills}
    relationships = [
        {
            "id": r.id,
            "from_skill_id": r.from_skill_id,
            "from_skill_name": names.get(r.from_skill_id),
            "to_skill_id": r.to_skill_id,
            "to_skill_name": names.get(r.to_skill_id),
            "relation_type": r.relation_type,
            "relation_label": RELATION_TYPES.get(r.relation_type, r.relation_type),
            "note": r.note,
        }
        for r in db.scalars(select(SkillRelationship)).all()
        if r.from_skill_id in skill_ids and r.to_skill_id in skill_ids
    ]
    categories = sorted({s.category for s in skills if s.category})
    return {
        "skills": [skill_read(s, disciplines=disciplines, customers=customers, holders=holders) for s in skills],
        "categories": categories,
        "kinds": [{"value": k, "label": v} for k, v in SKILL_KINDS.items()],
        "relation_types": [{"value": k, "label": v} for k, v in RELATION_TYPES.items()],
        "relationships": relationships,
        "proficiency_levels": proficiency_framework(db),
        "disciplines": [{"id": d_id, "name": name} for d_id, name in sorted(disciplines.items(), key=lambda x: x[1])],
        "verification_methods": [{"value": k, "label": v} for k, v in VERIFICATION_METHODS.items()],
    }


def _record_read(record: UserSkill, skill: Skill, *, users: dict, today: date, show_confidential: bool) -> dict:
    state = display_state(record, skill, today)
    return {
        "id": record.id,
        "user_id": record.user_id,
        "skill_id": skill.id,
        "skill_name": skill.name,
        "category": skill.category,
        "kind": skill.kind,
        "skill_is_active": bool(skill.is_active),
        "status": record.status,
        "state": state,
        "state_label": STATE_LABELS[state],
        "origin": record.origin,
        "origin_label": ORIGIN_LABELS.get(record.origin, record.origin),
        "declared_level": record.declared_level,
        "verified_level": record.verified_level,
        "claim_pending": claim_pending(record),
        "reassessment_due": reassessment_due(record, skill, today),
        "legacy_proficiency": record.proficiency.value if record.proficiency is not None else None,
        "verification_method": record.verification_method,
        "verification_method_label": VERIFICATION_METHODS.get(record.verification_method) if record.verification_method else None,
        "verified_at": record.verified_at,
        "verified_by_name": _name(users.get(record.verified_by_id)),
        "last_assessed_at": record.last_assessed_at,
        "last_assessed_by_name": _name(users.get(record.last_assessed_by_id)),
        "years_experience": record.years_experience,
        "last_used_on": record.last_used_on,
        "employee_note": record.employee_note,
        "assessment_feedback": record.assessment_feedback,
        "confidential_notes": record.confidential_notes if show_confidential else None,
        "confidential_hidden": (not show_confidential) and bool(record.confidential_notes),
        "updated_at": record.updated_at,
    }


def _event_read(event, *, users: dict, show_confidential: bool) -> dict:
    return {
        "id": event.id,
        "action": event.action,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "from_declared_level": event.from_declared_level,
        "to_declared_level": event.to_declared_level,
        "from_verified_level": event.from_verified_level,
        "to_verified_level": event.to_verified_level,
        "verification_method": event.verification_method,
        "actor_name": _name(users.get(event.actor_id)),
        "occurred_at": event.occurred_at,
        "feedback": event.feedback,
        "confidential_note": event.confidential_note if show_confidential else None,
        "detail": event.detail,
    }


def profile_read(db: Session, access: SkillAccess, subject: User, *, include_archived: bool = False) -> dict:
    today = date.today()
    show_confidential = access.can_review(db, subject.id)
    records = records_for_user(db, subject.id, include_archived=include_archived)
    events = {r.id: events_for_record(db, r.id) for r in records}
    user_ids = {subject.id}
    for r in records:
        user_ids |= {r.verified_by_id, r.last_assessed_by_id}
        user_ids |= {e.actor_id for e in events[r.id]}
    users = _users(db, user_ids)
    evidence = evidence_for_records(db, access.user, [r.id for r in records])
    team_ids = get_user_team_ids(db, subject.id)
    teams = [t.name for t in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()] if team_ids else []
    rows = []
    for r in sorted(records, key=lambda x: ((x.skill.category or ""), x.skill.name)):
        row = _record_read(r, r.skill, users=users, today=today, show_confidential=show_confidential)
        row["evidence"] = evidence.get(r.id, [])
        row["history"] = [_event_read(e, users=users, show_confidential=show_confidential) for e in events[r.id]]
        rows.append(row)
    return {
        "user_id": subject.id,
        "name": _name(subject),
        "designation": subject.designation,
        "teams": sorted(teams),
        "is_self": subject.id == access.user.id,
        "can_review": show_confidential,
        "can_declare": subject.id == access.user.id,
        "records": rows,
        "proficiency_levels": proficiency_framework(db),
    }


def matrix_read(
    db: Session,
    access: SkillAccess,
    *,
    team_id: UUID | None = None,
    category: str | None = None,
    kind: str | None = None,
    software_skill_id: UUID | None = None,
    min_level: int | None = None,
    states: set[str] | None = None,
    q: str | None = None,
    critical_only: bool = False,
) -> dict:
    today = date.today()
    visible = access.visible_user_ids(db, {team_id} if team_id else None)
    population = active_employee_ids(db, visible)
    people = list(
        db.scalars(select(User).where(User.id.in_(population)).order_by(User.first_name, User.last_name)).all()
    ) if population else []
    skill_stmt = select(Skill).where(Skill.is_active.is_(True))
    if category:
        skill_stmt = skill_stmt.where(Skill.category == category)
    if kind:
        skill_stmt = skill_stmt.where(Skill.kind == kind)
    if critical_only:
        skill_stmt = skill_stmt.where(Skill.is_critical.is_(True))
    skills = list(db.scalars(skill_stmt.order_by(Skill.category, Skill.sort_order, Skill.name)).all())
    needle = (q or "").strip().lower()
    if needle:
        skill_hits = [s for s in skills if needle in s.name.lower() or any(needle in a.lower() for a in parse_aliases(s.aliases))]
        person_hits = [p for p in people if needle in (_name(p) or "").lower()]
        if skill_hits and not person_hits:
            skills = skill_hits
        elif person_hits and not skill_hits:
            people = person_hits
        else:
            skills = skill_hits or skills
            people = person_hits or people
    records: dict[UUID, dict[UUID, UserSkill]] = defaultdict(dict)
    if people and skills:
        for r in db.scalars(
            select(UserSkill).where(
                UserSkill.user_id.in_([p.id for p in people]),
                UserSkill.skill_id.in_([s.id for s in skills]),
                UserSkill.status != STATUS_ARCHIVED,
            )
        ).all():
            records[r.user_id][r.skill_id] = r
    if software_skill_id is not None:
        people = [p for p in people if software_skill_id in records.get(p.id, {})]
    team_names = {t.id: t.name for t in db.scalars(select(Team)).all()}
    plan_counts = dict(
        db.execute(
            select(SkillDevelopmentPlan.user_id, func.count(SkillDevelopmentPlan.id))
            .where(SkillDevelopmentPlan.status.in_(OPEN_PLAN_STATUSES), SkillDevelopmentPlan.training_required.is_(True))
            .group_by(SkillDevelopmentPlan.user_id)
        ).all()
    )
    reviewable = access.reviewable_user_ids(db)
    rows = []
    for p in people:
        cells = {}
        any_match = False
        for s in skills:
            r = records.get(p.id, {}).get(s.id)
            state = display_state(r, s, today)
            level = (r.verified_level if state in ("verified", "reassessment") else r.declared_level) if r else None
            matches = True
            if states and state not in states:
                matches = False
            if min_level is not None and (level is None or level < min_level):
                matches = False
            any_match = any_match or (matches and state != "no_record")
            cells[str(s.id)] = {
                "record_id": r.id if r else None,
                "state": state,
                "verified_level": r.verified_level if r else None,
                "declared_level": r.declared_level if r else None,
                "claim_pending": claim_pending(r) if r else False,
                "last_verified_at": r.verified_at if r else None,
                "matches": matches,
            }
        if (states or min_level is not None) and not any_match:
            continue
        rows.append(
            {
                "user_id": p.id,
                "name": _name(p),
                "designation": p.designation,
                "team_name": team_names.get(p.team_id) if p.team_id else None,
                "training_plans_open": int(plan_counts.get(p.id, 0)),
                "can_review": p.id != access.user.id and (reviewable is None or p.id in reviewable),
                "cells": cells,
            }
        )
    return {
        "skills": [
            {"id": s.id, "name": s.name, "category": s.category, "kind": s.kind, "is_critical": bool(s.is_critical)}
            for s in skills
        ],
        "people": rows,
        "proficiency_levels": proficiency_framework(db),
        "state_labels": STATE_LABELS,
        "legend": [
            "No record: nothing recorded — unknown, not level 0.",
            "Self-declared / unverified: the employee's claim (or a legacy or manager-entered record awaiting review).",
            "Verified: confirmed by a reviewer; the number is the verified level.",
            "Needs reassessment: an earlier verification that must be reviewed again; not counted as coverage.",
        ],
    }


def review_queue(db: Session, access: SkillAccess) -> list[dict]:
    reviewable = access.reviewable_user_ids(db)
    if reviewable is not None and not reviewable:
        return []
    stmt = (
        select(UserSkill, Skill)
        .join(Skill, Skill.id == UserSkill.skill_id)
        .where(
            or_(
                UserSkill.status.in_((STATUS_PENDING, STATUS_NEEDS_REASSESSMENT)),
                UserSkill.status == STATUS_VERIFIED,
            )
        )
    )
    if reviewable is not None:
        stmt = stmt.where(UserSkill.user_id.in_(reviewable))
    today = date.today()
    rows = []
    active = active_employee_ids(db, reviewable)
    pairs = [(r, s) for r, s in db.execute(stmt).all() if r.user_id in active and r.user_id != access.user.id]
    users = _users(db, {r.user_id for r, _ in pairs})
    for record, skill in pairs:
        if record.status == STATUS_VERIFIED and not (claim_pending(record) or reassessment_due(record, skill, today)):
            continue
        reason = (
            "Awaiting verification"
            if record.status == STATUS_PENDING
            else "Reassessment requested"
            if record.status == STATUS_NEEDS_REASSESSMENT
            else "Reassessment interval passed"
            if reassessment_due(record, skill, today)
            else "New claim on a verified skill"
        )
        rows.append(
            {
                "record_id": record.id,
                "user_id": record.user_id,
                "name": _name(users.get(record.user_id)),
                "skill_id": skill.id,
                "skill_name": skill.name,
                "status": record.status,
                "origin": record.origin,
                "declared_level": record.declared_level,
                "verified_level": record.verified_level,
                "reason": reason,
                "since": record.status_changed_at or record.updated_at,
            }
        )
    rows.sort(key=lambda x: (x["since"] is None, x["since"]))
    return rows


def level_name_map(db: Session) -> dict[int, str]:
    return level_names(db)
