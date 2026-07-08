"""Shared email delivery types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EmailAttachment:
    filename: str
    path: Path | None = None
    content: bytes | None = None
    mime_type: str = "application/octet-stream"


@dataclass
class OutboundEmail:
    to_addresses: list[str]
    subject: str
    html_body: str
    text_body: str | None = None
    cc_addresses: list[str] = field(default_factory=list)
    reply_to: str | None = None
    attachments: list[EmailAttachment] = field(default_factory=list)


@dataclass
class EmailDeliveryResult:
    success: bool
    smtp_response: str | None = None
    error: str | None = None
    delivery_ms: int | None = None
