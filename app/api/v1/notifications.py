from uuid import UUID

from sqlalchemy import select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, HTTPException, Query, Session, get_db, status
from app.models.models import Activity, Notification, User
from app.schemas.timesheet import ActivityRead, NotificationRead, NotificationSummary
from app.services.notification_service import (
    archive_notification,
    count_unread_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = False,
    include_archived: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if not include_archived:
        query = query.where(Notification.is_archived.is_(False))
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    return db.scalars(query).all()


@router.get("/summary", response_model=NotificationSummary)
def notification_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return NotificationSummary(
        unread_count=count_unread_notifications(db, current_user.id)
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
def read_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return mark_notification_read(db, notification)


@router.post("/read-all", response_model=NotificationSummary)
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mark_all_notifications_read(db, current_user.id)
    return NotificationSummary(
        unread_count=count_unread_notifications(db, current_user.id)
    )


@router.post("/{notification_id}/archive", response_model=NotificationRead)
def archive_user_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return archive_notification(db, notification)
