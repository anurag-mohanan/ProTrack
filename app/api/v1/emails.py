import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db
from app.crud.foundation import get_email_template_by_slug
from app.models.foundation import EmailMessage
from app.models.models import User
from app.schemas.communication import (
    CustomerEmailRequest,
    EmailMessageRead,
    EmailPreviewRequest,
    EmailPreviewResponse,
    ManualEmailRequestExtended,
    OneClickEmailRequest,
)
from app.schemas.settings import ManualEmailRequest
from app.services.communication_service import send_customer_template_email, send_one_click_email
from app.services.email.engine import EmailService, list_email_messages
from app.services.email.template_renderer import EMAIL_TEMPLATE_VARIABLES, preview_template
from app.services.email_digest_service import (
    queue_daily_engineering_summary,
    queue_monthly_engineering_report,
    queue_weekly_engineering_summary,
)

router = APIRouter(
    prefix="/emails",
    tags=["emails"],
    dependencies=[Depends(get_current_user)],
)

_manager_roles = [Depends(require_roles("Admin", "Engineering Manager", "Design Leader", "Project Manager"))]


def _serialize_email_message(message: EmailMessage) -> EmailMessageRead:
    attachments = json.loads(message.attachment_metadata or "[]")
    return EmailMessageRead(
        id=message.id,
        project_id=message.project_id,
        sent_by_user_id=message.sent_by_user_id,
        template_slug=message.template_slug,
        to_addresses=json.loads(message.to_addresses or "[]"),
        subject=message.subject,
        body_html=message.body_html,
        body_text=message.body_text,
        status=message.status,
        retry_count=message.retry_count,
        max_retries=message.max_retries,
        last_error=message.last_error,
        smtp_response=message.smtp_response,
        attachments=attachments,
        recipients_display=message.recipients_display,
        timeline_label=message.timeline_label,
        sent_at=message.sent_at,
        delivered_at=message.delivered_at,
        created_at=message.created_at,
    )


@router.get("/variables")
def list_template_variables():
    return {"variables": EMAIL_TEMPLATE_VARIABLES}


@router.post("/preview", response_model=EmailPreviewResponse, dependencies=_manager_roles)
def preview_email_template(payload: EmailPreviewRequest):
    rendered = preview_template(
        subject=payload.subject,
        body_html=payload.body_html,
        body_text=payload.body_text,
        context=payload.context,
    )
    return EmailPreviewResponse(**rendered)


@router.get("/queue", response_model=list[EmailMessageRead], dependencies=_manager_roles)
def get_email_queue(
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = Query(default=100, le=500),
):
    return [
        _serialize_email_message(message)
        for message in list_email_messages(db, status=status_filter, search=search, limit=limit)
    ]


@router.get("/history", response_model=list[EmailMessageRead], dependencies=_manager_roles)
def get_email_history(
    db: Session = Depends(get_db),
    project_id: UUID | None = None,
    search: str | None = None,
    limit: int = Query(default=100, le=500),
):
    return [
        _serialize_email_message(message)
        for message in list_email_messages(db, project_id=project_id, search=search, limit=limit)
    ]


@router.post("/queue/process", dependencies=[Depends(require_roles("Admin", "Engineering Manager"))])
def process_email_queue(db: Session = Depends(get_db), limit: int = Query(default=50, le=200)):
    processed = EmailService(db).process_queue(limit=limit)
    return {"processed": processed}


@router.post("/send", dependencies=_manager_roles)
def send_manual_email(payload: ManualEmailRequest, db: Session = Depends(get_db)):
    template = get_email_template_by_slug(db, payload.template_slug)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email template not found")

    addresses = [address.strip() for address in payload.to_addresses if address.strip()]
    for user_id in payload.user_ids:
        user = db.get(User, user_id)
        if user and user.email:
            addresses.append(user.email)

    if not addresses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one recipient email address is required.",
        )

    sent = EmailService(db).send_templated_email(
        template_slug=payload.template_slug,
        to_addresses=addresses,
        context=payload.context,
    )
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email could not be sent. Verify SMTP settings are enabled and configured.",
        )
    return {"sent": True, "recipient_count": len(addresses)}


@router.post("/send-extended", dependencies=_manager_roles)
def send_manual_email_extended(
    payload: ManualEmailRequestExtended,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = get_email_template_by_slug(db, payload.template_slug)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email template not found")

    addresses = [address.strip() for address in payload.to_addresses if address.strip()]
    for user_id in payload.user_ids:
        user = db.get(User, user_id)
        if user and user.email:
            addresses.append(user.email)
    if not addresses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one recipient email address is required.",
        )

    sent = EmailService(db).send_templated_email(
        template_slug=payload.template_slug,
        to_addresses=addresses,
        context=payload.context,
        project_id=payload.project_id,
        sent_by_user_id=current_user.id,
        attachment_paths=payload.attachment_paths,
        timeline_label=payload.timeline_label,
    )
    if not sent:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email could not be sent.")
    return {"sent": True, "recipient_count": len(addresses)}


@router.post("/one-click", dependencies=_manager_roles)
def send_one_click(
    payload: OneClickEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        sent = send_one_click_email(
            db,
            project_id=payload.project_id,
            action=payload.action,
            sent_by_user_id=current_user.id,
            message=payload.message,
            extra_addresses=payload.extra_addresses,
            attach_released_files=payload.attach_released_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not sent:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email could not be sent.")
    return {"sent": True}


@router.post("/customer", dependencies=_manager_roles)
def send_customer_email(
    payload: CustomerEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        sent = send_customer_template_email(
            db,
            project_id=payload.project_id,
            template_slug=payload.template_slug,
            sent_by_user_id=current_user.id,
            message=payload.message,
            to_addresses=payload.to_addresses,
            attachment_paths=payload.attachment_paths,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not sent:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email could not be sent.")
    return {"sent": True}


@router.post("/digests/daily", dependencies=[Depends(require_roles("Admin", "Engineering Manager"))])
def trigger_daily_digest(db: Session = Depends(get_db)):
    return {"queued": queue_daily_engineering_summary(db)}


@router.post("/digests/weekly", dependencies=[Depends(require_roles("Admin", "Engineering Manager"))])
def trigger_weekly_digest(db: Session = Depends(get_db)):
    return {"queued": queue_weekly_engineering_summary(db)}


@router.post("/digests/monthly", dependencies=[Depends(require_roles("Admin", "Engineering Manager"))])
def trigger_monthly_digest(db: Session = Depends(get_db)):
    return {"queued": queue_monthly_engineering_report(db)}
