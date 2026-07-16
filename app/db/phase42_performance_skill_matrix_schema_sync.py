"""Phase 42 — user stream profile + stream skill matrix tables."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
    return row is not None


def ensure_phase42_performance_skill_matrix_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "users", "stream_id"):
                connection.execute(text("ALTER TABLE users ADD COLUMN stream_id CHAR(36) NULL"))
            if not _sqlite_has_column(engine, "users", "primary_tool"):
                connection.execute(text("ALTER TABLE users ADD COLUMN primary_tool VARCHAR(80) NULL"))
            if not _sqlite_has_column(engine, "users", "work_function"):
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN work_function VARCHAR(120) NULL")
                )
            if not _sqlite_has_table(engine, "stream_skills"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE stream_skills (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            stream_id CHAR(36) NOT NULL,
                            name VARCHAR(120) NOT NULL,
                            sort_order INTEGER NOT NULL DEFAULT 0,
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            created_at DATETIME,
                            updated_at DATETIME,
                            UNIQUE (stream_id, name),
                            FOREIGN KEY(stream_id) REFERENCES streams (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
            if not _sqlite_has_table(engine, "user_skill_ratings"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE user_skill_ratings (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            user_id CHAR(36) NOT NULL,
                            stream_skill_id CHAR(36) NOT NULL,
                            proficiency VARCHAR(20) NOT NULL DEFAULT 'learning',
                            assessed_by_id CHAR(36) NULL,
                            assessed_at DATETIME NULL,
                            notes TEXT NULL,
                            created_at DATETIME,
                            updated_at DATETIME,
                            UNIQUE (user_id, stream_skill_id),
                            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                            FOREIGN KEY(stream_skill_id) REFERENCES stream_skills (id) ON DELETE CASCADE,
                            FOREIGN KEY(assessed_by_id) REFERENCES users (id)
                        )
                        """
                    )
                )
            return

        connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS stream_id UUID NULL")
        )
        connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_tool VARCHAR(80) NULL")
        )
        connection.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS work_function VARCHAR(120) NULL")
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stream_skills (
                    id UUID PRIMARY KEY,
                    stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
                    name VARCHAR(120) NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE (stream_id, name)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_skill_ratings (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    stream_skill_id UUID NOT NULL REFERENCES stream_skills(id) ON DELETE CASCADE,
                    proficiency VARCHAR(20) NOT NULL DEFAULT 'learning',
                    assessed_by_id UUID NULL REFERENCES users(id),
                    assessed_at TIMESTAMP NULL,
                    notes TEXT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    UNIQUE (user_id, stream_skill_id)
                )
                """
            )
        )
