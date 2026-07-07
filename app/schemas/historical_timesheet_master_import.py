from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MasterImportJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class MasterDesignerScanRow(BaseModel):
    designer: str
    rows: int
    date_from: date | None = None
    date_to: date | None = None
    date_range_label: str
    user_matched: bool = True


class MasterScanResponse(BaseModel):
    upload_id: str
    filename: str
    row_count: int
    designer_count: int
    date_from: date | None = None
    date_to: date | None = None
    date_range_label: str | None = None
    designers: list[MasterDesignerScanRow] = Field(default_factory=list)


class MasterUploadResponse(BaseModel):
    upload_id: str
    filename: str
    scan: MasterScanResponse


class MasterImportRunRequest(BaseModel):
    upload_id: str
    designers: list[str] | None = None
    auto_create_missing_task_types: bool = False
    auto_create_task_type_stream_id: UUID | None = None


class MasterImportRunResponse(BaseModel):
    job_id: str
    backup_path: str | None = None


class MasterImportLogRow(BaseModel):
    row: int
    designer: str | None = None
    project: str | None = None
    error: str


class MasterImportSummary(BaseModel):
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    errors: int = 0
    duration_seconds: int = 0
    backup_path: str | None = None
    duplicate_check_disabled: bool = True
    unknown_task_types: list[str] = Field(default_factory=list)
    auto_created_task_types: list[str] = Field(default_factory=list)
    leave_entries: int = 0
    lack_of_work_entries: int = 0


class MasterImportJobProgress(BaseModel):
    job_id: str
    status: MasterImportJobStatus
    percent_complete: int
    rows_processed: int = 0
    rows_total: int = 0
    rows_imported: int = 0
    current_designer: str | None = None
    message: str | None = None
    last_progress_at: datetime | None = None
    summary: MasterImportSummary | None = None
    log_rows: list[MasterImportLogRow] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    log_download_name: str | None = None
