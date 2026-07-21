"""Email queue, delivery, and logging engine."""

from __future__ import annotations

import json
import logging
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import ATTACHMENT_ROOTS
from app.core.path_safety import is_within
from app.crud.foundation import get_email_template_by_slug, get_or_create_email_settings
from app.models.enums import ActivityAction, EmailMessageStatus, EntityType
from app.models.foundation import EmailMessage, EmailSettings, EmailTemplate
from app.models.models import User
from app.services.activity_service import log_activity
from app.services.email.providers.smtp_provider import SMTPProvider
from app.services.email.providers.zoho_provider import ZohoProvider
from app.services.email.template_renderer import render_email_template, render_template_content
from app.services.email.types import EmailAttachment, EmailDeliveryResult, OutboundEmail

logger = logging.getLogger(__name__)

_ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".step",
    ".stp",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".dwg",
    ".dxf",
}


def get_email_provider(settings: EmailSettings):
    if settings.provider_type == "zoho":
        return ZohoProvider()
    return SMTPProvider()


class EmailService:
    def __init__(self, db: Session):
        self.db = db

    def test_connection(self) -> EmailDeliveryResult:
        settings = get_or_create_email_settings(self.db)
        provider = get_email_provider(settings)
        result = provider.test_connection(settings)
        settings.connection_status = "connected" if result.success else "failed"
        settings.connection_checked_at = datetime.now(UTC)
        settings.connection_message = result.smtp_response or result.error
        self.db.add(settings)
        self.db.commit()
        return result

    def queue_email(
        self,
        *,
        to_addresses: list[str],
        subject: str,
        html_body: str,
        text_body: str | None = None,
        template_slug: str | None = None,
        project_id: UUID | None = None,
        sent_by_user_id: UUID | None = None,
        cc_addresses: list[str] | None = None,
        attachment_paths: list[str] | None = None,
        timeline_label: str | None = None,
        send_immediately: bool = True,
    ) -> EmailMessage | None:
        recipients = [address.strip() for address in to_addresses if address and address.strip()]
        if not recipients:
            return None

        settings = get_or_create_email_settings(self.db)
        if not settings.enabled:
            logger.info("Email delivery skipped — email is disabled.")
            return None

        attachments = self._build_attachment_metadata(attachment_paths or [])
        message = EmailMessage(
            project_id=project_id,
            sent_by_user_id=sent_by_user_id,
            template_slug=template_slug,
            to_addresses=json.dumps(recipients),
            cc_addresses=json.dumps(cc_addresses or []),
            subject=subject,
            body_html=html_body,
            body_text=text_body,
            status=EmailMessageStatus.queued.value,
            attachment_metadata=json.dumps(attachments) if attachments else None,
            recipients_display=", ".join(recipients),
            timeline_label=timeline_label,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        if send_immediately:
            self._deliver_message(message, attachment_paths or [])
        return message

    def send_templated_email(
        self,
        *,
        template_slug: str,
        to_addresses: list[str],
        context: dict[str, Any],
        project_id: UUID | None = None,
        sent_by_user_id: UUID | None = None,
        attachment_paths: list[str] | None = None,
        timeline_label: str | None = None,
        cc_addresses: list[str] | None = None,
    ) -> bool:
        template = get_email_template_by_slug(self.db, template_slug)
        if template is None or not template.is_enabled:
            logger.warning("Email template %s is missing or disabled.", template_slug)
            return False
        subject, html, text = render_email_template(template, context)
        message = self.queue_email(
            to_addresses=to_addresses,
            subject=subject,
            html_body=html,
            text_body=text,
            template_slug=template_slug,
            project_id=project_id,
            sent_by_user_id=sent_by_user_id,
            attachment_paths=attachment_paths,
            timeline_label=timeline_label or template.name,
            cc_addresses=cc_addresses,
            send_immediately=True,
        )
        return message is not None and message.status == EmailMessageStatus.sent.value

    def send_email_to_user(
        self,
        *,
        user_id: UUID,
        template_slug: str,
        context: dict[str, Any],
        extra_addresses: list[str] | None = None,
        project_id: UUID | None = None,
        timeline_label: str | None = None,
    ) -> bool:
        user = self.db.get(User, user_id)
        addresses = list(extra_addresses or [])
        if user and user.email:
            addresses.append(user.email)
        return self.send_templated_email(
            template_slug=template_slug,
            to_addresses=addresses,
            context=context,
            project_id=project_id,
            sent_by_user_id=user_id,
            timeline_label=timeline_label,
        )

    def send_test_email(self, *, to_address: str) -> None:
        settings = get_or_create_email_settings(self.db)
        if not settings.smtp_host or not settings.sender_email:
            raise ValueError("SMTP host and sender email are required before sending a test email.")

        html = (
            "<p>This is a test email from <strong>ProTrack</strong>.</p>"
            "<p>Your SMTP configuration is working correctly.</p>"
        )
        message = self.queue_email(
            to_addresses=[to_address],
            subject="ProTrack SMTP test",
            html_body=html,
            text_body="This is a test email from ProTrack. Your SMTP configuration is working correctly.",
            timeline_label="SMTP test",
            send_immediately=True,
        )
        if message is None or message.status != EmailMessageStatus.sent.value:
            raise RuntimeError(
                message.last_error if message and message.last_error else "Test email could not be sent."
            )

    def process_queue(self, *, limit: int = 50) -> int:
        rows = self.db.scalars(
            select(EmailMessage)
            .where(
                EmailMessage.status.in_(
                    [EmailMessageStatus.queued.value, EmailMessageStatus.failed.value]
                ),
                EmailMessage.retry_count < EmailMessage.max_retries,
            )
            .order_by(EmailMessage.created_at)
            .limit(limit)
        ).all()
        processed = 0
        for row in rows:
            attachment_paths = [
                item["path"]
                for item in json.loads(row.attachment_metadata or "[]")
                if item.get("path")
            ]
            if self._deliver_message(row, attachment_paths):
                processed += 1
        return processed

    def _deliver_message(self, message: EmailMessage, attachment_paths: list[str]) -> bool:
        settings = get_or_create_email_settings(self.db)
        if not settings.smtp_host or not settings.sender_email:
            message.status = EmailMessageStatus.failed.value
            message.last_error = "SMTP is not fully configured."
            self.db.add(message)
            self.db.commit()
            return False

        message.status = EmailMessageStatus.sending.value
        self.db.add(message)
        self.db.commit()

        outbound = OutboundEmail(
            to_addresses=json.loads(message.to_addresses),
            cc_addresses=json.loads(message.cc_addresses or "[]"),
            subject=message.subject,
            html_body=message.body_html,
            text_body=message.body_text,
            attachments=self._load_attachments(attachment_paths),
        )
        provider = get_email_provider(settings)
        result = provider.send(settings, outbound)
        message.retry_count += 1
        message.smtp_response = result.smtp_response
        message.last_error = result.error
        if result.success:
            now = datetime.now(UTC)
            message.status = EmailMessageStatus.sent.value
            message.sent_at = now
            message.delivered_at = now
            self._log_project_timeline(message)
        elif message.retry_count >= message.max_retries:
            message.status = EmailMessageStatus.failed.value
        else:
            message.status = EmailMessageStatus.queued.value
        self.db.add(message)
        self.db.commit()
        return result.success

    def _log_project_timeline(self, message: EmailMessage) -> None:
        if message.project_id is None:
            return
        sender = self.db.get(User, message.sent_by_user_id) if message.sent_by_user_id else None
        log_activity(
            self.db,
            user=sender,
            entity_type=EntityType.project,
            entity_id=message.project_id,
            action=ActivityAction.email_sent,
            new_value={
                "email_id": str(message.id),
                "subject": message.subject,
                "recipients": message.recipients_display,
                "template_slug": message.template_slug,
                "timeline_label": message.timeline_label,
                "status": message.status,
            },
        )

    def _safe_attachment_path(self, raw_path: str) -> Path | None:
        """Return a validated attachment path, or ``None`` if it is rejected.

        Rejects files outside the configured attachment sandbox roots and any
        extension not on the allowlist. This prevents a caller from exfiltrating
        arbitrary server files via ``attachment_paths``.
        """
        path = Path(raw_path)
        if not path.is_file():
            return None
        if path.suffix.lower() not in _ALLOWED_ATTACHMENT_EXTENSIONS:
            return None
        if not is_within(path, ATTACHMENT_ROOTS):
            logger.warning("Rejected out-of-sandbox email attachment: %s", raw_path)
            return None
        return path

    def _build_attachment_metadata(self, attachment_paths: list[str]) -> list[dict[str, str]]:
        metadata: list[dict[str, str]] = []
        for raw_path in attachment_paths:
            path = self._safe_attachment_path(raw_path)
            if path is None:
                continue
            metadata.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                }
            )
        return metadata

    def _load_attachments(self, attachment_paths: list[str]) -> list[EmailAttachment]:
        attachments: list[EmailAttachment] = []
        for raw_path in attachment_paths:
            path = self._safe_attachment_path(raw_path)
            if path is None:
                continue
            attachments.append(
                EmailAttachment(
                    filename=path.name,
                    path=path,
                    mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                )
            )
        return attachments


def list_email_messages(
    db: Session,
    *,
    project_id: UUID | None = None,
    search: str | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 25,
) -> list[EmailMessage]:
    query = select(EmailMessage).order_by(EmailMessage.created_at.desc())
    if project_id is not None:
        query = query.where(EmailMessage.project_id == project_id)
    if status:
        query = query.where(EmailMessage.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                EmailMessage.subject.ilike(pattern),
                EmailMessage.recipients_display.ilike(pattern),
                EmailMessage.template_slug.ilike(pattern),
            )
        )
    return list(db.scalars(query.offset(skip).limit(limit)).all())


def count_email_messages(
    db: Session,
    *,
    project_id: UUID | None = None,
    search: str | None = None,
    status: str | None = None,
) -> int:
    from sqlalchemy import func

    query = select(EmailMessage)
    if project_id is not None:
        query = query.where(EmailMessage.project_id == project_id)
    if status:
        query = query.where(EmailMessage.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                EmailMessage.subject.ilike(pattern),
                EmailMessage.recipients_display.ilike(pattern),
                EmailMessage.template_slug.ilike(pattern),
            )
        )
    return int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
