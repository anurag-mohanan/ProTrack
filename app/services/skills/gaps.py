"""Skills gap, specialist-dependency and training reporting.

Coverage counts current verified records only. A single verified specialist is
reported as a *dependency*; whether the skill is critical is a management flag on
the skill, never inferred from the count. People with no record are reported as
"unknown", never as lacking the skill.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foundation import Skill, UserSkill
from app.models.models import Project, Team, TeamMember, User
from app.models.skills import (
    OPEN_PLAN_STATUSES,
    STATUS_NEEDS_REASSESSMENT,
    STATUS_VERIFIED,
    ProjectSkillRequirement,
    SkillDevelopmentPlan,
)
from app.services.forecasting.effort import open_projects
from app.services.skills.access import SkillAccess
from app.services.skills.coverage import (
    active_employee_ids,
    coverage_for_skills,
    specialist_level,
)
from app.services.skills.profiles import add_months, reassessment_due
from app.services.skills.taxonomy import level_names

GAPS_VERSION = "skills-gaps-1"


def _name(user: User) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def _skills(db: Session, *, category: str | None, kind: str | None, critical_only: bool, skill_ids: set[UUID] | None) -> list[Skill]:
    stmt = select(Skill).where(Skill.is_active.is_(True))
    if category:
        stmt = stmt.where(Skill.category == category)
    if kind:
        stmt = stmt.where(Skill.kind == kind)
    if critical_only:
        stmt = stmt.where(Skill.is_critical.is_(True))
    if skill_ids:
        stmt = stmt.where(Skill.id.in_(skill_ids))
    return list(db.scalars(stmt.order_by(Skill.category, Skill.sort_order, Skill.name)).all())


def build_gap_report(
    db: Session,
    access: SkillAccess,
    *,
    team_id: UUID | None = None,
    category: str | None = None,
    kind: str | None = None,
    critical_only: bool = False,
    min_level: int = 1,
    skill_ids: set[UUID] | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    visible = access.visible_user_ids(db, {team_id} if team_id else None)
    population = active_employee_ids(db, visible)
    skills = _skills(db, category=category, kind=kind, critical_only=critical_only, skill_ids=skill_ids)
    coverage = coverage_for_skills(db, skills, population, today)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(population))).all()} if population else {}
    names = level_names(db)

    rows = []
    findings = []
    for skill in skills:
        cov = coverage[skill.id]
        spec_level = specialist_level(skill)
        verified = cov.verified_at_or_above(min_level)
        specialists = cov.verified_at_or_above(spec_level)
        flags = []
        if not cov.verified_user_levels:
            flags.append("no_verified_coverage")
        if len(specialists) == 1:
            flags.append("single_verified_specialist")
        if cov.verified_user_levels and not specialists:
            flags.append("no_verified_specialist")
        if skill.min_verified_coverage and len(cov.verified_user_levels) < skill.min_verified_coverage:
            flags.append("below_coverage_target")
        if cov.reassessment_user_ids:
            flags.append("reassessment_pending")
        row = {
            "skill_id": skill.id,
            "skill_name": skill.name,
            "category": skill.category,
            "kind": skill.kind,
            "is_critical": bool(skill.is_critical),
            "specialist_level": spec_level,
            "specialist_level_name": names.get(spec_level),
            "min_verified_coverage": skill.min_verified_coverage,
            "verified_count": len(cov.verified_user_levels),
            "verified_at_min_level": len(verified),
            "verified_specialists": len(specialists),
            "specialist_names": sorted(_name(users[u]) for u in specialists if u in users),
            "claimed_unverified": len(cov.claimed_user_ids),
            "reassessment_due": len(cov.reassessment_user_ids),
            "rejected": len(cov.rejected_user_ids),
            "no_record": len(population - cov.recorded_user_ids),
            "population": len(population),
            "flags": flags,
        }
        rows.append(row)
        if skill.is_critical:
            if "no_verified_coverage" in flags:
                findings.append(_finding("critical_no_verified_coverage", "high", skill, row,
                    f"Critical skill '{skill.name}' has no verified employee in scope. {row['claimed_unverified']} unverified claim(s) and {row['no_record']} people without a record — unknown, not confirmed absent."))
            elif "single_verified_specialist" in flags:
                findings.append(_finding("critical_single_specialist", "high", skill, row,
                    f"Critical skill '{skill.name}' has one verified specialist at level {spec_level}+ ({', '.join(row['specialist_names']) or 'outside your scope'}). Plan knowledge transfer."))
            elif "no_verified_specialist" in flags:
                findings.append(_finding("critical_no_specialist", "medium", skill, row,
                    f"Critical skill '{skill.name}' has verified holders but none at specialist level {spec_level}+."))
            if "below_coverage_target" in flags:
                findings.append(_finding("critical_below_target", "medium", skill, row,
                    f"Critical skill '{skill.name}' has {row['verified_count']} verified holder(s) against a target of {skill.min_verified_coverage}."))
            if "reassessment_pending" in flags:
                findings.append(_finding("critical_reassessment", "medium", skill, row,
                    f"Critical skill '{skill.name}' has {row['reassessment_due']} verification(s) needing reassessment; they are not counted as coverage."))
        elif "single_verified_specialist" in flags:
            findings.append(_finding("single_specialist_dependency", "info", skill, row,
                f"'{skill.name}' depends on one verified specialist. It is not marked critical; management decides whether it matters."))

    team_depth = _team_depth(db, access, team_id, [s for s in skills if s.is_critical], coverage, population)
    return {
        "method_version": GAPS_VERSION,
        "as_of": today,
        "population": len(population),
        "skills": rows,
        "findings": findings,
        "team_depth": team_depth,
        "training": _training_rows(db, population, users, today),
        "reassessment": _reassessment_rows(db, population, users, today),
        "project_requirements": _project_requirement_rows(db, access, today),
        "rules": [
            "Coverage counts only current verified records (status verified, not past the skill's reassessment interval).",
            "Self-declared, pending, legacy, rejected and reassessment records are shown separately and never counted.",
            "People without a record are 'unknown', not people who lack the skill.",
            "Specialist level is the skill's configured specialist level (default 4 — Advanced).",
            "Critical skills are marked by management; a single specialist alone does not make a skill critical.",
        ],
    }


def _finding(code: str, severity: str, skill: Skill, row: dict, explanation: str) -> dict:
    return {
        "code": code,
        "severity": severity,
        "skill_id": skill.id,
        "skill_name": skill.name,
        "explanation": explanation,
        "evidence": {
            "verified": row["verified_count"],
            "verified_specialists": row["verified_specialists"],
            "claimed_unverified": row["claimed_unverified"],
            "reassessment_due": row["reassessment_due"],
            "no_record": row["no_record"],
        },
    }


def _team_depth(db: Session, access: SkillAccess, team_id: UUID | None, skills: list[Skill], coverage, population: set[UUID]) -> list[dict]:
    if not skills:
        return []
    stmt = select(Team).where(Team.is_active.is_(True))
    if team_id:
        stmt = stmt.where(Team.id == team_id)
    elif access.view_team_ids is not None:
        if not access.view_team_ids:
            return []
        stmt = stmt.where(Team.id.in_(access.view_team_ids))
    teams = list(db.scalars(stmt.order_by(Team.name)).all())
    members: dict[UUID, set[UUID]] = defaultdict(set)
    if population:
        for tid, uid in db.execute(select(TeamMember.team_id, TeamMember.user_id).where(TeamMember.user_id.in_(population))).all():
            members[tid].add(uid)
        for uid, tid in db.execute(select(User.id, User.team_id).where(User.id.in_(population), User.team_id.is_not(None))).all():
            members[tid].add(uid)
    out = []
    for team in teams:
        team_members = members.get(team.id, set())
        for skill in skills:
            specialists = coverage[skill.id].verified_at_or_above(specialist_level(skill)) & team_members
            out.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                    "members": len(team_members),
                    "verified_specialists": len(specialists),
                    "depth": "none" if not specialists else "single" if len(specialists) == 1 else "adequate",
                }
            )
    return out


def _training_rows(db: Session, population: set[UUID], users: dict[UUID, User], today: date) -> list[dict]:
    if not population:
        return []
    plans = list(
        db.scalars(
            select(SkillDevelopmentPlan).where(
                SkillDevelopmentPlan.user_id.in_(population), SkillDevelopmentPlan.status.in_(OPEN_PLAN_STATUSES)
            )
        ).all()
    )
    skills = {s.id: s.name for s in db.scalars(select(Skill).where(Skill.id.in_({p.skill_id for p in plans}))).all()} if plans else {}
    mentors = {u.id: _name(u) for u in db.scalars(select(User).where(User.id.in_({p.mentor_id for p in plans if p.mentor_id}))).all()} if plans else {}
    return [
        {
            "plan_id": p.id,
            "user_id": p.user_id,
            "name": _name(users[p.user_id]) if p.user_id in users else str(p.user_id),
            "skill_id": p.skill_id,
            "skill_name": skills.get(p.skill_id),
            "baseline_verified_level": p.baseline_verified_level,
            "target_level": p.target_level,
            "training_required": bool(p.training_required),
            "training_requirement": p.training_requirement,
            "is_knowledge_transfer": bool(p.is_knowledge_transfer),
            "mentor_name": mentors.get(p.mentor_id),
            "target_review_date": p.target_review_date,
            "overdue": bool(p.target_review_date and p.target_review_date < today),
            "status": p.status,
        }
        for p in sorted(plans, key=lambda x: (x.target_review_date or date.max))
    ]


def _reassessment_rows(db: Session, population: set[UUID], users: dict[UUID, User], today: date) -> list[dict]:
    if not population:
        return []
    rows = db.execute(
        select(UserSkill, Skill)
        .join(Skill, Skill.id == UserSkill.skill_id)
        .where(UserSkill.user_id.in_(population), UserSkill.status.in_((STATUS_VERIFIED, STATUS_NEEDS_REASSESSMENT)))
    ).all()
    out = []
    for record, skill in rows:
        due = record.status == STATUS_NEEDS_REASSESSMENT or reassessment_due(record, skill, today)
        if not due:
            continue
        out.append(
            {
                "record_id": record.id,
                "user_id": record.user_id,
                "name": _name(users[record.user_id]) if record.user_id in users else str(record.user_id),
                "skill_id": skill.id,
                "skill_name": skill.name,
                "verified_level": record.verified_level,
                "verified_at": record.verified_at,
                "reason": "Requested by a reviewer"
                if record.status == STATUS_NEEDS_REASSESSMENT
                else f"Verified more than {skill.reassessment_months} month(s) ago (due {add_months(record.verified_at.date(), int(skill.reassessment_months))})",
            }
        )
    return out


def requirement_coverage(db: Session, projects: list[Project], today: date) -> dict[UUID, list[dict]]:
    """Org-wide verified coverage of each open project's requirements (counts only)."""
    if not projects:
        return {}
    reqs = list(
        db.scalars(select(ProjectSkillRequirement).where(ProjectSkillRequirement.project_id.in_([p.id for p in projects]))).all()
    )
    if not reqs:
        return {}
    skills = list(db.scalars(select(Skill).where(Skill.id.in_({r.skill_id for r in reqs}))).all())
    population = active_employee_ids(db)
    coverage = coverage_for_skills(db, skills, population, today)
    by_id = {s.id: s for s in skills}
    out: dict[UUID, list[dict]] = defaultdict(list)
    for r in reqs:
        cov = coverage[r.skill_id]
        holders = cov.verified_at_or_above(r.min_level)
        out[r.project_id].append(
            {
                "requirement_id": r.id,
                "skill_id": r.skill_id,
                "skill_name": by_id[r.skill_id].name,
                "is_critical": bool(by_id[r.skill_id].is_critical),
                "min_level": r.min_level,
                "is_mandatory": bool(r.is_mandatory),
                "verified_holders": len(holders),
                "verified_holder_ids": holders,
                "claimed_unverified": len(cov.claimed_user_ids),
                "reassessment_due": len(cov.reassessment_user_ids),
            }
        )
    return dict(out)


def _project_requirement_rows(db: Session, access: SkillAccess, today: date) -> list[dict]:
    from app.core.team_access import project_visibility_clause

    projects = open_projects(db, visibility_clause=project_visibility_clause(db, access.user))
    coverage = requirement_coverage(db, projects, today)
    rows = []
    for p in projects:
        for req in coverage.get(p.id, []):
            rows.append(
                {
                    "project_id": p.id,
                    "tool_number": p.tool_number,
                    "part_description": p.part_description,
                    **{k: v for k, v in req.items() if k != "verified_holder_ids"},
                    "status": "no_verified_coverage"
                    if req["verified_holders"] == 0
                    else "single_verified_holder"
                    if req["verified_holders"] == 1
                    else "covered",
                }
            )
    return rows
