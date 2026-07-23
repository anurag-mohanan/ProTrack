from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.foundation import get_or_create_notification_settings
from app.models.enums import EntityType, NotificationType
from app.models.foundation import UserPreferences
from app.models.models import Notification, User

_NOTIFICATION_TYPE_TO_SETTING = {
    NotificationType.project_assigned: "new_assignments_enabled",
    NotificationType.milestone_due_tomorrow: "projects_due_enabled",
    NotificationType.project_due_soon: "projects_due_enabled",
    NotificationType.project_overdue: "overdue_enabled",
    NotificationType.timesheet_submitted: "pending_approvals_enabled",
    NotificationType.pending_approval: "pending_approvals_enabled",
    NotificationType.timesheet_approved: "pending_approvals_enabled",
    NotificationType.timesheet_rejected: "pending_approvals_enabled",
    NotificationType.import_completed: "imports_completed_enabled",
}

_NOTIFICATION_TYPE_TO_TEMPLATE = {
    NotificationType.project_assigned: "project_assigned",
    NotificationType.milestone_due_tomorrow: "milestone_due",
    NotificationType.project_due_soon: "milestone_due",
    NotificationType.project_overdue: "milestone_overdue",
    NotificationType.timesheet_submitted: "timesheet_reminder",
    NotificationType.pending_approval: "timesheet_reminder",
    NotificationType.timesheet_approved: "timesheet_approved",
    NotificationType.timesheet_rejected: "timesheet_rejected",
    NotificationType.import_completed: "historical_import_completed",
    NotificationType.new_hire_onboarding: "new_hire_onboarding",
}


def _notification_allowed(db: Session, notification_type: NotificationType) -> bool:
    settings = get_or_create_notification_settings(db)
    key = _NOTIFICATION_TYPE_TO_SETTING.get(notification_type)
    if key is None:
        return True
    return bool(getattr(settings, key, True))


def _user_wants_email(db: Session, user_id: UUID, notification_type: NotificationType) -> bool:
    settings = get_or_create_notification_settings(db)
    if not settings.email_notifications_enabled:
        return False
    prefs = db.scalar(select(UserPreferences).where(UserPreferences.user_id == user_id))
    if prefs is not None and not prefs.email_notifications_enabled:
        return False
    if prefs is not None:
        if notification_type == NotificationType.project_assigned and not prefs.email_assignment_enabled:
            return False
        reminder_types = {
            NotificationType.milestone_due_tomorrow,
            NotificationType.project_due_soon,
            NotificationType.project_overdue,
            NotificationType.timesheet_submitted,
            NotificationType.pending_approval,
        }
        if notification_type in reminder_types and not prefs.email_reminder_enabled:
            return False
    return True


def _dispatch_notification_email(
    db: Session,
    *,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    email_context: dict | None = None,
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
) -> None:
    if not _user_wants_email(db, user_id, notification_type):
        return
    template_slug = _NOTIFICATION_TYPE_TO_TEMPLATE.get(notification_type)
    if not template_slug:
        return
    user = db.get(User, user_id)
    context = {
        "Designer": f"{user.first_name} {user.last_name}".strip() if user else "",
        "Message": message,
        "Title": title,
        **(email_context or {}),
    }
    project_id = entity_id if entity_type == EntityType.project else None
    if user and user.email:
        from app.services.email.engine import EmailService

        EmailService(db).send_templated_email(
            template_slug=template_slug,
            to_addresses=[user.email],
            context=context,
            project_id=project_id,
            sent_by_user_id=user_id,
            timeline_label=title,
        )


def create_notification(
    db: Session,
    *,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
    email_context: dict | None = None,
    send_email: bool = True,
    commit: bool = True,
) -> Notification | None:
    if not _notification_allowed(db, notification_type):
        return None

    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    else:
        db.flush()

    if send_email:
        _dispatch_notification_email(
            db,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            email_context=email_context,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    return notification


def mark_notification_read(
    db: Session,
    notification: Notification,
) -> Notification:
    notification.is_read = True
    notification.read_at = datetime.now(UTC)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def archive_notification(db: Session, notification: Notification) -> Notification:
    notification.is_archived = True
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, user_id: UUID) -> int:
    notifications = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
            Notification.is_archived.is_(False),
        )
    ).all()
    now = datetime.now(UTC)
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now
        db.add(notification)
    db.commit()
    return len(notifications)


def count_unread_notifications(db: Session, user_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
                Notification.is_archived.is_(False),
            )
        )
        or 0
    )


def notify_users(
    db: Session,
    *,
    user_ids: set[UUID],
    notification_type: NotificationType,
    title: str,
    message: str,
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
    email_context: dict | None = None,
) -> list[Notification]:
    created: list[Notification] = []
    for user_id in user_ids:
        if user_id:
            notification = create_notification(
                db,
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=entity_id,
                email_context=email_context,
            )
            if notification is not None:
                created.append(notification)
    return created
