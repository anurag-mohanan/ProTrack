"""Email provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.foundation import EmailSettings
from app.services.email.types import EmailDeliveryResult, OutboundEmail


class BaseEmailProvider(ABC):
    provider_type: str = "smtp"

    @abstractmethod
    def test_connection(self, settings: EmailSettings) -> EmailDeliveryResult:
        raise NotImplementedError

    @abstractmethod
    def send(self, settings: EmailSettings, message: OutboundEmail) -> EmailDeliveryResult:
        raise NotImplementedError
