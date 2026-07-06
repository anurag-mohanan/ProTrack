from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.historical_timesheet_folder_import import (
    FolderImportJobProgress,
    FolderImportJobStatus,
    FolderImportLogRow,
    FolderImportSummary,
)


class TimesheetFolderImportJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, FolderImportJobProgress] = {}
        self._cancel_flags: dict[str, bool] = {}
        self._lock = threading.Lock()

    def create_job(self, *, files_total: int, rows_total: int) -> str:
        job_id = str(uuid4())
        job = FolderImportJobProgress(
            job_id=job_id,
            status=FolderImportJobStatus.pending,
            percent_complete=0,
            files_total=files_total,
            rows_total=rows_total,
            started_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[job_id] = job
            self._cancel_flags[job_id] = False
        return job_id

    def get(self, job_id: str) -> FolderImportJobProgress | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job is not None else None

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._cancel_flags.get(job_id, False)

    def request_cancel(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._cancel_flags[job_id] = True
            return True

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            self._jobs[job_id].status = FolderImportJobStatus.running

    def update_progress(
        self,
        job_id: str,
        *,
        percent_complete: int,
        current_designer: str | None = None,
        current_file: str | None = None,
        rows_imported: int = 0,
        rows_total: int | None = None,
        files_processed: int = 0,
        files_total: int | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.percent_complete = min(max(percent_complete, 0), 100)
            if current_designer is not None:
                job.current_designer = current_designer
            if current_file is not None:
                job.current_file = current_file
            job.rows_imported = rows_imported
            if rows_total is not None:
                job.rows_total = rows_total
            job.files_processed = files_processed
            if files_total is not None:
                job.files_total = files_total

    def complete(
        self,
        job_id: str,
        *,
        summary: FolderImportSummary,
        log_rows: list[FolderImportLogRow],
        log_download_name: str,
        cancelled: bool = False,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = (
                FolderImportJobStatus.cancelled
                if cancelled
                else FolderImportJobStatus.completed
            )
            job.percent_complete = 100
            job.summary = summary
            job.log_rows = log_rows
            job.log_download_name = log_download_name
            job.completed_at = datetime.now(timezone.utc)
            job.message = "Import cancelled" if cancelled else "Import completed"

    def fail(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = FolderImportJobStatus.failed
            job.message = message
            job.completed_at = datetime.now(timezone.utc)


timesheet_folder_import_job_store = TimesheetFolderImportJobStore()
