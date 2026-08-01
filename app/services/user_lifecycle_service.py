"""User archive, restore, soft delete, and permanent delete."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.models import Activity, Project, Timesheet, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class UserDeleteDependencies:
    timesheets: int = 0
    assigned_projects: int = 0
    activities: int = 0

    @property
    def has_blockers(self) -> bool:
        return self.timesheets > 0 or self.assigned_projects > 0 or self.activities > 0

    def blocker_messages(self) -> list[str]:
        messages: list[str] = []
        if self.timesheets:
            messages.append(f"{self.timesheets} timesheet{'s' if self.timesheets != 1 else ''}")
        if self.assigned_projects:
            messages.append(
                f"{self.assigned_projects} assigned project"
                f"{'s' if self.assigned_projects != 1 else ''}"
            )
        if self.activities:
            messages.append(
                f"{self.activities} activit{'y' if self.activities == 1 else 'ies'}"
            )
        return messages


def get_user_delete_dependencies(db: Session, user_id: UUID) -> UserDeleteDependencies:
    timesheets = int(
        db.scalar(
            select(func.count()).select_from(Timesheet).where(Timesheet.user_id == user_id)
        )
        or 0
    )
    assigned_projects = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                or_(
                    Project.design_leader_id == user_id,
                    Project.designer_id == user_id,
                    Project.surfacer_id == user_id,
                ),
            )
        )
        or 0
    )
    activities = int(
        db.scalar(
            select(func.count())
            .select_from(Activity)
            .where(Activity.user_id == user_id)
        )
        or 0
    )
    return UserDeleteDependencies(
        timesheets=timesheets,
        assigned_projects=assigned_projects,
        activities=activities,
    )


def _require_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ProTrackValidationError("User not found")
    return user


def mark_user_archived(db: Session, user: User) -> User:
    """Archive in-session without committing (for composed workflows)."""
    if user.is_deleted:
        raise ProTrackValidationError("Deleted users cannot be archived")
    if user.is_archived:
        return user
    user.is_archived = True
    user.archived_at = _utcnow()
    user.is_active = False
    db.add(user)
    return user


def archive_user(db: Session, user_id: UUID) -> User:
    user = _require_user(db, user_id)
    if user.is_archived:
        raise ProTrackValidationError("User is already archived")
    mark_user_archived(db, user)
    db.commit()
    db.refresh(user)
    return user


def restore_user_from_archive(db: Session, user_id: UUID) -> User:
    user = _require_user(db, user_id)
    if user.is_deleted:
        raise ProTrackValidationError("Deleted users must be restored from Deleted Users")
    if not user.is_archived:
        raise ProTrackValidationError("User is not archived")
    user.is_archived = False
    user.archived_at = None
    user.is_active = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def soft_delete_user(db: Session, user_id: UUID, actor: User) -> User:
    user = _require_user(db, user_id)
    if user.id == actor.id:
        raise ProTrackValidationError("You cannot delete your own account")
    if user.is_deleted:
        raise ProTrackValidationError("User is already deleted")
    user.is_deleted = True
    user.deleted_at = _utcnow()
    user.deleted_by_id = actor.id
    user.is_active = False
    user.is_archived = False
    user.archived_at = None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def restore_user_from_deleted(db: Session, user_id: UUID) -> User:
    user = _require_user(db, user_id)
    if not user.is_deleted:
        raise ProTrackValidationError("User is not deleted")
    user.is_deleted = False
    user.deleted_at = None
    user.deleted_by_id = None
    user.is_active = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def permanent_delete_user(db: Session, user_id: UUID) -> None:
    user = _require_user(db, user_id)
    if not user.is_deleted:
        raise ProTrackValidationError("Only soft-deleted users can be permanently deleted")
    deps = get_user_delete_dependencies(db, user_id)
    if deps.has_blockers:
        detail = ", ".join(deps.blocker_messages())
        raise ProTrackValidationError(f"Cannot permanently delete user: {detail} still exist")
    db.delete(user)
    db.commit()
