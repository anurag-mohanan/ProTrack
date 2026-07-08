"""Generic SMTP email provider."""

from __future__ import annotations

import logging
import re
import smtplib
import time
from email.message import EmailMessage as MimeEmailMessage

from app.core.secret_encryption import decrypt_secret
from app.models.foundation import EmailSettings
from app.services.email.providers.base import BaseEmailProvider
from app.services.email.types import EmailAttachment, EmailDeliveryResult, OutboundEmail

logger = logging.getLogger(__name__)


class SMTPProvider(BaseEmailProvider):
    provider_type = "smtp"

    def _smtp_connection(self, settings: EmailSettings):
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

    def test_connection(self, settings: EmailSettings) -> EmailDeliveryResult:
        if not settings.smtp_host:
            return EmailDeliveryResult(success=False, error="SMTP host is required.")
        started = time.perf_counter()
        try:
            with self._smtp_connection(settings) as server:
                response = server.noop()[1]
                if isinstance(response, list):
                    response = " ".join(
                        part.decode() if isinstance(part, bytes) else str(part)
                        for part in response
                    )
                return EmailDeliveryResult(
                    success=True,
                    smtp_response=str(response),
                    delivery_ms=int((time.perf_counter() - started) * 1000),
                )
        except Exception as exc:
            logger.exception("SMTP connection test failed")
            return EmailDeliveryResult(
                success=False,
                error=str(exc),
                delivery_ms=int((time.perf_counter() - started) * 1000),
            )

    def send(self, settings: EmailSettings, message: OutboundEmail) -> EmailDeliveryResult:
        started = time.perf_counter()
        mime = self._build_mime_message(settings, message)
        try:
            with self._smtp_connection(settings) as server:
                refused = server.send_message(mime)
                if refused:
                    return EmailDeliveryResult(
                        success=False,
                        error=f"SMTP refused recipients: {refused}",
                        delivery_ms=int((time.perf_counter() - started) * 1000),
                    )
                return EmailDeliveryResult(
                    success=True,
                    smtp_response="250 Message accepted",
                    delivery_ms=int((time.perf_counter() - started) * 1000),
                )
        except Exception as exc:
            logger.exception("SMTP send failed")
            return EmailDeliveryResult(
                success=False,
                error=str(exc),
                delivery_ms=int((time.perf_counter() - started) * 1000),
            )

    def _build_mime_message(
        self, settings: EmailSettings, message: OutboundEmail
    ) -> MimeEmailMessage:
        mime = MimeEmailMessage()
        mime["Subject"] = message.subject
        mime["From"] = (
            f"{settings.sender_name} <{settings.sender_email}>"
            if settings.sender_name
            else settings.sender_email or ""
        )
        mime["To"] = ", ".join(message.to_addresses)
        if message.cc_addresses:
            mime["Cc"] = ", ".join(message.cc_addresses)
        reply_to = message.reply_to or settings.reply_to_email
        if reply_to:
            mime["Reply-To"] = reply_to

        text_body = message.text_body or _html_to_text(message.html_body)
        if settings.company_signature:
            text_body = f"{text_body}\n\n{settings.company_signature}"
            html_body = f"{message.html_body}<br/><br/>{settings.company_signature}"
        else:
            html_body = message.html_body

        if message.attachments:
            mime.set_content(text_body)
            mime.add_alternative(html_body, subtype="html")
            for attachment in message.attachments:
                self._attach_file(mime, attachment)
        else:
            mime.set_content(text_body)
            mime.add_alternative(html_body, subtype="html")
        return mime

    def _attach_file(self, mime: MimeEmailMessage, attachment: EmailAttachment) -> None:
        if attachment.content is not None:
            mime.add_attachment(
                attachment.content,
                maintype=attachment.mime_type.split("/")[0],
                subtype=attachment.mime_type.split("/")[-1],
                filename=attachment.filename,
            )
        elif attachment.path and attachment.path.is_file():
            data = attachment.path.read_bytes()
            mime.add_attachment(
                data,
                maintype=attachment.mime_type.split("/")[0],
                subtype=attachment.mime_type.split("/")[-1],
                filename=attachment.filename,
            )


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
