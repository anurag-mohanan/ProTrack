from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DuplicateAction(str, Enum):
    skip = "skip"
    update = "update"
    create = "create"


class ImportRowStatus(str, Enum):
    ready = "ready"
    error = "error"
    skipped = "skipped"
    duplicate = "duplicate"
    imported = "imported"
    updated = "updated"


class ImportJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ImportRowPreview(BaseModel):
    row_number: int
    tool_number: str | None = None
    customer: str | None = None
    designer: str | None = None
    surfacer: str | None = None
    quoted_hours: str | None = None
    actual_hours: str | None = None
    design_phase: str | None = None
    progress: str | None = None
    status: str | None = None
    status_label: ImportRowStatus = ImportRowStatus.ready
    messages: list[str] = Field(default_factory=list)
    existing_project_id: UUID | None = None


class ImportUploadResponse(BaseModel):
    upload_id: str
    file_name: str
    total_rows: int
    ready_rows: int
    error_rows: int
    duplicate_rows: int
    missing_customer_rows: int
    missing_designer_rows: int
    preview: list[ImportRowPreview]


class ImportRunRequest(BaseModel):
    upload_id: str
    dry_run: bool = False
    duplicate_action: DuplicateAction = DuplicateAction.skip
    import_as_archived: bool = False


class ImportSummary(BaseModel):
    projects_imported: int = 0
    projects_updated: int = 0
    projects_skipped: int = 0
    np_entries_imported: int = 0
    customers_created: int = 0
    users_created: int = 0
    milestones_created: int = 0
    errors: int = 0


class ImportJobProgress(BaseModel):
    job_id: str
    status: ImportJobStatus
    total_rows: int
    processed_rows: int
    percent_complete: int
    summary: ImportSummary | None = None
    error_log: list[ImportRowPreview] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None


class ImportRunResponse(BaseModel):
    job_id: str
