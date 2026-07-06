from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class FolderImportJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class FolderDesignerScanRow(BaseModel):
    designer: str
    files: int
    entries: int


class FolderScanResponse(BaseModel):
    batch_id: str | None = None
    source_label: str
    designer_count: int
    file_count: int
    estimated_entries: int
    designers: list[FolderDesignerScanRow] = Field(default_factory=list)


class FolderBatchUploadResponse(BaseModel):
    batch_id: str
    file_count: int
    source_label: str


class FolderScanRequest(BaseModel):
    batch_id: str | None = None
    source_path: str | None = None


class FolderImportRunRequest(BaseModel):
    batch_id: str | None = None
    source_path: str | None = None


class FolderImportRunResponse(BaseModel):
    job_id: str
    backup_path: str | None = None


class FolderImportLogRow(BaseModel):
    file: str
    row: int | None = None
    designer: str | None = None
    entry_date: str | None = None
    project: str | None = None
    reason: str


class FolderImportSummary(BaseModel):
    designers_imported: int = 0
    files_imported: int = 0
    rows_read: int = 0
    rows_imported: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    duration_seconds: int = 0
    backup_path: str | None = None


class FolderImportJobProgress(BaseModel):
    job_id: str
    status: FolderImportJobStatus
    percent_complete: int
    current_designer: str | None = None
    current_file: str | None = None
    rows_imported: int = 0
    rows_total: int = 0
    files_processed: int = 0
    files_total: int = 0
    summary: FolderImportSummary | None = None
    log_rows: list[FolderImportLogRow] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None
    log_download_name: str | None = None
