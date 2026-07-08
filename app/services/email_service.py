"""SMTP email delivery and template rendering."""

from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.secret_encryption import decrypt_secret
from app.crud.foundation import get_or_create_email_settings, get_email_template_by_slug
from app.models.foundation import EmailSettings, EmailTemplate
from app.models.models import User

logger = logging.getLogger(__name__)

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def render_template_content(content: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key, context.get(key.lower(), ""))
        return "" if value is None else str(value)

    return _PLACEHOLDER_PATTERN.sub(replace, content)


def render_email_template(
    template: EmailTemplate,
    context: dict[str, Any],
) -> tuple[str, str, str | None]:
    subject = render_template_content(template.subject, context)
    html = render_template_content(template.body_html, context)
    text = (
        render_template_content(template.body_text, context)
        if template.body_text
        else None
    )
    return subject, html, text


def _smtp_connection(settings: EmailSettings):
    password = decrypt_secret(settings.smtp_password_encrypted or "")
    if settings.use_ssl:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
        if settings.use_tls:
            server.starttls()
    if settings.smtp_username:
        server.login(settings.smtp_username, password)
    return server


def send_email_message(
    db: Session,
    *,
    to_addresses: list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> bool:
    recipients = [address.strip() for address in to_addresses if address and address.strip()]
    if not recipients:
        return False

    settings = get_or_create_email_settings(db)
    if not settings.enabled or not settings.smtp_host or not settings.sender_email:
        logger.info("Email delivery skipped — SMTP not configured.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        f"{settings.sender_name} <{settings.sender_email}>"
        if settings.sender_name
        else settings.sender_email
    )
    message["To"] = ", ".join(recipients)
    message.set_content(text_body or _html_to_text(html_body))
    message.add_alternative(html_body, subtype="html")

    try:
        with _smtp_connection(settings) as server:
            server.send_message(message)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", recipients)
        return False


def send_templated_email(
    db: Session,
    *,
    template_slug: str,
    to_addresses: list[str],
    context: dict[str, Any],
) -> bool:
    template = get_email_template_by_slug(db, template_slug)
    if template is None or not template.is_enabled:
        logger.warning("Email template %s is missing or disabled.", template_slug)
        return False
    subject, html, text = render_email_template(template, context)
    return send_email_message(
        db,
        to_addresses=to_addresses,
        subject=subject,
        html_body=html,
        text_body=text,
    )


def send_email_to_user(
    db: Session,
    *,
    user_id,
    template_slug: str,
    context: dict[str, Any],
    extra_addresses: list[str] | None = None,
) -> bool:
    user = db.get(User, user_id)
    addresses = list(extra_addresses or [])
    if user and user.email:
        addresses.append(user.email)
    return send_templated_email(db, template_slug=template_slug, to_addresses=addresses, context=context)


def send_test_email(db: Session, *, to_address: str) -> None:
    settings = get_or_create_email_settings(db)
    if not settings.smtp_host or not settings.sender_email:
        raise ValueError("SMTP host and sender email are required before sending a test email.")

    html = (
        "<p>This is a test email from <strong>ProTrack</strong>.</p>"
        "<p>Your SMTP configuration is working correctly.</p>"
    )
    sent = send_email_message(
        db,
        to_addresses=[to_address],
        subject="ProTrack SMTP test",
        html_body=html,
        text_body="This is a test email from ProTrack. Your SMTP configuration is working correctly.",
    )
    if not sent:
        raise RuntimeError("Test email could not be sent. Check SMTP settings and server logs.")


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
