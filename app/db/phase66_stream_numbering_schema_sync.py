"""Phase 66 — optional stream project prefix and numbering system."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase66_stream_numbering_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "streams", "use_project_prefix"):
                connection.execute(
                    text(
                        "ALTER TABLE streams "
                        "ADD COLUMN use_project_prefix BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if not _sqlite_has_column(engine, "streams", "use_project_numbering"):
                connection.execute(
                    text(
                        "ALTER TABLE streams "
                        "ADD COLUMN use_project_numbering BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if not _sqlite_has_column(engine, "streams", "project_number_prefix"):
                connection.execute(
                    text("ALTER TABLE streams ADD COLUMN project_number_prefix VARCHAR(50)")
                )
            if not _sqlite_has_column(engine, "streams", "project_number_format"):
                connection.execute(
                    text("ALTER TABLE streams ADD COLUMN project_number_format VARCHAR(100)")
                )
            if not _sqlite_has_column(engine, "streams", "next_project_sequence"):
                connection.execute(
                    text(
                        "ALTER TABLE streams "
                        "ADD COLUMN next_project_sequence INTEGER NOT NULL DEFAULT 1"
                    )
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE streams "
                    "ADD COLUMN IF NOT EXISTS use_project_prefix BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE streams "
                    "ADD COLUMN IF NOT EXISTS use_project_numbering BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE streams "
                    "ADD COLUMN IF NOT EXISTS project_number_prefix VARCHAR(50)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE streams "
                    "ADD COLUMN IF NOT EXISTS project_number_format VARCHAR(100)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE streams "
                    "ADD COLUMN IF NOT EXISTS next_project_sequence INTEGER NOT NULL DEFAULT 1"
                )
            )
