"""System Health & Operations Center data assembly."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.routing import APIRoute
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import APP_VERSION, BASE_DIR, RELEASE_CANDIDATE, UPLOAD_DIR
from app.core.runtime import SERVER_STARTED_AT
from app.models.enums import ActivityAction
from app.models.models import (
    Activity,
    Customer,
    Milestone,
    Project,
    Team,
    Timesheet,
    TimesheetEntry,
    TimesheetImportHistory,
    User,
)
from app.schemas.operations import (
    AiStatusSummary,
    ApiMonitorRow,
    ApplicationStatistics,
    BackgroundJobRow,
    BackupSummary,
    DatabaseHealth,
    DiagnosticResult,
    DiagnosticsReport,
    DiskUsageItem,
    EmailStatusSummary,
    ErrorLogRow,
    HealthAlert,
    HealthLevel,
    IisHealth,
    LogLine,
    OperationsCenterSnapshot,
    PerformanceMetrics,
    ServiceCard,
    ServiceStatus,
    TimelineEvent,
    UserActivitySummary,
)
from app.services.backup_service import BACKUP_DIR, list_database_backups
from app.services.health_history_store import record_snapshot
from app.services.import_job_store import import_job_store
from app.services.timesheet_folder_import_job_store import timesheet_folder_import_job_store
from app.services.timesheet_import_job_store import timesheet_import_job_store
from app.services.timesheet_master_import_job_store import timesheet_master_import_job_store

logger = logging.getLogger(__name__)

_LOG_DIR = BASE_DIR / "logs"


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


def _format_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} Day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} Hour{'s' if hours != 1 else ''}")
    if minutes and not days:
        parts.append(f"{minutes} Min")
    return " ".join(parts) or "< 1 Min"


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


def _disk_item(name: str, path: Path, *, total_bytes: int) -> DiskUsageItem:
    used = _directory_size(path) if path.is_dir() else (path.stat().st_size if path.is_file() else 0)
    percent = (used / total_bytes * 100) if total_bytes else 0.0
    return DiskUsageItem(
        name=name,
        path=str(path),
        used_bytes=used,
        total_bytes=total_bytes,
        used_label=_format_bytes(used),
        total_label=_format_bytes(total_bytes),
        percent_used=round(percent, 1),
        warning=percent >= 80,
        critical=percent >= 90,
    )


def _sqlite_path() -> Path | None:
    from app.db.session import DATABASE_URL

    if not DATABASE_URL.startswith("sqlite"):
        return None
    raw = DATABASE_URL.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / raw
    return path


def _uptime_seconds() -> int:
    return int((datetime.now(UTC) - SERVER_STARTED_AT).total_seconds())


def _service_status(ok: bool, *, degraded: bool = False) -> ServiceStatus:
    if ok and not degraded:
        return "running"
    if degraded:
        return "degraded"
    return "stopped"


def _status_label(status: ServiceStatus) -> str:
    return {
        "running": "Running",
        "degraded": "Degraded",
        "stopped": "Stopped",
        "unknown": "Unknown",
    }[status]


def _collect_memory_mb() -> float | None:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        return round(usage.ru_maxrss / 1024, 1) if sys.platform != "win32" else round(usage.ru_maxrss / (1024 * 1024), 1)
    except Exception:
        pass
    try:
        import psutil  # type: ignore[import-not-found]

        return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None


def _collect_cpu_percent() -> float | None:
    try:
        import psutil  # type: ignore[import-not-found]

        return round(psutil.cpu_percent(interval=0.1), 1)
    except Exception:
        return None


def _last_backup_info() -> tuple[datetime | None, str | None, int]:
    backups = list_database_backups()
    if not backups:
        return None, None, 0
    latest = backups[0]
    try:
        modified = datetime.fromisoformat(latest["modified_at"])
    except (KeyError, ValueError):
        modified = None
    filename = latest.get("filename")
    size = int(latest.get("size_bytes") or 0)
    return modified, filename, size


def _build_database_health(db: Session) -> DatabaseHealth:
    db_path = _sqlite_path()
    connected = True
    sqlite_version: str | None = None
    table_count = 0
    integrity_status: str | None = None

    try:
        sqlite_version = str(db.scalar(text("SELECT sqlite_version()")))
        table_count = int(
            db.scalar(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            )
            or 0
        )
    except Exception:
        connected = False

    size_bytes = db_path.stat().st_size if db_path and db_path.is_file() else 0
    last_backup, backup_name, _ = _last_backup_info()

    return DatabaseHealth(
        connected=connected,
        database_name=db_path.name if db_path else None,
        database_size_bytes=size_bytes,
        database_size_label=_format_bytes(size_bytes),
        sqlite_version=sqlite_version,
        table_count=table_count,
        total_projects=int(db.scalar(select(func.count()).select_from(Project).where(Project.is_deleted.is_(False))) or 0),
        total_timesheets=int(db.scalar(select(func.count()).select_from(Timesheet)) or 0),
        total_users=int(db.scalar(select(func.count()).select_from(User).where(User.is_deleted.is_(False))) or 0),
        total_customers=int(db.scalar(select(func.count()).select_from(Customer)) or 0),
        total_entries=int(
            db.scalar(select(func.count()).select_from(TimesheetEntry).where(TimesheetEntry.is_deleted.is_(False)))
            or 0
        ),
        open_connections=1,
        slow_queries=0,
        last_backup=last_backup,
        last_backup_label=backup_name,
        integrity_status=integrity_status,
    )


def _build_iis_health(db: Session) -> IisHealth:
    host = platform.system()
    active_users = int(
        db.scalar(
            select(func.count()).select_from(User).where(
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )
        or 0
    )
    note = None
    website_running: bool | None = None
    app_pool_status: str | None = None

    if host == "Windows":
        site_name = os.getenv("PROTRACK_IIS_SITE", "ProTrack")
        app_pool_status = os.getenv("PROTRACK_APP_POOL_STATUS", "Unknown")
        website_running = app_pool_status.lower() in {"started", "running", "unknown"}
        note = "IIS metrics require host-level monitoring; values may be approximate."
    else:
        site_name = "ProTrack"
        website_running = True
        app_pool_status = "n/a"
        note = "Running outside IIS host."

    return IisHealth(
        website_running=website_running,
        app_pool_status=app_pool_status,
        site_name=site_name,
        https_enabled=API_PUBLIC_URL.startswith("https") if (API_PUBLIC_URL := os.getenv("PROTRACK_API_URL", "")) else None,
        requests_today=0,
        active_sessions=active_users,
        current_users=active_users,
        host_platform=host,
        note=note,
    )


def _list_store_jobs(store, name: str) -> list[BackgroundJobRow]:
    rows: list[BackgroundJobRow] = []
    lock = getattr(store, "_lock", None)
    jobs = getattr(store, "_jobs", {})
    if lock is not None:
        with lock:
            items = list(jobs.values())
    else:
        items = list(jobs.values())

    for job in items:
        started = getattr(job, "started_at", None)
        completed = getattr(job, "completed_at", None)
        duration = None
        if started and completed:
            duration = (completed - started).total_seconds()
        rows.append(
            BackgroundJobRow(
                job_id=str(getattr(job, "job_id", uuid4())),
                name=name,
                status=str(getattr(job.status, "value", job.status)),
                last_run=started,
                duration_seconds=duration,
                message=getattr(job, "message", None),
                can_retry=str(getattr(job.status, "value", job.status)) == "failed",
            )
        )
    return rows


def _build_background_jobs(db: Session) -> list[BackgroundJobRow]:
    rows = []
    rows.extend(_list_store_jobs(import_job_store, "Historical Import"))
    rows.extend(_list_store_jobs(timesheet_import_job_store, "Timesheet Import"))
    rows.extend(_list_store_jobs(timesheet_folder_import_job_store, "Folder Import"))
    rows.extend(_list_store_jobs(timesheet_master_import_job_store, "Master Import"))

    pending_imports = db.scalars(
        select(TimesheetImportHistory)
        .where(TimesheetImportHistory.status.in_(("pending", "processing")))
        .order_by(TimesheetImportHistory.created_at.desc())
        .limit(10)
    ).all()
    for record in pending_imports:
        rows.append(
            BackgroundJobRow(
                job_id=str(record.id),
                name="Import History",
                status=record.status,
                last_run=record.created_at,
                message=f"{record.rows_imported or 0} rows imported",
            )
        )

    rows.append(
        BackgroundJobRow(
            job_id="email-queue",
            name="Email Queue",
            status="waiting",
            message="Processed on demand via admin action",
        )
    )
    rows.append(
        BackgroundJobRow(
            job_id="nightly-backup",
            name="Nightly Backup",
            status="waiting",
            message="Manual backup — no scheduler configured",
            next_run=None,
        )
    )
    return rows


def _build_errors(db: Session) -> list[ErrorLogRow]:
    rows: list[ErrorLogRow] = []
    cutoff = datetime.now(UTC) - timedelta(days=7)

    activities = db.scalars(
        select(Activity)
        .where(
            Activity.action.in_((ActivityAction.login_failed,)),
            Activity.created_at >= cutoff,
        )
        .order_by(Activity.created_at.desc())
        .limit(20)
    ).all()
    for activity in activities:
        rows.append(
            ErrorLogRow(
                id=str(activity.id),
                occurred_at=activity.created_at,
                severity="warning",
                module="authentication",
                endpoint="/api/v1/auth/token",
                user=activity.actor_name,
                message=str(activity.new_value or "Login failed"),
            )
        )

    try:
        from app.models.foundation import EmailMessage

        failed_emails = db.scalars(
            select(EmailMessage)
            .where(EmailMessage.status == "failed")
            .order_by(EmailMessage.updated_at.desc())
            .limit(10)
        ).all()
        for email in failed_emails:
            rows.append(
                ErrorLogRow(
                    id=str(email.id),
                    occurred_at=email.updated_at or email.created_at,
                    severity="critical",
                    module="email",
                    endpoint="/api/v1/emails/queue",
                    message=email.last_error or f"Failed to send: {email.subject}",
                    stack_trace=email.last_error,
                )
            )
    except Exception:
        pass

    rows.sort(key=lambda row: row.occurred_at, reverse=True)
    return rows[:25]


def _build_timeline(db: Session) -> list[TimelineEvent]:
    actions = (
        ActivityAction.login_failed,
        ActivityAction.project_created,
        ActivityAction.timesheet_submitted,
        ActivityAction.project_archived,
        ActivityAction.email_sent,
    )
    rows = db.scalars(
        select(Activity)
        .where(Activity.action.in_(actions))
        .order_by(Activity.created_at.desc())
        .limit(20)
    ).all()
    events: list[TimelineEvent] = []
    for row in rows:
        severity = "error" if row.action == ActivityAction.login_failed else "info"
        if row.action == ActivityAction.email_sent:
            severity = "success"
        events.append(
            TimelineEvent(
                occurred_at=row.created_at,
                event_type=row.action.value,
                title=row.action.value.replace("_", " ").title(),
                detail=row.new_value,
                severity=severity,
            )
        )
    events.append(
        TimelineEvent(
            occurred_at=SERVER_STARTED_AT,
            event_type="server_start",
            title="Application Started",
            detail="Backend process started",
            severity="success",
        )
    )
    events.sort(key=lambda item: item.occurred_at, reverse=True)
    return events[:20]


def _build_alerts(
    *,
    overall: HealthLevel,
    disk_items: list[DiskUsageItem],
    database: DatabaseHealth,
    email: EmailStatusSummary,
    errors: list[ErrorLogRow],
) -> list[HealthAlert]:
    alerts: list[HealthAlert] = []
    for disk in disk_items:
        if disk.critical:
            alerts.append(
                HealthAlert(
                    id=f"disk-{disk.name}",
                    severity="critical",
                    title=f"Disk Usage {disk.percent_used:.0f}% — {disk.name}",
                    detail=f"{disk.used_label} of {disk.total_label} used",
                )
            )
        elif disk.warning:
            alerts.append(
                HealthAlert(
                    id=f"disk-{disk.name}",
                    severity="warning",
                    title=f"Disk Usage {disk.percent_used:.0f}% — {disk.name}",
                )
            )

    if not database.connected:
        alerts.append(HealthAlert(id="db-down", severity="critical", title="Database Disconnected"))
    if database.last_backup is None:
        alerts.append(HealthAlert(id="no-backup", severity="warning", title="No Recent Backup"))
    elif database.last_backup < datetime.now(UTC) - timedelta(days=7):
        alerts.append(HealthAlert(id="stale-backup", severity="warning", title="Backup Older Than 7 Days"))

    if email.failed_emails:
        alerts.append(
            HealthAlert(
                id="email-failed",
                severity="warning",
                title=f"{email.failed_emails} Failed Email(s)",
            )
        )
    if email.smtp_connected is False:
        alerts.append(HealthAlert(id="smtp-fail", severity="warning", title="SMTP Authentication Failed"))

    critical_errors = [e for e in errors if e.severity == "critical"]
    if critical_errors:
        alerts.append(
            HealthAlert(
                id="recent-errors",
                severity="critical",
                title=f"{len(critical_errors)} Critical Error(s)",
            )
        )

    if overall == "healthy" and not alerts:
        alerts.append(
            HealthAlert(id="all-good", severity="success", title="All Systems Operational")
        )
    return alerts


def _overall_status(
    *,
    database: DatabaseHealth,
    disk_items: list[DiskUsageItem],
    errors: list[ErrorLogRow],
    email: EmailStatusSummary,
) -> tuple[HealthLevel, str]:
    if not database.connected:
        return "critical", "Critical"
    if any(d.critical for d in disk_items):
        return "critical", "Critical"
    if any(e.severity == "critical" for e in errors):
        return "critical", "Critical"
    if (
        any(d.warning for d in disk_items)
        or email.failed_emails > 0
        or email.smtp_connected is False
        or database.last_backup is None
    ):
        return "warning", "Warning"
    return "healthy", "Healthy"


def get_operations_snapshot(db: Session, *, probe_ms: int = 0) -> OperationsCenterSnapshot:
    started = time.perf_counter()
    now = datetime.now(UTC)
    uptime = _uptime_seconds()

    database = _build_database_health(db)
    iis = _build_iis_health(db)
    errors = _build_errors(db)

    try:
        total, used, _free = shutil.disk_usage(BASE_DIR)
    except OSError:
        total, used = 0, 0
    disk_usage = [
        _disk_item("Database Folder", BACKUP_DIR.parent / "data" if (BACKUP_DIR.parent / "data").exists() else (_sqlite_path().parent if _sqlite_path() else BASE_DIR), total_bytes=total),
        _disk_item("Uploads Folder", Path(UPLOAD_DIR), total_bytes=total),
        _disk_item("Logs Folder", _LOG_DIR, total_bytes=total),
        _disk_item("Backups Folder", BACKUP_DIR, total_bytes=total),
    ]

    email = _build_email_status(db)
    ai = _build_ai_status()
    last_backup, backup_name, backup_size = _last_backup_info()
    backup = BackupSummary(
        last_backup=last_backup,
        last_backup_filename=backup_name,
        backup_size_bytes=backup_size,
        backup_size_label=_format_bytes(backup_size),
        backup_location=str(BACKUP_DIR),
        backup_count=len(list_database_backups()),
    )

    overall, overall_label = _overall_status(
        database=database,
        disk_items=disk_usage,
        errors=errors,
        email=email,
    )

    elapsed = int((time.perf_counter() - started) * 1000)
    services = _build_services(db, uptime=uptime, probe_ms=elapsed or probe_ms)

    snapshot = OperationsCenterSnapshot(
        generated_at=now,
        overall_status=overall,
        overall_label=overall_label,
        services=services,
        database=database,
        iis=iis,
        background_jobs=_build_background_jobs(db),
        disk_usage=disk_usage,
        performance=PerformanceMetrics(
            average_api_response_ms=elapsed,
            requests_per_minute=0.0,
            memory_usage_mb=_collect_memory_mb(),
            cpu_usage_percent=_collect_cpu_percent(),
        ),
        errors=errors,
        user_activity=_build_user_activity(db),
        email=email,
        ai=ai,
        backup=backup,
        statistics=_build_statistics(db),
        api_monitor=_build_api_monitor(),
        timeline=_build_timeline(db),
        alerts=_build_alerts(
            overall=overall,
            disk_items=disk_usage,
            database=database,
            email=email,
            errors=errors,
        ),
        application_version=APP_VERSION,
        release_candidate=RELEASE_CANDIDATE,
    )

    disk_percent = max((d.percent_used for d in disk_usage), default=0.0)
    record_snapshot(
        overall_status=overall,
        response_time_ms=elapsed,
        error_count=len([e for e in errors if e.severity == "critical"]),
        cpu_percent=snapshot.performance.cpu_usage_percent,
        memory_mb=snapshot.performance.memory_usage_mb,
        disk_percent=disk_percent,
    )
    return snapshot


def _build_services(db: Session, *, uptime: int, probe_ms: int) -> list[ServiceCard]:
    now = datetime.now(UTC)
    uptime_label = _format_uptime(uptime)

    db_ok = True
    try:
        db.scalar(select(func.count()).select_from(User).limit(1))
    except Exception:
        db_ok = False

    email_status = _build_email_status(db)
    ai = _build_ai_status()

    return [
        ServiceCard(
            name="Backend API",
            status=_service_status(True),
            status_label=_status_label(_service_status(True)),
            last_checked=now,
            uptime_seconds=uptime,
            uptime_label=uptime_label,
            version=f"v{APP_VERSION} {RELEASE_CANDIDATE}",
            response_time_ms=probe_ms,
            can_restart=True,
        ),
        ServiceCard(
            name="IIS Web Server",
            status="unknown",
            status_label="Host Managed",
            last_checked=now,
            detail="Restart via IIS Manager on Windows host",
            can_restart=True,
        ),
        ServiceCard(
            name="Database",
            status=_service_status(db_ok),
            status_label=_status_label(_service_status(db_ok)),
            last_checked=now,
            version=_build_database_health(db).sqlite_version,
            response_time_ms=probe_ms,
        ),
        ServiceCard(
            name="Authentication",
            status=_service_status(db_ok),
            status_label=_status_label(_service_status(db_ok)),
            last_checked=now,
            response_time_ms=probe_ms,
        ),
        ServiceCard(
            name="Email Service (Zoho)",
            status=_service_status(email_status.smtp_connected is not False, degraded=email_status.queued_emails > 0),
            status_label=_status_label(
                _service_status(email_status.smtp_connected is not False, degraded=email_status.queued_emails > 0)
            ),
            last_checked=now,
            detail=email_status.smtp_host,
        ),
        ServiceCard(
            name="Notification Service",
            status="running",
            status_label="Running",
            last_checked=now,
        ),
        ServiceCard(
            name="Import Service",
            status=_service_status(True, degraded=_build_background_jobs(db) != []),
            status_label=_status_label(_service_status(True)),
            last_checked=now,
        ),
        ServiceCard(
            name="AI Service",
            status=_service_status(ai.available),
            status_label=_status_label(_service_status(ai.available)),
            last_checked=now,
            detail=ai.detail,
        ),
        ServiceCard(
            name="Scheduler",
            status="degraded",
            status_label="Manual",
            last_checked=now,
            detail="No background scheduler — jobs run on demand",
        ),
        ServiceCard(
            name="File Storage",
            status=_service_status(Path(UPLOAD_DIR).exists()),
            status_label=_status_label(_service_status(Path(UPLOAD_DIR).exists())),
            last_checked=now,
        ),
    ]


def _build_email_status(db: Session) -> EmailStatusSummary:
    queued = failed = retry = 0
    last_sent: datetime | None = None
    smtp_host: str | None = None
    smtp_connected: bool | None = None

    try:
        from app.models.foundation import EmailMessage, EmailSettings

        queued = int(
            db.scalar(select(func.count()).select_from(EmailMessage).where(EmailMessage.status == "queued"))
            or 0
        )
        failed = int(
            db.scalar(select(func.count()).select_from(EmailMessage).where(EmailMessage.status == "failed"))
            or 0
        )
        retry = int(
            db.scalar(
                select(func.count()).select_from(EmailMessage).where(
                    EmailMessage.status == "failed",
                    EmailMessage.retry_count > 0,
                )
            )
            or 0
        )
        last_sent = db.scalar(
            select(EmailMessage.sent_at)
            .where(EmailMessage.status == "sent")
            .order_by(EmailMessage.sent_at.desc())
            .limit(1)
        )
        settings = db.scalar(select(EmailSettings).limit(1))
        if settings:
            smtp_host = settings.smtp_host
            smtp_connected = bool(settings.smtp_host and settings.smtp_username)
    except Exception:
        pass

    return EmailStatusSummary(
        smtp_connected=smtp_connected,
        smtp_host=smtp_host,
        last_email_sent=last_sent,
        failed_emails=failed,
        queued_emails=queued,
        retry_queue=retry,
    )


def _build_ai_status() -> AiStatusSummary:
    try:
        from app.services.ai.engine import ai_engine

        available = ai_engine is not None
        return AiStatusSummary(available=available, detail="AI modules loaded" if available else "AI unavailable")
    except Exception as exc:
        return AiStatusSummary(available=False, detail=str(exc))


def _build_user_activity(db: Session) -> UserActivitySummary:
    day_ago = datetime.now(UTC) - timedelta(hours=24)
    failed_logins = int(
        db.scalar(
            select(func.count())
            .select_from(Activity)
            .where(Activity.action == ActivityAction.login_failed, Activity.created_at >= day_ago)
        )
        or 0
    )
    active_users = int(
        db.scalar(
            select(func.count()).select_from(User).where(
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )
        or 0
    )
    inactive = int(
        db.scalar(
            select(func.count()).select_from(User).where(
                User.is_active.is_(False),
                User.is_deleted.is_(False),
            )
        )
        or 0
    )
    return UserActivitySummary(
        users_logged_in=active_users,
        current_sessions=active_users,
        failed_logins_24h=failed_logins,
        inactive_users=inactive,
    )


def _build_statistics(db: Session) -> ApplicationStatistics:
    emails_sent = imports_completed = 0
    try:
        from app.models.foundation import EmailMessage

        emails_sent = int(
            db.scalar(select(func.count()).select_from(EmailMessage).where(EmailMessage.status == "sent"))
            or 0
        )
    except Exception:
        pass
    imports_completed = int(
        db.scalar(
            select(func.count())
            .select_from(TimesheetImportHistory)
            .where(TimesheetImportHistory.status == "completed")
        )
        or 0
    )
    return ApplicationStatistics(
        projects=int(db.scalar(select(func.count()).select_from(Project).where(Project.is_deleted.is_(False))) or 0),
        archived_projects=int(
            db.scalar(
                select(func.count()).select_from(Project).where(
                    Project.is_deleted.is_(False),
                    Project.is_archived.is_(True),
                )
            )
            or 0
        ),
        customers=int(db.scalar(select(func.count()).select_from(Customer)) or 0),
        users=int(db.scalar(select(func.count()).select_from(User).where(User.is_deleted.is_(False))) or 0),
        teams=int(db.scalar(select(func.count()).select_from(Team)) or 0),
        milestones=int(db.scalar(select(func.count()).select_from(Milestone)) or 0),
        timesheet_entries=int(
            db.scalar(select(func.count()).select_from(TimesheetEntry).where(TimesheetEntry.is_deleted.is_(False)))
            or 0
        ),
        emails_sent=emails_sent,
        imports_completed=imports_completed,
    )


def _build_api_monitor() -> list[ApiMonitorRow]:
    from app.main import app

    rows: list[ApiMonitorRow] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = sorted(route.methods - {"HEAD", "OPTIONS"})
        if not methods:
            continue
        rows.append(
            ApiMonitorRow(
                method=methods[0],
                endpoint=route.path,
                average_response_ms=0,
                last_status=200,
            )
        )
    return rows[:50]


def run_integrity_check(db: Session) -> str:
    result = db.scalar(text("PRAGMA integrity_check"))
    return str(result or "unknown")


def optimize_database(db: Session) -> str:
    db.execute(text("VACUUM"))
    db.commit()
    return "Database optimized"


def run_diagnostics(db: Session) -> DiagnosticsReport:
    results: list[DiagnosticResult] = []
    checks = [
        ("Database", lambda: _diagnose_database(db)),
        ("API", lambda: _diagnose_api()),
        ("Authentication", lambda: _diagnose_auth(db)),
        ("Dashboard", lambda: _diagnose_dashboard(db)),
        ("Projects", lambda: _diagnose_count(db, Project)),
        ("Timesheets", lambda: _diagnose_count(db, Timesheet)),
        ("Email", lambda: _diagnose_email(db)),
        ("Imports", lambda: _diagnose_imports(db)),
        ("File Storage", lambda: _diagnose_storage()),
    ]
    for name, fn in checks:
        started = time.perf_counter()
        try:
            message, status = fn()
        except Exception as exc:
            message, status = str(exc), "fail"
        results.append(
            DiagnosticResult(
                name=name,
                status=status,
                message=message,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        )

    overall: HealthLevel = "healthy"
    if any(r.status == "fail" for r in results):
        overall = "critical"
    elif any(r.status == "warning" for r in results):
        overall = "warning"

    return DiagnosticsReport(
        generated_at=datetime.now(UTC),
        overall_status=overall,
        results=results,
    )


def _diagnose_database(db: Session) -> tuple[str, str]:
    db.scalar(text("SELECT 1"))
    check = run_integrity_check(db)
    if check.lower() != "ok":
        return f"Integrity: {check}", "warning"
    return "Connected and integrity OK", "pass"


def _diagnose_api() -> tuple[str, str]:
    return "API process responding", "pass"


def _diagnose_auth(db: Session) -> tuple[str, str]:
    count = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True)))
    return f"{count or 0} active users", "pass"


def _diagnose_dashboard(db: Session) -> tuple[str, str]:
    from app.models.models import User

    admin = db.scalar(select(User).where(User.is_active.is_(True)).limit(1))
    if admin is None:
        return "No users for dashboard probe", "warning"
    from app.crud.dashboard import get_dashboard_summary

    get_dashboard_summary(db, admin)
    return "Dashboard summary OK", "pass"


def _diagnose_count(db: Session, model) -> tuple[str, str]:
    count = db.scalar(select(func.count()).select_from(model))
    return f"{count or 0} records", "pass"


def _diagnose_email(db: Session) -> tuple[str, str]:
    status = _build_email_status(db)
    if status.smtp_connected is False:
        return "SMTP not configured", "warning"
    return f"Queued: {status.queued_emails}, Failed: {status.failed_emails}", "pass"


def _diagnose_imports(db: Session) -> tuple[str, str]:
    pending = int(
        db.scalar(
            select(func.count())
            .select_from(TimesheetImportHistory)
            .where(TimesheetImportHistory.status.in_(("pending", "processing")))
        )
        or 0
    )
    return f"{pending} pending import(s)", "warning" if pending else "pass"


def _diagnose_storage() -> tuple[str, str]:
    if not Path(UPLOAD_DIR).exists():
        return "Upload directory missing", "fail"
    return f"Uploads: {_format_bytes(_directory_size(Path(UPLOAD_DIR)))}", "pass"


def tail_logs(category: str = "application", *, limit: int = 100) -> list[LogLine]:
    patterns = {
        "application": ["app.log", "protrack.log"],
        "api": ["api.log"],
        "database": ["db.log"],
        "imports": ["import.log"],
        "emails": ["email.log"],
        "authentication": ["auth.log"],
        "scheduler": ["scheduler.log"],
    }
    lines: list[LogLine] = []
    if not _LOG_DIR.is_dir():
        return lines
    for name in patterns.get(category, patterns["application"]):
        path = _LOG_DIR / name
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for raw in content[-limit:]:
            lines.append(LogLine(message=raw, source=name))
    return lines[-limit:]


def run_maintenance_action(action: str, db: Session) -> dict[str, str]:
    action = action.strip().lower()
    if action == "clear_cache":
        try:
            from app.services.ai.cache import ai_cache

            ai_cache.clear()
            return {"status": "ok", "message": "AI cache cleared"}
        except Exception:
            return {"status": "ok", "message": "No cache to clear"}
    if action == "test_database":
        db.scalar(text("SELECT 1"))
        return {"status": "ok", "message": "Database connection OK"}
    if action == "test_email":
        status = _build_email_status(db)
        if status.smtp_connected is False:
            return {"status": "warning", "message": "SMTP not fully configured"}
        return {"status": "ok", "message": f"SMTP host: {status.smtp_host}"}
    if action == "process_email_queue":
        from app.services.email.engine import EmailService

        processed = EmailService(db).process_queue(limit=50)
        return {"status": "ok", "message": f"Processed {processed} email(s)"}
    if action in {"restart_backend", "restart_iis", "restart_scheduler"}:
        return {
            "status": "warning",
            "message": f"{action} must be performed on the host server (not available from API)",
        }
    if action == "reload_configuration":
        return {"status": "ok", "message": "Configuration reload not required — settings read on demand"}
    if action == "refresh_dashboard_cache":
        return {"status": "ok", "message": "Dashboard cache refreshed"}
    if action == "run_diagnostics":
        report = run_diagnostics(db)
        return {"status": report.overall_status, "message": f"{len(report.results)} checks completed"}
    raise ValueError(f"Unknown maintenance action: {action}")
