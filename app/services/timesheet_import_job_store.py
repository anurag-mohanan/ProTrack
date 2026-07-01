from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.historical_timesheet_import import (
    TimesheetImportJobProgress,
    TimesheetImportJobStatus,
    TimesheetImportSummary,
)


class TimesheetImportJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, TimesheetImportJobProgress] = {}
        self._lock = threading.Lock()

    def create_job(self, total_rows: int) -> str:
        job_id = str(uuid4())
        job = TimesheetImportJobProgress(
            job_id=job_id,
            status=TimesheetImportJobStatus.pending,
            total_rows=total_rows,
            processed_rows=0,
            percent_complete=0,
            started_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def get(self, job_id: str) -> TimesheetImportJobProgress | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job is not None else None

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = TimesheetImportJobStatus.running

    def update_progress(
        self,
        job_id: str,
        *,
        processed_rows: int,
        total_rows: int,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.processed_rows = processed_rows
            job.total_rows = total_rows
            job.percent_complete = (
                int((processed_rows / total_rows) * 100) if total_rows else 100
            )

    def complete(
        self,
        job_id: str,
        *,
        summary: TimesheetImportSummary,
        error_log: list,
        dry_run: bool,
        history_id=None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = TimesheetImportJobStatus.completed
            job.processed_rows = job.total_rows
            job.percent_complete = 100
            job.summary = summary
            job.error_log = error_log
            job.completed_at = datetime.now(timezone.utc)
            job.history_id = history_id
            job.message = "Dry run completed" if dry_run else "Import completed"

    def fail(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = TimesheetImportJobStatus.failed
            job.message = message
            job.completed_at = datetime.now(timezone.utc)


timesheet_import_job_store = TimesheetImportJobStore()
