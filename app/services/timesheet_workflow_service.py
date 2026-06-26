from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.core.permissions import (
    can_approve_timesheet,
    can_edit_timesheet,
    can_read_timesheet,
    can_reject_timesheet,
    can_return_timesheet_to_draft,
    can_submit_timesheet,
    get_role_name,
    FULL_ACCESS_ROLES,
)
from app.models.enums import ActivityAction, EntityType, NotificationType, TimesheetStatus
from app.models.models import Project, Role, Timesheet, TimesheetEntry, User
from app.services.activity_service import log_activity
from app.services.notification_service import create_notification, notify_users
from sqlalchemy import select


class TimesheetWorkflowError(ProTrackValidationError):
    pass


def _require_permission(check: bool, message: str) -> None:
    if not check:
        raise TimesheetWorkflowError(message)


def _approver_ids_for_timesheet(db: Session, timesheet: Timesheet) -> set:
    user_ids = set()
    project_ids = db.scalars(
        select(TimesheetEntry.project_id).where(
            TimesheetEntry.timesheet_id == timesheet.id
        )
    ).all()
    if not project_ids:
        return user_ids
    projects = db.scalars(select(Project).where(Project.id.in_(project_ids))).all()
    for project in projects:
        user_ids.add(project.design_leader_id)
    em_users = db.scalars(
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(Role.name.in_(["Engineering Manager", "Admin"]))
    ).all()
    for user in em_users:
        user_ids.add(user.id)
    return user_ids


def submit_timesheet(db: Session, *, timesheet: Timesheet, actor: User) -> Timesheet:
    _require_permission(
        can_submit_timesheet(db, actor, timesheet),
        "You cannot submit this timesheet",
    )
    old_status = timesheet.status
    timesheet.status = TimesheetStatus.submitted
    timesheet.submitted_at = datetime.now(UTC)
    timesheet.approved_by = None
    timesheet.approved_at = None
    timesheet.approval_comments = None
    db.add(timesheet)
    db.commit()
    db.refresh(timesheet)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.timesheet,
        entity_id=timesheet.id,
        action=ActivityAction.timesheet_submitted,
        old_value=old_status,
        new_value=timesheet.status,
    )
    owner = db.get(User, timesheet.user_id)
    owner_name = f"{owner.first_name} {owner.last_name}" if owner else "A user"
    notify_users(
        db,
        user_ids=_approver_ids_for_timesheet(db, timesheet) - {actor.id},
        notification_type=NotificationType.timesheet_submitted,
        title="Timesheet submitted",
        message=f"{owner_name} submitted a timesheet for week {timesheet.week_start}.",
        entity_type=EntityType.timesheet,
        entity_id=timesheet.id,
    )
    return timesheet


def approve_timesheet(
    db: Session,
    *,
    timesheet: Timesheet,
    actor: User,
    comments: str | None = None,
) -> Timesheet:
    _require_permission(
        can_approve_timesheet(db, actor, timesheet),
        "You cannot approve this timesheet",
    )
    old_status = timesheet.status
    timesheet.status = TimesheetStatus.approved
    timesheet.approved_by = actor.id
    timesheet.approved_at = datetime.now(UTC)
    timesheet.approval_comments = comments
    db.add(timesheet)
    db.commit()
    db.refresh(timesheet)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.timesheet,
        entity_id=timesheet.id,
        action=ActivityAction.timesheet_approved,
        old_value=old_status,
        new_value=timesheet.status,
    )
    create_notification(
        db,
        user_id=timesheet.user_id,
        notification_type=NotificationType.timesheet_approved,
        title="Timesheet approved",
        message=comments or "Your timesheet has been approved.",
        entity_type=EntityType.timesheet,
        entity_id=timesheet.id,
    )
    return timesheet


def reject_timesheet(
    db: Session,
    *,
    timesheet: Timesheet,
    actor: User,
    comments: str,
) -> Timesheet:
    if not comments.strip():
        raise TimesheetWorkflowError("Approval comments are required when rejecting")
    _require_permission(
        can_reject_timesheet(db, actor, timesheet),
        "You cannot reject this timesheet",
    )
    old_status = timesheet.status
    timesheet.status = TimesheetStatus.rejected
    timesheet.approved_by = actor.id
    timesheet.approved_at = datetime.now(UTC)
    timesheet.approval_comments = comments.strip()
    db.add(timesheet)
    db.commit()
    db.refresh(timesheet)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.timesheet,
        entity_id=timesheet.id,
        action=ActivityAction.timesheet_rejected,
        old_value=old_status,
        new_value=timesheet.status,
    )
    create_notification(
        db,
        user_id=timesheet.user_id,
        notification_type=NotificationType.timesheet_rejected,
        title="Timesheet rejected",
        message=comments.strip(),
        entity_type=EntityType.timesheet,
        entity_id=timesheet.id,
    )
    return timesheet


def return_timesheet_to_draft(
    db: Session,
    *,
    timesheet: Timesheet,
    actor: User,
) -> Timesheet:
    _require_permission(
        can_return_timesheet_to_draft(db, actor, timesheet),
        "You cannot return this timesheet to draft",
    )
    old_status = timesheet.status
    timesheet.status = TimesheetStatus.draft
    timesheet.submitted_at = None
    timesheet.approved_by = None
    timesheet.approved_at = None
    timesheet.approval_comments = None
    db.add(timesheet)
    db.commit()
    db.refresh(timesheet)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.timesheet,
        entity_id=timesheet.id,
        action=ActivityAction.timesheet_rejected,
        old_value=old_status,
        new_value=timesheet.status,
    )
    return timesheet


def filter_visible_timesheets(
    db: Session,
    actor: User,
    timesheets: list[Timesheet],
) -> list[Timesheet]:
    role_name = get_role_name(db, actor)
    if role_name in FULL_ACCESS_ROLES:
        return timesheets
    if role_name == "Design Leader":
        return [ts for ts in timesheets if can_read_timesheet(db, actor, ts)]
    return [ts for ts in timesheets if ts.user_id == actor.id]
