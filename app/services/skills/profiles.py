"""Employee skill records and the verification workflow.

Rules:

* A record is created by the employee (self-declared), by a reviewer
  (manager-entered) or came from the legacy settings endpoint. Only a review
  decision sets ``verified_level``; declaring, submitting, project evidence and
  completed development plans never do.
* A verified record is never changed silently. A new claim on a verified record
  keeps the verified level and is shown as awaiting review; every change writes a
  ``user_skill_events`` row and an ``activities`` entry (without comments).
* "Current verified coverage" means status ``verified`` and not past the skill's
  reassessment interval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ActivityAction, EntityType, SkillLevel
from app.models.foundation import Skill, UserSkill
from app.models.models import User
from app.models.skills import (
    ORIGIN_LEGACY,
    ORIGIN_MANAGER,
    ORIGIN_SELF,
    STATUS_ARCHIVED,
    STATUS_NEEDS_REASSESSMENT,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_SELF_DECLARED,
    STATUS_VERIFIED,
    UserSkillEvent,
)
from app.services.activity_service import log_activity
from app.services.skills.access import SkillAccess
from app.services.skills.errors import (
    SkillNotFoundError,
    SkillPermissionError,
    SkillValidationError,
)
from app.services.skills.taxonomy import validate_level

METHOD_MANAGER = "manager_assessment"
METHOD_INDEPENDENT = "independent_assessment"
VERIFICATION_METHODS = {
    METHOD_MANAGER: "Manager assessment",
    METHOD_INDEPENDENT: "Independent verification (technical panel, test or certification)",
}

DECISION_VERIFY = "verify"
DECISION_REJECT = "reject"
DECISION_REASSESS = "request_reassessment"
DECISIONS = (DECISION_VERIFY, DECISION_REJECT, DECISION_REASSESS)

# Legacy four-value field kept in step for the old profile and settings endpoints.
_LEGACY_BY_LEVEL = {
    1: SkillLevel.beginner,
    2: SkillLevel.beginner,
    3: SkillLevel.intermediate,
    4: SkillLevel.advanced,
    5: SkillLevel.expert,
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    for candidate in (31, 30, 29, 28):
        try:
            return date(year, month, min(day.day, candidate))
        except ValueError:
            continue
    return date(year, month, 28)


def reassessment_due(record: UserSkill, skill: Skill, today: date) -> bool:
    if record.status != STATUS_VERIFIED or not skill.reassessment_months or record.verified_at is None:
        return False
    return add_months(record.verified_at.date(), int(skill.reassessment_months)) <= today


def is_current_verified(record: UserSkill, skill: Skill, today: date) -> bool:
    return record.status == STATUS_VERIFIED and record.verified_level is not None and not reassessment_due(record, skill, today)


def claim_pending(record: UserSkill) -> bool:
    return (
        record.status == STATUS_VERIFIED
        and record.declared_level is not None
        and record.verified_level is not None
        and record.declared_level != record.verified_level
    )


def display_state(record: UserSkill | None, skill: Skill, today: date) -> str:
    """One of: no_record, claimed, verified, reassessment, rejected, archived."""
    if record is None:
        return "no_record"
    if record.status == STATUS_ARCHIVED:
        return "archived"
    if record.status == STATUS_REJECTED:
        return "rejected"
    if record.status == STATUS_NEEDS_REASSESSMENT or reassessment_due(record, skill, today):
        return "reassessment"
    if record.status == STATUS_VERIFIED:
        return "verified"
    return "claimed"


def _record_event(
    db: Session,
    record: UserSkill,
    *,
    actor: User | None,
    action: str,
    before: dict,
    method: str | None = None,
    feedback: str | None = None,
    confidential_note: str | None = None,
    detail: str | None = None,
) -> UserSkillEvent:
    event = UserSkillEvent(
        user_skill_id=record.id,
        subject_user_id=record.user_id,
        skill_id=record.skill_id,
        actor_id=actor.id if actor else None,
        action=action,
        from_status=before.get("status"),
        to_status=record.status,
        from_declared_level=before.get("declared_level"),
        to_declared_level=record.declared_level,
        from_verified_level=before.get("verified_level"),
        to_verified_level=record.verified_level,
        verification_method=method,
        feedback=feedback,
        confidential_note=confidential_note,
        detail=detail,
        occurred_at=_now(),
    )
    db.add(event)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.user,
        entity_id=record.user_id,
        action=ActivityAction.skill_profile_changed,
        old_value={"skill_id": str(record.skill_id), **before},
        new_value={
            "skill_id": str(record.skill_id),
            "action": action,
            "status": record.status,
            "declared_level": record.declared_level,
            "verified_level": record.verified_level,
        },
        module="skills",
        commit=False,
    )
    return event


def _state(record: UserSkill) -> dict:
    return {
        "status": record.status,
        "declared_level": record.declared_level,
        "verified_level": record.verified_level,
    }


def _set_status(record: UserSkill, status: str) -> None:
    if record.status != status:
        record.status = status
        record.status_changed_at = _now()


def get_record(db: Session, record_id: UUID) -> UserSkill:
    record = db.scalar(select(UserSkill).options(selectinload(UserSkill.skill)).where(UserSkill.id == record_id))
    if record is None:
        raise SkillNotFoundError("Skill record not found.")
    return record


def find_record(db: Session, user_id: UUID, skill_id: UUID) -> UserSkill | None:
    return db.scalar(select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.skill_id == skill_id))


def _active_skill(db: Session, skill_id: UUID) -> Skill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise SkillNotFoundError("Skill not found.")
    if not skill.is_active:
        raise SkillValidationError(f"'{skill.name}' is inactive and cannot be declared.")
    return skill


def _active_subject(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None or getattr(user, "is_deleted", False):
        raise SkillNotFoundError("Employee not found.")
    return user


@dataclass
class Declaration:
    skill_id: UUID
    declared_level: int
    years_experience: Decimal | None = None
    last_used_on: date | None = None
    employee_note: str | None = None
    submit_for_verification: bool = False


def declare_skill(db: Session, access: SkillAccess, data: Declaration) -> UserSkill:
    """The signed-in employee declares or updates their own claim."""
    actor = access.user
    skill = _active_skill(db, data.skill_id)
    level = validate_level(data.declared_level, field_name="declared_level")
    if data.years_experience is not None and (data.years_experience < 0 or data.years_experience > 60):
        raise SkillValidationError("years_experience must be between 0 and 60.")
    if data.last_used_on is not None and data.last_used_on > date.today():
        raise SkillValidationError("last_used_on cannot be in the future.")
    record = find_record(db, actor.id, skill.id)
    note = (data.employee_note or "").strip() or None
    if record is None:
        record = UserSkill(
            user_id=actor.id,
            skill_id=skill.id,
            origin=ORIGIN_SELF,
            status=STATUS_PENDING if data.submit_for_verification else STATUS_SELF_DECLARED,
            status_changed_at=_now(),
            declared_level=level,
            proficiency=_LEGACY_BY_LEVEL[level],
            years_experience=data.years_experience,
            last_used_on=data.last_used_on,
            employee_note=note,
            updated_by_id=actor.id,
        )
        db.add(record)
        db.flush()
        _record_event(db, record, actor=actor, action="declared", before={})
        return record

    before = _state(record)
    record.declared_level = level
    record.years_experience = data.years_experience
    record.last_used_on = data.last_used_on
    record.employee_note = note
    record.updated_by_id = actor.id
    if record.verified_level is None:
        record.proficiency = _LEGACY_BY_LEVEL[level]
    if record.status == STATUS_ARCHIVED:
        # An archived verification does not carry over to a new claim; the event keeps the old level.
        record.verified_level = None
        record.verified_at = None
        record.verified_by_id = None
        record.verification_method = None
        record.proficiency = _LEGACY_BY_LEVEL[level]
        _set_status(record, STATUS_PENDING if data.submit_for_verification else STATUS_SELF_DECLARED)
        action = "redeclared"
    elif record.status in (STATUS_SELF_DECLARED, STATUS_REJECTED):
        if data.submit_for_verification:
            _set_status(record, STATUS_PENDING)
        elif record.status == STATUS_REJECTED and before["declared_level"] != level:
            _set_status(record, STATUS_SELF_DECLARED)
        action = "claim_updated"
    else:
        # pending / verified / needs reassessment keep their status; a verified level is never changed here.
        action = "claim_updated"
    db.flush()
    if _state(record) != before or action == "redeclared":
        _record_event(db, record, actor=actor, action=action, before=before)
    return record


def submit_for_verification(db: Session, access: SkillAccess, record: UserSkill) -> UserSkill:
    if record.user_id != access.user.id:
        raise SkillPermissionError("Only the employee can submit their own claim.")
    if record.declared_level is None:
        raise SkillValidationError("Declare a level before submitting.")
    if record.status not in (STATUS_SELF_DECLARED, STATUS_REJECTED):
        raise SkillValidationError(f"A record that is {record.status.replace('_', ' ')} cannot be submitted.")
    before = _state(record)
    _set_status(record, STATUS_PENDING)
    record.updated_by_id = access.user.id
    db.flush()
    _record_event(db, record, actor=access.user, action="submitted", before=before)
    return record


@dataclass
class Assessment:
    decision: str
    level: int | None = None
    method: str = METHOD_MANAGER
    feedback: str | None = None
    confidential_note: str | None = None


def assess(db: Session, access: SkillAccess, *, subject_id: UUID, skill_id: UUID, data: Assessment) -> UserSkill:
    """Reviewer decision. Creates a manager-entered record when the employee has none."""
    actor = access.user
    if subject_id == actor.id:
        raise SkillPermissionError("You cannot assess your own skills.")
    _active_subject(db, subject_id)
    if not access.can_review(db, subject_id):
        raise SkillPermissionError("You are not an authorised reviewer for this employee.")
    if data.decision not in DECISIONS:
        raise SkillValidationError(f"Unknown decision '{data.decision}'.")
    if data.method not in VERIFICATION_METHODS:
        raise SkillValidationError(f"Unknown verification method '{data.method}'.")
    feedback = (data.feedback or "").strip() or None
    confidential = (data.confidential_note or "").strip() or None
    record = find_record(db, subject_id, skill_id)
    if record is None:
        if data.decision != DECISION_VERIFY:
            raise SkillValidationError("There is no record to reject or reassess.")
        skill = _active_skill(db, skill_id)
        record = UserSkill(
            user_id=subject_id,
            skill_id=skill.id,
            origin=ORIGIN_MANAGER,
            status=STATUS_PENDING,
            proficiency=SkillLevel.intermediate,
        )
        db.add(record)
        db.flush()
        before: dict = {}
    else:
        if record.status == STATUS_ARCHIVED:
            raise SkillValidationError("The record is archived. The employee must declare it again first.")
        before = _state(record)
    now = _now()
    if data.decision == DECISION_VERIFY:
        level = validate_level(data.level)
        record.verified_level = level
        record.verified_at = now
        record.verified_by_id = actor.id
        record.verification_method = data.method
        record.proficiency = _LEGACY_BY_LEVEL[level]
        _set_status(record, STATUS_VERIFIED)
        if record.declared_level is not None and record.declared_level != level and record.origin != ORIGIN_MANAGER:
            detail = f"Claimed level {record.declared_level}; verified at level {level}."
        else:
            detail = None
        # The claim has now been reviewed.
        if record.declared_level is not None:
            record.declared_level = level
        action = "verified"
    elif data.decision == DECISION_REJECT:
        if record.verified_level is not None and record.status in (STATUS_VERIFIED, STATUS_NEEDS_REASSESSMENT):
            detail = f"Claim of level {record.declared_level} not confirmed; verified level {record.verified_level} stands."
            record.declared_level = record.verified_level
        else:
            detail = "Claim not confirmed."
            _set_status(record, STATUS_REJECTED)
        action = "rejected"
    else:
        if record.status != STATUS_VERIFIED:
            raise SkillValidationError("Only a verified record can be sent for reassessment.")
        _set_status(record, STATUS_NEEDS_REASSESSMENT)
        detail = None
        action = "reassessment_requested"
    record.last_assessed_at = now
    record.last_assessed_by_id = actor.id
    record.updated_by_id = actor.id
    if feedback is not None:
        record.assessment_feedback = feedback
    if confidential is not None:
        record.confidential_notes = confidential
    db.flush()
    _record_event(
        db,
        record,
        actor=actor,
        action=action,
        before=before,
        method=data.method if data.decision == DECISION_VERIFY else None,
        feedback=feedback,
        confidential_note=confidential,
        detail=detail,
    )
    return record


def archive_record(db: Session, access: SkillAccess, record: UserSkill, *, reason: str | None) -> UserSkill:
    is_owner = record.user_id == access.user.id
    if record.status == STATUS_ARCHIVED:
        return record
    if record.verified_level is not None:
        if not access.can_review(db, record.user_id):
            raise SkillPermissionError("A verified record can only be archived by an authorised reviewer.")
    elif not (is_owner or access.can_review(db, record.user_id)):
        raise SkillPermissionError("You cannot archive this record.")
    before = _state(record)
    _set_status(record, STATUS_ARCHIVED)
    record.updated_by_id = access.user.id
    db.flush()
    _record_event(db, record, actor=access.user, action="archived", before=before, detail=(reason or "").strip() or None)
    return record


def legacy_replace(db: Session, *, user_id: UUID, items: list[tuple[UUID, SkillLevel]], actor: User) -> list[UserSkill]:
    """Non-destructive implementation of ``PUT /settings/users/{id}/skills``.

    Listed skills are created (pending verification) or have their legacy
    proficiency updated; unlisted records are archived, never deleted, so history
    and verification survive.
    """
    _active_subject(db, user_id)
    wanted = dict(items)
    existing = {row.skill_id: row for row in db.scalars(select(UserSkill).where(UserSkill.user_id == user_id)).all()}
    for skill_id, proficiency in wanted.items():
        record = existing.get(skill_id)
        if record is None:
            if db.get(Skill, skill_id) is None:
                raise SkillNotFoundError("Skill not found.")
            record = UserSkill(
                user_id=user_id,
                skill_id=skill_id,
                origin=ORIGIN_MANAGER,
                status=STATUS_PENDING,
                status_changed_at=_now(),
                proficiency=proficiency,
                updated_by_id=actor.id,
            )
            db.add(record)
            db.flush()
            _record_event(db, record, actor=actor, action="legacy_recorded", before={}, detail=f"Legacy proficiency {proficiency.value}.")
            continue
        before = _state(record)
        changed = record.proficiency != proficiency
        record.proficiency = proficiency
        if record.status == STATUS_ARCHIVED:
            _set_status(record, STATUS_PENDING)
            changed = True
        if changed:
            record.updated_by_id = actor.id
            db.flush()
            _record_event(db, record, actor=actor, action="legacy_updated", before=before, detail=f"Legacy proficiency {proficiency.value}.")
    for skill_id, record in existing.items():
        if skill_id not in wanted and record.status != STATUS_ARCHIVED:
            before = _state(record)
            _set_status(record, STATUS_ARCHIVED)
            record.updated_by_id = actor.id
            db.flush()
            _record_event(db, record, actor=actor, action="archived", before=before, detail="Removed through the legacy settings endpoint.")
    db.flush()
    return [
        row
        for row in db.scalars(select(UserSkill).where(UserSkill.user_id == user_id)).all()
        if row.status != STATUS_ARCHIVED
    ]


def records_for_user(db: Session, user_id: UUID, *, include_archived: bool) -> list[UserSkill]:
    stmt = select(UserSkill).options(selectinload(UserSkill.skill)).where(UserSkill.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(UserSkill.status != STATUS_ARCHIVED)
    return list(db.scalars(stmt).all())


def events_for_record(db: Session, record_id: UUID) -> list[UserSkillEvent]:
    return list(
        db.scalars(
            select(UserSkillEvent).where(UserSkillEvent.user_skill_id == record_id).order_by(UserSkillEvent.occurred_at, UserSkillEvent.id)
        ).all()
    )


ORIGIN_LABELS = {ORIGIN_SELF: "Self-declared", ORIGIN_MANAGER: "Manager-entered", ORIGIN_LEGACY: "Legacy record"}
