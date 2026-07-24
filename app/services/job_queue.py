"""Durable background job queue (R1 — no Redis/Celery)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import BackgroundJob

logger = logging.getLogger("protrack.jobs")

JOB_PROCESS_EMAIL_QUEUE = "process_email_queue"
JOB_HISTORICAL_IMPORT = "historical_import"
JOB_TIMESHEET_IMPORT = "timesheet_import"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job(
    db: Session,
    *,
    job_type: str,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 3,
    commit: bool = True,
) -> BackgroundJob:
    row = BackgroundJob(
        job_type=job_type,
        payload_json=json.dumps(payload or {}),
        status=STATUS_QUEUED,
        attempts=0,
        max_attempts=max_attempts,
        run_after=_utcnow(),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def _payload(row: BackgroundJob) -> dict[str, Any]:
    try:
        data = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def claim_next_job(db: Session) -> BackgroundJob | None:
    now = _utcnow()
    row = None
    try:
        row = db.scalar(
            select(BackgroundJob)
            .where(
                BackgroundJob.status == STATUS_QUEUED,
                BackgroundJob.run_after <= now,
            )
            .order_by(BackgroundJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
    except Exception:
        db.rollback()
        row = None
    if row is None:
        row = db.scalar(
            select(BackgroundJob)
            .where(
                BackgroundJob.status == STATUS_QUEUED,
                BackgroundJob.run_after <= now,
            )
            .order_by(BackgroundJob.created_at.asc())
            .limit(1)
        )
    if row is None:
        return None
    row.status = STATUS_RUNNING
    row.attempts = int(row.attempts or 0) + 1
    row.started_at = now
    row.last_error = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _execute(db: Session, row: BackgroundJob) -> None:
    payload = _payload(row)
    if row.job_type == JOB_PROCESS_EMAIL_QUEUE:
        from app.services.email.engine import EmailService

        limit = int(payload.get("limit") or 50)
        EmailService(db).process_queue(limit=limit)
        return
    if row.job_type == JOB_HISTORICAL_IMPORT:
        from app.api.v1.imports import _execute_import_job

        _execute_import_job(
            str(payload["job_id"]),
            str(payload["upload_id"]),
            dry_run=bool(payload.get("dry_run")),
            duplicate_action=str(payload.get("duplicate_action") or "skip"),
            import_as_archived=bool(payload.get("import_as_archived")),
        )
        return
    if row.job_type == JOB_TIMESHEET_IMPORT:
        from uuid import UUID as _UUID

        from app.api.v1.timesheet_imports import (
            _build_context,
            _execute_timesheet_import_job,
        )
        from app.schemas.historical_timesheet_import import TimesheetImportRunRequest

        request_data = payload.get("request") or {}
        req = TimesheetImportRunRequest.model_validate(request_data)
        context = _build_context(req)
        _execute_timesheet_import_job(
            str(payload["job_id"]),
            str(payload["upload_id"]),
            dry_run=bool(payload.get("dry_run")),
            context=context,
            imported_by_id=_UUID(str(payload["imported_by_id"])),
        )
        return
    raise ValueError(f"Unknown job type: {row.job_type}")



def complete_job(db: Session, row: BackgroundJob, *, error: str | None = None) -> None:
    now = _utcnow()
    if error:
        row.last_error = error[:2000]
        if int(row.attempts or 0) < int(row.max_attempts or 3):
            row.status = STATUS_QUEUED
            row.run_after = now
        else:
            row.status = STATUS_FAILED
            row.finished_at = now
    else:
        row.status = STATUS_SUCCEEDED
        row.finished_at = now
        row.last_error = None
    db.add(row)
    db.commit()


def process_job_by_id(job_id: UUID | str) -> None:
    """Run a single queued job by id (used from FastAPI BackgroundTasks)."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        uid = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
        row = db.get(BackgroundJob, uid)
        if row is None:
            return
        if row.status not in {STATUS_QUEUED, STATUS_RUNNING}:
            return
        if row.status == STATUS_QUEUED:
            row.status = STATUS_RUNNING
            row.attempts = int(row.attempts or 0) + 1
            row.started_at = _utcnow()
            db.add(row)
            db.commit()
            db.refresh(row)
        try:
            _execute(db, row)
            complete_job(db, row)
        except Exception as exc:
            logger.exception("Background job %s failed: %s", row.id, exc)
            complete_job(db, row, error=str(exc))
    finally:
        db.close()


def process_one(db: Session) -> BackgroundJob | None:
    row = claim_next_job(db)
    if row is None:
        return None
    try:
        _execute(db, row)
        complete_job(db, row)
    except Exception as exc:
        logger.exception("Background job %s failed: %s", row.id, exc)
        complete_job(db, row, error=str(exc))
    return row


def process_due(db: Session, *, limit: int = 20) -> int:
    done = 0
    for _ in range(max(1, limit)):
        row = process_one(db)
        if row is None:
            break
        done += 1
    return done
