"""Reset all timesheet data before a historical re-import."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.db.session import DATABASE_URL
from app.models.models import (
    Project,
    Timesheet,
    TimesheetEntry,
    TimesheetEntryDeletionLog,
    TimesheetImportHistory,
)
from app.services.project_calculation_service import recalculate_project


@dataclass
class TimesheetResetResult:
    backup_path: Path
    timesheets_deleted: int
    entries_deleted: int
    import_history_deleted: int
    deletion_logs_deleted: int


def resolve_sqlite_db_path() -> Path:
    """Resolve the active SQLite database file path."""
    candidates: list[Path] = []
    configured = Path("database/protrack.db")
    if configured.is_file():
        candidates.append(configured)

    database_url = os.getenv("DATABASE_URL", DATABASE_URL)
    if database_url.startswith("sqlite"):
        url_path = Path(database_url.removeprefix("sqlite:///"))
        if url_path.is_file():
            candidates.append(url_path)

    root_db = Path("protrack.db")
    if root_db.is_file():
        candidates.append(root_db)

    if not candidates:
        raise FileNotFoundError(
            "SQLite database file not found. Expected database/protrack.db or protrack.db."
        )
    return candidates[0]


def create_reimport_backup() -> Path:
    """Copy the SQLite database to backups/Before_Historical_Reimport_YYYYMMDD_HHMM.db."""
    source = resolve_sqlite_db_path()
    backup_root = Path("backups")
    backup_root.mkdir(parents=True, exist_ok=True)
    dest = backup_root / f"Before_Historical_Reimport_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    shutil.copy2(source, dest)
    return dest


def timesheet_tables_are_empty(db: Session) -> bool:
    entry_count = db.scalar(select(func.count()).select_from(TimesheetEntry)) or 0
    timesheet_count = db.scalar(select(func.count()).select_from(Timesheet)) or 0
    return entry_count == 0 and timesheet_count == 0


def delete_all_timesheet_data(db: Session) -> TimesheetResetResult:
    """Hard-delete all timesheet rows and related audit/history, then recalculate projects."""
    backup_path = create_reimport_backup()

    entries_deleted = db.scalar(select(func.count()).select_from(TimesheetEntry)) or 0
    timesheets_deleted = db.scalar(select(func.count()).select_from(Timesheet)) or 0
    import_history_deleted = (
        db.scalar(select(func.count()).select_from(TimesheetImportHistory)) or 0
    )
    deletion_logs_deleted = (
        db.scalar(select(func.count()).select_from(TimesheetEntryDeletionLog)) or 0
    )

    db.execute(delete(TimesheetEntry))
    db.execute(delete(Timesheet))
    db.execute(delete(TimesheetEntryDeletionLog))
    db.execute(delete(TimesheetImportHistory))
    db.commit()

    if DATABASE_URL.startswith("sqlite"):
        sequence_exists = db.scalar(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='sqlite_sequence'"
            )
        )
        if sequence_exists:
            db.execute(
                text(
                    "DELETE FROM sqlite_sequence "
                    "WHERE name IN ('timesheets', 'timesheet_entries')"
                )
            )
            db.commit()

    for project_id in db.scalars(select(Project.id)):
        recalculate_project(db, project_id)

    return TimesheetResetResult(
        backup_path=backup_path,
        timesheets_deleted=timesheets_deleted,
        entries_deleted=entries_deleted,
        import_history_deleted=import_history_deleted,
        deletion_logs_deleted=deletion_logs_deleted,
    )
