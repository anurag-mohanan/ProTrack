from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EntityType, NotificationType
from app.models.models import Notification, User


def create_notification(
    db: Session,
    *,
    user_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
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


def mark_all_notifications_read(db: Session, user_id: UUID) -> int:
    notifications = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
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
) -> list[Notification]:
    created: list[Notification] = []
    for user_id in user_ids:
        if user_id:
            created.append(
                create_notification(
                    db,
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )
    return created
