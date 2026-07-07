from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.historical_timesheet_master_import import (
    MasterImportJobProgress,
    MasterImportJobStatus,
    MasterImportLogRow,
    MasterImportSummary,
)


class TimesheetMasterImportJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, MasterImportJobProgress] = {}
        self._cancel_flags: dict[str, bool] = {}
        self._lock = threading.Lock()

    def create_job(self, *, rows_total: int) -> str:
        job_id = str(uuid4())
        now = datetime.now(timezone.utc)
        job = MasterImportJobProgress(
            job_id=job_id,
            status=MasterImportJobStatus.pending,
            percent_complete=0,
            rows_total=rows_total,
            started_at=now,
            last_progress_at=now,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._cancel_flags[job_id] = False
        return job_id

    def get(self, job_id: str) -> MasterImportJobProgress | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                self._mark_stale_locked(job)
            return job.model_copy(deep=True) if job is not None else None

    def _mark_stale_locked(
        self,
        job: MasterImportJobProgress,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        if job.status != MasterImportJobStatus.running:
            return
        now = datetime.now(timezone.utc)
        last = job.last_progress_at or job.started_at
        if last is None:
            return
        if (now - last).total_seconds() <= timeout_seconds:
            return
        job.status = MasterImportJobStatus.failed
        job.completed_at = now
        job.message = (
            "Import failed: worker made no progress for over "
            f"{timeout_seconds} seconds. Check server logs."
        )

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._cancel_flags.get(job_id, False)

    def request_cancel(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._cancel_flags[job_id] = True
            return True

    def mark_running(self, job_id: str, *, message: str | None = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = MasterImportJobStatus.running
            job.last_progress_at = datetime.now(timezone.utc)
            if message:
                job.message = message

    def update_progress(
        self,
        job_id: str,
        *,
        percent_complete: int,
        rows_processed: int = 0,
        rows_imported: int = 0,
        rows_total: int | None = None,
        current_designer: str | None = None,
        message: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.percent_complete = min(max(percent_complete, 0), 100)
            job.rows_processed = rows_processed
            job.rows_imported = rows_imported
            job.last_progress_at = datetime.now(timezone.utc)
            if rows_total is not None:
                job.rows_total = rows_total
            if current_designer is not None:
                job.current_designer = current_designer
            if message is not None:
                job.message = message

    def complete(
        self,
        job_id: str,
        *,
        summary: MasterImportSummary,
        log_rows: list[MasterImportLogRow],
        log_download_name: str,
        cancelled: bool = False,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = (
                MasterImportJobStatus.cancelled
                if cancelled
                else MasterImportJobStatus.completed
            )
            job.percent_complete = 100
            job.summary = summary
            job.log_rows = log_rows
            job.log_download_name = log_download_name
            job.completed_at = datetime.now(timezone.utc)
            job.last_progress_at = job.completed_at
            job.message = "Import cancelled" if cancelled else "Import completed"

    def fail(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = MasterImportJobStatus.failed
            job.message = message
            job.completed_at = datetime.now(timezone.utc)
            job.last_progress_at = job.completed_at


timesheet_master_import_job_store = TimesheetMasterImportJobStore()
