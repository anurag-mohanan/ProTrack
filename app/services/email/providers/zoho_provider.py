"""Zoho Mail SMTP provider."""

from __future__ import annotations

from app.models.foundation import EmailSettings
from app.services.email.providers.smtp_provider import SMTPProvider
from app.services.email.types import EmailDeliveryResult, OutboundEmail

ZOHO_SMTP_HOST = "smtp.zoho.com"
ZOHO_SSL_PORT = 465
ZOHO_TLS_PORT = 587


class ZohoProvider(SMTPProvider):
    provider_type = "zoho"

    @staticmethod
    def apply_defaults(settings: EmailSettings) -> EmailSettings:
        settings.provider_type = "zoho"
        settings.smtp_host = ZOHO_SMTP_HOST
        settings.smtp_port = ZOHO_SSL_PORT
        settings.use_ssl = True
        settings.use_tls = False
        return settings

    def test_connection(self, settings: EmailSettings) -> EmailDeliveryResult:
        normalized = ZohoProvider.apply_defaults(settings)
        return super().test_connection(normalized)

    def send(self, settings: EmailSettings, message: OutboundEmail) -> EmailDeliveryResult:
        normalized = ZohoProvider.apply_defaults(settings)
        return super().send(normalized, message)
