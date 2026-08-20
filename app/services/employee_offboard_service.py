"""Confirm last working day and soft-offboard employees while retaining history."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.models import Project, TeamMember, TeamMembershipPeriod, User
from app.services.activity_service import log_activity
from app.services.user_lifecycle_service import mark_user_archived


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _require_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ProTrackValidationError("User not found")
    return user


def _close_all_open_membership_periods(
    db: Session, *, user_id: UUID, effective_to: date
) -> None:
    rows = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id == user_id,
            TeamMembershipPeriod.effective_to.is_(None),
        )
    ).all()
    for row in rows:
        if row.effective_from > effective_to:
            row.effective_to = row.effective_from
        else:
            row.effective_to = effective_to
        db.add(row)


def _clear_live_project_roles(db: Session, *, user_id: UUID) -> int:
    projects = db.scalars(
        select(Project).where(
            Project.is_deleted.is_(False),
            or_(
                Project.design_leader_id == user_id,
                Project.designer_id == user_id,
                Project.surfacer_id == user_id,
            ),
        )
    ).all()
    cleared = 0
    for project in projects:
        if project.design_leader_id == user_id:
            project.design_leader_id = None
            cleared += 1
        if project.designer_id == user_id:
            project.designer_id = None
            cleared += 1
        if project.surfacer_id == user_id:
            project.surfacer_id = None
            cleared += 1
        db.add(project)
    return cleared


def _remove_live_team_memberships(db: Session, *, user: User) -> int:
    members = db.scalars(
        select(TeamMember).where(TeamMember.user_id == user.id)
    ).all()
    count = len(members)
    for member in members:
        db.delete(member)
    user.team_id = None
    db.add(user)
    return count


def apply_live_offboard(
    db: Session,
    *,
    user: User,
    actor: User | None = None,
) -> bool:
    """Remove live team membership, clear project roles, archive. Idempotent."""
    if user.offboard_applied_at is not None:
        return False

    removed = _remove_live_team_memberships(db, user=user)
    cleared = _clear_live_project_roles(db, user_id=user.id)
    mark_user_archived(db, user)
    user.offboard_applied_at = _utcnow()
    db.add(user)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.user,
        entity_id=user.id,
        action=ActivityAction.employee_offboard_applied,
        new_value=(
            f"leaving_date:{user.leaving_date};"
            f"teams_removed:{removed};roles_cleared:{cleared}"
        ),
        commit=False,
    )
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.user,
        entity_id=user.id,
        action=ActivityAction.user_archived,
        new_value=user.email,
        commit=False,
    )
    return True


def confirm_and_set_leaving_date(
    db: Session,
    *,
    user_id: UUID,
    leaving_date: date | None,
    actor: User | None,
    confirm_left_organisation: bool = False,
    commit: bool = True,
) -> User:
    """
    Set last working day. When the date is newly set or changed to a non-null
    value, require confirm_left_organisation and run soft-offboard side effects.
    """
    user = _require_user(db, user_id)
    previous = user.leaving_date

    if leaving_date is None:
        user.leaving_date = None
        db.add(user)
        if commit:
            db.commit()
            db.refresh(user)
        else:
            db.flush()
        return user

    changing = previous != leaving_date
    if changing and not confirm_left_organisation:
        raise ProTrackValidationError(
            "Confirm that the employee has left / is leaving the organisation "
            "before setting last working day."
        )

    user.leaving_date = leaving_date
    db.add(user)

    if changing:
        _close_all_open_membership_periods(
            db, user_id=user.id, effective_to=leaving_date
        )
        # Queue IT reclaim work (assets / accounts / IPs) as an open Help Desk ticket.
        # Non-destructive: IT completes actions via IT Operations workflows.
        from app.services.it_deprovision_service import ensure_offboard_tasks

        ensure_offboard_tasks(db, user=user, actor=actor)
        today = date.today()
        if leaving_date <= today:
            apply_live_offboard(db, user=user, actor=actor)
        else:
            log_activity(
                db,
                user=actor,
                entity_type=EntityType.user,
                entity_id=user.id,
                action=ActivityAction.employee_offboard_scheduled,
                new_value=f"leaving_date:{leaving_date.isoformat()}",
                commit=False,
            )
    else:
        # Same date re-saved — still apply if due and not yet applied
        if leaving_date <= date.today() and user.offboard_applied_at is None:
            apply_live_offboard(db, user=user, actor=actor)

    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def apply_due_offboards(db: Session, *, as_of: date | None = None) -> int:
    """Apply deferred live offboards for users whose leaving_date has arrived."""
    day = as_of or date.today()
    pending = db.scalars(
        select(User).where(
            User.leaving_date.is_not(None),
            User.leaving_date <= day,
            User.offboard_applied_at.is_(None),
            User.is_deleted.is_(False),
        )
    ).all()
    applied = 0
    for user in pending:
        # Ensure periods closed to leaving_date (idempotent close of any still-open)
        if user.leaving_date is not None:
            _close_all_open_membership_periods(
                db, user_id=user.id, effective_to=user.leaving_date
            )
        if apply_live_offboard(db, user=user, actor=None):
            applied += 1
    return applied
