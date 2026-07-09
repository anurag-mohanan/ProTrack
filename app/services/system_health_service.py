from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import APP_VERSION, INTERNAL_RELEASE, RELEASE_CANDIDATE, UPLOAD_DIR
from app.models.enums import ActivityAction
from app.models.models import Activity, TimesheetImportHistory, User
from app.schemas.system import SystemHealthRead


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def get_system_health(db: Session) -> SystemHealthRead:
    backend_status = "ok"
    database_status = "ok"
    database_version: str | None = None

    try:
        database_version = db.scalar(text("SELECT sqlite_version()"))
    except Exception:
        try:
            database_version = db.scalar(text("SELECT version()"))
        except Exception:
            database_status = "degraded"
            backend_status = "degraded"

    try:
        db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True)))
    except Exception:
        database_status = "error"
        backend_status = "error"

    active_users = int(
        db.scalar(
            select(func.count()).select_from(User).where(
                User.is_active.is_(True),
                User.is_deleted.is_(False),
                User.is_archived.is_(False),
            )
        )
        or 0
    )

    storage_bytes = _directory_size(Path(UPLOAD_DIR))

    import_queue = int(
        db.scalar(
            select(func.count())
            .select_from(TimesheetImportHistory)
            .where(TimesheetImportHistory.status.in_(("pending", "processing")))
        )
        or 0
    )

    failed_jobs = int(
        db.scalar(
            select(func.count())
            .select_from(TimesheetImportHistory)
            .where(TimesheetImportHistory.rows_failed > 0)
        )
        or 0
    )

    cutoff = datetime.now(UTC) - timedelta(days=7)
    error_rows = db.scalars(
        select(Activity.new_value)
        .where(
            Activity.action.in_(
                (
                    ActivityAction.login_failed,
                )
            ),
            Activity.created_at >= cutoff,
        )
        .order_by(Activity.created_at.desc())
        .limit(5)
    ).all()
    recent_errors = [str(row) for row in error_rows if row]

    failed_emails = 0
    try:
        from app.models.foundation import EmailMessage

        failed_emails = int(
            db.scalar(
                select(func.count())
                .select_from(EmailMessage)
                .where(EmailMessage.status == "failed")
            )
            or 0
        )
    except Exception:
        failed_emails = 0

    return SystemHealthRead(
        backend_status=backend_status,
        database_status=database_status,
        api_status="ok" if backend_status == "ok" else backend_status,
        application_version=APP_VERSION,
        release_candidate=RELEASE_CANDIDATE,
        database_version=str(database_version) if database_version else None,
        active_users=active_users,
        storage_usage_bytes=storage_bytes,
        storage_usage_label=_format_bytes(storage_bytes),
        last_backup=None,
        import_queue=import_queue,
        failed_jobs=failed_jobs,
        failed_emails=failed_emails,
        recent_errors=recent_errors,
        internal_release=INTERNAL_RELEASE,
    )
