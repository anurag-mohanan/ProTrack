"""Database backup and restore helpers."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import BASE_DIR
from app.db.session import DATABASE_URL

BACKUP_DIR = BASE_DIR / "Backups"


def _sqlite_path() -> Path:
    if not DATABASE_URL.startswith("sqlite"):
        raise ValueError("Automated backup is only supported for SQLite databases.")
    raw = DATABASE_URL.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / raw
    return path


def create_database_backup() -> dict[str, str]:
    source = _sqlite_path()
    if not source.is_file():
        raise FileNotFoundError(f"Database file not found: {source}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    destination = BACKUP_DIR / f"protrack_backup_{timestamp}.db"
    shutil.copy2(source, destination)
    return {
        "filename": destination.name,
        "path": str(destination),
        "created_at": datetime.now().isoformat(),
    }


def list_database_backups() -> list[dict[str, str]]:
    if not BACKUP_DIR.is_dir():
        return []
    backups = []
    for path in sorted(BACKUP_DIR.glob("protrack_backup_*.db"), reverse=True):
        backups.append(
            {
                "filename": path.name,
                "path": str(path),
                "size_bytes": str(path.stat().st_size),
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            }
        )
    return backups


def restore_database_backup(filename: str) -> dict[str, str]:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Invalid backup filename.")
    source = BACKUP_DIR / filename
    if not source.is_file():
        raise FileNotFoundError("Backup file not found.")

    target = _sqlite_path()
    pre_restore = BACKUP_DIR / f"pre_restore_{datetime.now().strftime('%Y-%m-%d_%H%M')}.db"
    if target.is_file():
        shutil.copy2(target, pre_restore)
    shutil.copy2(source, target)
    return {
        "restored_from": filename,
        "safety_copy": pre_restore.name if pre_restore.is_file() else "",
    }
