"""Communication center API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EmailAttachmentMeta(BaseModel):
    name: str
    path: str | None = None
    mime_type: str | None = None


class EmailMessageRead(BaseModel):
    id: UUID
    project_id: UUID | None = None
    sent_by_user_id: UUID | None = None
    template_slug: str | None = None
    to_addresses: list[str]
    subject: str
    body_html: str
    body_text: str | None = None
    status: str
    retry_count: int
    max_retries: int
    last_error: str | None = None
    smtp_response: str | None = None
    attachments: list[EmailAttachmentMeta] = Field(default_factory=list)
    recipients_display: str | None = None
    timeline_label: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime


class EmailPreviewRequest(BaseModel):
    subject: str
    body_html: str
    body_text: str | None = None
    context: dict[str, str] = Field(default_factory=dict)


class EmailPreviewResponse(BaseModel):
    subject: str
    body_html: str
    body_text: str | None = None


class OneClickEmailRequest(BaseModel):
    project_id: UUID
    action: str
    message: str = ""
    extra_addresses: list[str] = Field(default_factory=list)
    attach_released_files: bool = False


class CustomerEmailRequest(BaseModel):
    project_id: UUID
    template_slug: str
    message: str
    to_addresses: list[str] = Field(default_factory=list)
    attachment_paths: list[str] = Field(default_factory=list)


class ManualEmailRequestExtended(BaseModel):
    template_slug: str
    to_addresses: list[str] = Field(default_factory=list)
    user_ids: list[UUID] = Field(default_factory=list)
    context: dict[str, str] = Field(default_factory=dict)
    project_id: UUID | None = None
    attachment_paths: list[str] = Field(default_factory=list)
    timeline_label: str | None = None


class EmailConnectionStatus(BaseModel):
    status: str | None = None
    checked_at: datetime | None = None
    message: str | None = None
    success: bool
