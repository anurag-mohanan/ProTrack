"""Phase 57 — R1 background_jobs durable queue table.

Idempotent for SQLite and PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
    return row is not None


_SQLITE = """
CREATE TABLE IF NOT EXISTS background_jobs (
    id CHAR(36) NOT NULL PRIMARY KEY,
    job_type VARCHAR(80) NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    run_after DATETIME NOT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    last_error TEXT NULL,
    created_at DATETIME,
    updated_at DATETIME
)
"""

_PG = """
CREATE TABLE IF NOT EXISTS background_jobs (
    id UUID PRIMARY KEY,
    job_type VARCHAR(80) NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    run_after TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""


def ensure_phase57_background_jobs_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "background_jobs"):
                connection.execute(text(_SQLITE))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_background_jobs_status "
                    "ON background_jobs (status)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_background_jobs_job_type "
                    "ON background_jobs (job_type)"
                )
            )
        elif dialect == "postgresql":
            connection.execute(text(_PG))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_background_jobs_status "
                    "ON background_jobs (status)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_background_jobs_job_type "
                    "ON background_jobs (job_type)"
                )
            )
