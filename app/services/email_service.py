"""Backward-compatible email service facade."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.email.engine import EmailService


def render_template_content(content: str, context: dict[str, Any]) -> str:
    from app.services.email.template_renderer import render_template_content as _render

    return _render(content, context)


def render_email_template(template, context: dict[str, Any]):
    from app.services.email.template_renderer import render_email_template as _render

    return _render(template, context)


def send_email_message(
    db: Session,
    *,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> bool:
    service = EmailService(db)
    message = service.queue_email(
        to_addresses=to_addresses,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        send_immediately=True,
    )
    return message is not None and message.status == "sent"


def send_templated_email(
    db: Session,
    *,
    template_slug: str,
    to_addresses: list[str],
    context: dict[str, Any],
    project_id: UUID | None = None,
    sent_by_user_id: UUID | None = None,
    attachment_paths: list[str] | None = None,
    timeline_label: str | None = None,
) -> bool:
    return EmailService(db).send_templated_email(
        template_slug=template_slug,
        to_addresses=to_addresses,
        context=context,
        project_id=project_id,
        sent_by_user_id=sent_by_user_id,
        attachment_paths=attachment_paths,
        timeline_label=timeline_label,
    )


def send_email_to_user(
    db: Session,
    *,
    user_id: UUID,
    template_slug: str,
    context: dict[str, Any],
    extra_addresses: list[str] | None = None,
    project_id: UUID | None = None,
) -> bool:
    return EmailService(db).send_email_to_user(
        user_id=user_id,
        template_slug=template_slug,
        context=context,
        extra_addresses=extra_addresses,
        project_id=project_id,
    )


def send_test_email(db: Session, *, to_address: str) -> None:
    EmailService(db).send_test_email(to_address=to_address)
