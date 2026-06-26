from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.historical_import import ImportJobProgress, ImportJobStatus, ImportSummary


class ImportJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ImportJobProgress] = {}
        self._lock = threading.Lock()

    def create_job(self, total_rows: int) -> str:
        job_id = str(uuid4())
        job = ImportJobProgress(
            job_id=job_id,
            status=ImportJobStatus.pending,
            total_rows=total_rows,
            processed_rows=0,
            percent_complete=0,
            started_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def get(self, job_id: str) -> ImportJobProgress | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job is not None else None

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = ImportJobStatus.running

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
        summary: ImportSummary,
        error_log: list,
        dry_run: bool,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = ImportJobStatus.completed
            job.processed_rows = job.total_rows
            job.percent_complete = 100
            job.summary = summary
            job.error_log = error_log
            job.completed_at = datetime.now(timezone.utc)
            job.message = "Dry run completed" if dry_run else "Import completed"

    def fail(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = ImportJobStatus.failed
            job.message = message
            job.completed_at = datetime.now(timezone.utc)


import_job_store = ImportJobStore()
