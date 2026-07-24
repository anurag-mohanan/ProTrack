"""Database backup and restore helpers (SQLite + Postgres)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

from app.core.config import BASE_DIR
from app.db.session import DATABASE_URL

BACKUP_DIR = BASE_DIR / "Backups"


def _is_sqlite() -> bool:
    return DATABASE_URL.startswith("sqlite")


def _is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")


def _sqlite_path() -> Path:
    if not _is_sqlite():
        raise ValueError("SQLite path requested but DATABASE_URL is not SQLite.")
    raw = DATABASE_URL.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        path = BASE_DIR / raw
    return path


def _parse_postgres_url() -> dict[str, str]:
    # postgresql+psycopg2://user:pass@host:port/db
    normalized = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError("Not a PostgreSQL DATABASE_URL.")
    return {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": (parsed.path or "/protrack").lstrip("/") or "protrack",
    }


def create_database_backup() -> dict[str, str]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    if _is_sqlite():
        source = _sqlite_path()
        if not source.is_file():
            raise FileNotFoundError(f"Database file not found: {source}")
        destination = BACKUP_DIR / f"protrack_backup_{timestamp}.db"
        shutil.copy2(source, destination)
        return {
            "filename": destination.name,
            "path": str(destination),
            "created_at": datetime.now().isoformat(),
            "engine": "sqlite",
        }

    if _is_postgres():
        cfg = _parse_postgres_url()
        destination = BACKUP_DIR / f"protrack_backup_{timestamp}.dump"
        env = os.environ.copy()
        if cfg["password"]:
            env["PGPASSWORD"] = cfg["password"]
        cmd = [
            "pg_dump",
            "-Fc",
            "-h",
            cfg["host"],
            "-p",
            cfg["port"],
            "-U",
            cfg["user"],
            "-d",
            cfg["dbname"],
            "-f",
            str(destination),
        ]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "pg_dump failed")
        return {
            "filename": destination.name,
            "path": str(destination),
            "created_at": datetime.now().isoformat(),
            "engine": "postgresql",
        }

    raise ValueError("Automated backup supports SQLite and PostgreSQL only.")


def list_database_backups() -> list[dict[str, str]]:
    if not BACKUP_DIR.is_dir():
        return []
    backups = []
    patterns = ("protrack_backup_*.db", "protrack_backup_*.dump")
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(BACKUP_DIR.glob(pattern))
    for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
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

    if _is_sqlite():
        if not filename.endswith(".db"):
            raise ValueError("SQLite restore requires a .db backup file.")
        target = _sqlite_path()
        pre_restore = BACKUP_DIR / f"pre_restore_{datetime.now().strftime('%Y-%m-%d_%H%M')}.db"
        if target.is_file():
            shutil.copy2(target, pre_restore)
        shutil.copy2(source, target)
        return {
            "restored_from": filename,
            "safety_copy": pre_restore.name if pre_restore.is_file() else "",
            "engine": "sqlite",
        }

    if _is_postgres():
        if not filename.endswith(".dump"):
            raise ValueError("PostgreSQL restore requires a .dump (pg_dump -Fc) file.")
        cfg = _parse_postgres_url()
        env = os.environ.copy()
        if cfg["password"]:
            env["PGPASSWORD"] = cfg["password"]
        cmd = [
            "pg_restore",
            "--clean",
            "--if-exists",
            "-h",
            cfg["host"],
            "-p",
            cfg["port"],
            "-U",
            cfg["user"],
            "-d",
            cfg["dbname"],
            str(source),
        ]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        # pg_restore often exits 1 with warnings; treat only hard failures
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr.strip() or "pg_restore failed")
        return {
            "restored_from": filename,
            "safety_copy": "",
            "engine": "postgresql",
        }

    raise ValueError("Automated restore supports SQLite and PostgreSQL only.")
