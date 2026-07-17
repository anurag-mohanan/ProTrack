"""Assignment skill-fit vs project complexity."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.enums import SkillProficiency
from app.models.models import Stream, StreamSkill, UserSkillRating
from app.services.assignment_skill_fit_service import evaluate_assignment_skill_fit
from tests.conftest import IDS, login


def _ensure_skill_rating(session, *, user_id, skill_name: str, proficiency: SkillProficiency):
    skill = session.scalar(select(StreamSkill).where(StreamSkill.name == skill_name))
    if skill is None:
        stream = session.get(Stream, IDS["stream"]) if "stream" in IDS else None
        if stream is None:
            stream = session.scalar(select(Stream))
        assert stream is not None
        skill = StreamSkill(
            id=uuid.uuid4(),
            stream_id=stream.id,
            name=skill_name,
            sort_order=0,
            is_active=True,
        )
        session.add(skill)
        session.flush()
    existing = session.scalar(
        select(UserSkillRating).where(
            UserSkillRating.user_id == user_id,
            UserSkillRating.stream_skill_id == skill.id,
        )
    )
    if existing is None:
        session.add(
            UserSkillRating(
                id=uuid.uuid4(),
                user_id=user_id,
                stream_skill_id=skill.id,
                proficiency=proficiency,
            )
        )
    else:
        existing.proficiency = proficiency
    session.commit()


def test_high_complexity_warns_when_complex_design_is_developing(session):
    _ensure_skill_rating(
        session,
        user_id=IDS["user_binil"],
        skill_name="Complex Design",
        proficiency=SkillProficiency.developing,
    )
    result = evaluate_assignment_skill_fit(
        session,
        user_id=IDS["user_binil"],
        complexity="high",
        role="designer",
    )
    assert result["requires_confirmation"] is True
    assert result["warnings"]


def test_high_complexity_ok_when_complex_design_is_proficient(session):
    _ensure_skill_rating(
        session,
        user_id=IDS["user_binil"],
        skill_name="Complex Design",
        proficiency=SkillProficiency.proficient,
    )
    result = evaluate_assignment_skill_fit(
        session,
        user_id=IDS["user_binil"],
        complexity="high",
        role="designer",
    )
    assert result["requires_confirmation"] is False


def test_assignment_fit_api(client, session):
    _ensure_skill_rating(
        session,
        user_id=IDS["user_binil"],
        skill_name="Complex Design",
        proficiency=SkillProficiency.learning,
    )
    headers = login(client, "anurag@prosohm.com")
    response = client.get(
        f"/api/v1/hr/performance/assignment-fit?user_id={IDS['user_binil']}&complexity=expert&role=designer",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requires_confirmation"] is True
