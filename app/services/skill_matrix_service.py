"""Team skill matrix helpers — stream skills + industry-style proficiency levels."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import SkillProficiency
from app.models.models import Stream, StreamSkill, Team, TeamMember, User, UserSkillRating
from app.services.performance_review_service import format_tenure

# Excel PP skill chart for mold design (industry-aligned 4-level scale).
MOLD_DESIGN_SKILLS: list[str] = [
    "Complex Design",
    "Design",
    "Surfacing",
    "Checking",
    "NX Open / NX Programming",
    "NX Customization",
]

# Optional default skill packs keyed by normalized stream name substrings.
STREAM_SKILL_PACKS: list[tuple[tuple[str, ...], list[str]]] = [
    (("mold",), MOLD_DESIGN_SKILLS),
    (
        ("biw", "body"),
        ["Complex Design", "Design", "Checking", "Feasibility", "CATIA", "Automation"],
    ),
    (
        ("plastic", "injection"),
        ["Complex Design", "Design", "Surfacing", "Checking", "Estimation", "Customization"],
    ),
]

PROFICIENCY_META: list[dict[str, str]] = [
    {
        "value": SkillProficiency.learning.value,
        "label": "Learning",
        "short_label": "L",
        "tone": "error",
        "guidance": "Needs guidance — building fundamentals.",
    },
    {
        "value": SkillProficiency.developing.value,
        "label": "Developing",
        "short_label": "D",
        "tone": "warning",
        "guidance": "Can deliver with support — growing independence.",
    },
    {
        "value": SkillProficiency.proficient.value,
        "label": "Proficient",
        "short_label": "P",
        "tone": "success",
        "guidance": "Delivers independently to expected quality.",
    },
    {
        "value": SkillProficiency.expert.value,
        "label": "Expert",
        "short_label": "E",
        "tone": "info",
        "guidance": "Sets the standard and coaches others.",
    },
]


def _normalize(value: str) -> str:
    return value.strip().lower()


def default_skills_for_stream_name(stream_name: str) -> list[str]:
    name = _normalize(stream_name)
    for needles, skills in STREAM_SKILL_PACKS:
        if any(needle in name for needle in needles):
            return list(skills)
    return list(MOLD_DESIGN_SKILLS)


def ensure_stream_skills(db: Session, stream: Stream) -> list[StreamSkill]:
    existing = db.scalars(
        select(StreamSkill)
        .where(StreamSkill.stream_id == stream.id)
        .order_by(StreamSkill.sort_order, StreamSkill.name)
    ).all()
    if existing:
        return list(existing)

    skills: list[StreamSkill] = []
    for index, name in enumerate(default_skills_for_stream_name(stream.name)):
        skills.append(
            StreamSkill(
                stream_id=stream.id,
                name=name,
                sort_order=index,
                is_active=True,
            )
        )
    db.add_all(skills)
    db.flush()
    return skills


def build_team_skill_matrix(
    db: Session,
    *,
    team_id: UUID | None = None,
    team_ids: list[UUID] | None = None,
    stream_id: UUID | None = None,
) -> dict[str, Any]:
    scope_ids: list[UUID]
    if team_id is not None:
        scope_ids = [team_id]
    elif team_ids:
        scope_ids = list(team_ids)
    else:
        scope_ids = []

    if not scope_ids:
        return {
            "team_id": None,
            "stream_id": stream_id,
            "stream_name": None,
            "title": "Team skill matrix",
            "proficiency_scale": PROFICIENCY_META,
            "skills": [],
            "people": [],
        }

    members = db.scalars(
        select(User)
        .join(TeamMember, TeamMember.user_id == User.id)
        .options(selectinload(User.stream), selectinload(User.role))
        .where(
            TeamMember.team_id.in_(scope_ids),
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        )
        .order_by(User.first_name, User.last_name)
    ).all()

    # De-dupe users who belong to multiple teams in the All-teams scope.
    unique_members: list[User] = []
    seen_users: set[UUID] = set()
    for member in members:
        if member.id in seen_users:
            continue
        seen_users.add(member.id)
        unique_members.append(member)
    members = unique_members

    # Prefer primary membership team name when a user sits on multiple teams in scope.
    team_name_by_id = {
        row.id: row.name
        for row in db.scalars(select(Team).where(Team.id.in_(scope_ids))).all()
    }
    preferred_team_by_user: dict[UUID, UUID] = {}
    if members:
        memberships = db.scalars(
            select(TeamMember).where(
                TeamMember.team_id.in_(scope_ids),
                TeamMember.user_id.in_([row.id for row in members]),
            )
        ).all()
        for membership in memberships:
            current = preferred_team_by_user.get(membership.user_id)
            if current is None or membership.is_primary:
                preferred_team_by_user[membership.user_id] = membership.team_id

    if stream_id is not None:
        members = [row for row in members if row.stream_id == stream_id]

    stream: Stream | None = None
    if stream_id is not None:
        stream = db.get(Stream, stream_id)
    elif members:
        # Prefer the most common stream among members; else first assigned.
        counts: dict[UUID, int] = {}
        for member in members:
            if member.stream_id is None:
                continue
            counts[member.stream_id] = counts.get(member.stream_id, 0) + 1
        if counts:
            top_stream_id = max(counts.items(), key=lambda item: item[1])[0]
            stream = db.get(Stream, top_stream_id)
            members = [row for row in members if row.stream_id == top_stream_id]

    skills: list[StreamSkill] = []
    if stream is not None:
        skills = ensure_stream_skills(db, stream)

    skill_ids = [skill.id for skill in skills]
    ratings_by_user: dict[UUID, dict[UUID, UserSkillRating]] = {}
    if skill_ids and members:
        ratings = db.scalars(
            select(UserSkillRating).where(
                UserSkillRating.user_id.in_([row.id for row in members]),
                UserSkillRating.stream_skill_id.in_(skill_ids),
            )
        ).all()
        for rating in ratings:
            ratings_by_user.setdefault(rating.user_id, {})[rating.stream_skill_id] = rating

    people: list[dict[str, Any]] = []
    for member in members:
        member_ratings = ratings_by_user.get(member.id, {})
        member_team_id = preferred_team_by_user.get(member.id)
        people.append(
            {
                "user_id": member.id,
                "name": f"{member.first_name} {member.last_name}".strip(),
                "role": member.designation
                or (member.role.name if member.role is not None else None),
                "primary_tool": member.primary_tool or "NX Local",
                "work_function": member.work_function or "Design/Surfacing",
                "team_id": member_team_id,
                "team_name": team_name_by_id.get(member_team_id) if member_team_id else None,
                "stream_id": member.stream_id,
                "stream_name": member.stream.name if member.stream is not None else None,
                "company_experience": format_tenure(member.joining_date),
                "industry_experience": format_tenure(member.first_job_date),
                "joining_date": member.joining_date,
                "first_job_date": member.first_job_date,
                "ratings": {
                    str(skill.id): (
                        member_ratings[skill.id].proficiency.value
                        if skill.id in member_ratings
                        else None
                    )
                    for skill in skills
                },
            }
        )

    scope_label = (
        team_name_by_id.get(team_id, "Team")
        if team_id is not None
        else "All teams"
    )
    return {
        "team_id": team_id,
        "stream_id": stream.id if stream is not None else None,
        "stream_name": stream.name if stream is not None else None,
        "title": (
            f"{stream.name} skill matrix · {scope_label}"
            if stream is not None
            else f"Skill matrix · {scope_label}"
        ),
        "proficiency_scale": PROFICIENCY_META,
        "skills": [
            {
                "id": skill.id,
                "name": skill.name,
                "sort_order": skill.sort_order,
            }
            for skill in skills
        ],
        "people": people,
    }


def upsert_skill_ratings(
    db: Session,
    *,
    ratings: list[dict[str, Any]],
    assessed_by_id: UUID,
) -> int:
    updated = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in ratings:
        user_id = row["user_id"]
        stream_skill_id = row["stream_skill_id"]
        proficiency_raw = row.get("proficiency")
        if proficiency_raw in (None, ""):
            existing = db.scalar(
                select(UserSkillRating).where(
                    UserSkillRating.user_id == user_id,
                    UserSkillRating.stream_skill_id == stream_skill_id,
                )
            )
            if existing is not None:
                db.delete(existing)
                updated += 1
            continue
        try:
            proficiency = SkillProficiency(str(proficiency_raw))
        except ValueError:
            continue
        existing = db.scalar(
            select(UserSkillRating).where(
                UserSkillRating.user_id == user_id,
                UserSkillRating.stream_skill_id == stream_skill_id,
            )
        )
        if existing is None:
            db.add(
                UserSkillRating(
                    user_id=user_id,
                    stream_skill_id=stream_skill_id,
                    proficiency=proficiency,
                    assessed_by_id=assessed_by_id,
                    assessed_at=now,
                    notes=row.get("notes"),
                )
            )
        else:
            existing.proficiency = proficiency
            existing.assessed_by_id = assessed_by_id
            existing.assessed_at = now
            if row.get("notes") is not None:
                existing.notes = row.get("notes")
        updated += 1
    return updated
