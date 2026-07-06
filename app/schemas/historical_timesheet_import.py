from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DuplicateWeekAction(str, Enum):
    skip = "skip"
    replace = "replace"
    merge = "merge"


class ProjectResolutionAction(str, Enum):
    create = "create"
    skip = "skip"
    map_existing = "map_existing"


class DesignerResolutionAction(str, Enum):
    match_existing = "match_existing"
    create_new = "create_new"


class TimesheetImportRowStatus(str, Enum):
    ready = "ready"
    error = "error"
    skipped = "skipped"
    warning = "warning"
    imported = "imported"


class TimesheetImportJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TimesheetImportRowPreview(BaseModel):
    row_number: int
    designer: str | None = None
    tool_number: str | None = None
    project_code: str | None = None
    customer: str | None = None
    task_type: str | None = None
    np_code: str | None = None
    hours: str | None = None
    entry_date: str | None = None
    description: str | None = None
    is_np_row: bool = False
    status_label: TimesheetImportRowStatus = TimesheetImportRowStatus.ready
    messages: list[str] = Field(default_factory=list)
    matched_project_id: UUID | None = None
    matched_user_id: UUID | None = None
    matched_task_type_id: UUID | None = None


class DesignerMatchInfo(BaseModel):
    detected_name: str
    matched_user_id: UUID | None = None
    matched_user_name: str | None = None
    requires_resolution: bool = False


class DuplicateWeekInfo(BaseModel):
    week_start: date
    week_label: str
    designer_name: str
    existing_entry_count: int
    previously_imported: bool = False
    import_history_id: UUID | None = None


class TimesheetImportUploadResponse(BaseModel):
    upload_id: str
    file_name: str
    total_rows: int
    ready_rows: int
    error_rows: int
    warning_rows: int
    skipped_rows: int
    designer: DesignerMatchInfo
    duplicate_weeks: list[DuplicateWeekInfo] = Field(default_factory=list)
    preview: list[TimesheetImportRowPreview]


class TimesheetValidationIssue(BaseModel):
    row_number: int | None = None
    severity: str
    code: str
    message: str


class TimesheetImportValidateResponse(BaseModel):
    upload_id: str
    is_valid: bool
    issues: list[TimesheetValidationIssue] = Field(default_factory=list)
    ready_rows: int
    error_rows: int


class DesignerResolution(BaseModel):
    action: DesignerResolutionAction
    user_id: UUID | None = None


class ProjectRowResolution(BaseModel):
    row_number: int
    action: ProjectResolutionAction
    project_id: UUID | None = None


class CustomerRowResolution(BaseModel):
    row_number: int
    customer_id: UUID | None = None
    create_name: str | None = None


class TaskTypeRowResolution(BaseModel):
    row_number: int
    task_type_id: UUID


class TimesheetImportResolveRequest(BaseModel):
    upload_id: str
    designer: DesignerResolution
    duplicate_week_action: DuplicateWeekAction = DuplicateWeekAction.skip
    project_resolutions: list[ProjectRowResolution] = Field(default_factory=list)
    customer_resolutions: list[CustomerRowResolution] = Field(default_factory=list)
    task_type_resolutions: list[TaskTypeRowResolution] = Field(default_factory=list)


class TimesheetImportSummary(BaseModel):
    designer: str | None = None
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    duplicates_skipped: int = 0
    rows_failed: int = 0
    projects_matched: int = 0
    projects_created: int = 0
    customers_created: int = 0
    users_created: int = 0
    np_entries: int = 0
    warnings: int = 0
    errors: int = 0
    duplicate_check_disabled: bool = False


class TimesheetImportJobProgress(BaseModel):
    job_id: str
    status: TimesheetImportJobStatus
    total_rows: int
    processed_rows: int
    percent_complete: int
    summary: TimesheetImportSummary | None = None
    error_log: list[TimesheetImportRowPreview] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None
    history_id: UUID | None = None


class TimesheetImportRunRequest(BaseModel):
    upload_id: str
    dry_run: bool = False
    duplicate_week_action: DuplicateWeekAction = DuplicateWeekAction.skip
    ignore_duplicate_check: bool = True
    designer: DesignerResolution | None = None
    project_resolutions: list[ProjectRowResolution] = Field(default_factory=list)
    customer_resolutions: list[CustomerRowResolution] = Field(default_factory=list)
    task_type_resolutions: list[TaskTypeRowResolution] = Field(default_factory=list)


class TimesheetImportRunResponse(BaseModel):
    job_id: str


class TimesheetImportHistoryRead(BaseModel):
    id: UUID
    filename: str
    imported_by_name: str
    designer_name: str
    date_range_label: str | None = None
    rows_imported: int
    rows_failed: int
    duration_ms: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TimesheetImportHistoryDetail(TimesheetImportHistoryRead):
    log_json: str | None = None
    upload_id: str | None = None
