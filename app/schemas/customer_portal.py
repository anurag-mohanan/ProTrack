"""Future customer portal architecture (backend only)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CustomerPortalSession(BaseModel):
    customer_id: UUID
    contact_id: UUID
    issued_at: datetime
    expires_at: datetime


class CustomerPortalProjectView(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str
    current_stage: str | None = None
    due_date: str | None = None
    completion_percent: float = 0


class CustomerPortalFileUpload(BaseModel):
    project_id: UUID
    category: str
    filename: str
    content_type: str


class CustomerPortalReleaseApproval(BaseModel):
    project_id: UUID
    document_id: UUID
    approved: bool
    comment: str | None = None


class CustomerPortalComment(BaseModel):
    project_id: UUID
    message: str = Field(..., min_length=1, max_length=4000)


class CustomerPortalCapabilities(BaseModel):
    can_view_projects: bool = True
    can_upload_files: bool = True
    can_download_deliverables: bool = True
    can_approve_releases: bool = True
    can_comment: bool = True
