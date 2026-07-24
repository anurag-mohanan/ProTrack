"""Phase 59 — R4 enterprise: QA gate columns, legal entities, documents, learning plans."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _table_exists(engine: Engine, table_name: str) -> bool:
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
                {"n": table_name},
            ).fetchone()
        return row is not None
    with engine.connect() as connection:
        row = connection.execute(text("SELECT to_regclass(:n)"), {"n": table_name}).fetchone()
    return bool(row and row[0])


def _add_column_sqlite(connection, engine: Engine, table: str, column: str, ddl: str) -> None:
    if _table_exists(engine, table) and not _sqlite_has_column(engine, table, column):
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


_LEGAL_ENTITIES_SQLITE = """
CREATE TABLE IF NOT EXISTS legal_entities (
    id CHAR(36) NOT NULL PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
    is_default BOOLEAN NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME
)
"""

_DOCUMENT_ASSETS_SQLITE = """
CREATE TABLE IF NOT EXISTS document_assets (
    id CHAR(36) NOT NULL PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    entity_id CHAR(36) NOT NULL,
    title VARCHAR(255),
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(120),
    size_bytes INTEGER NOT NULL DEFAULT 0,
    storage_backend VARCHAR(32) NOT NULL DEFAULT 'local',
    storage_key VARCHAR(500) NOT NULL,
    checksum VARCHAR(128),
    uploaded_by_id CHAR(36),
    notes TEXT,
    created_at DATETIME,
    updated_at DATETIME
)
"""

_LEARNING_PLANS_SQLITE = """
CREATE TABLE IF NOT EXISTS learning_plans (
    id CHAR(36) NOT NULL PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    title VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_by_id CHAR(36),
    created_at DATETIME,
    updated_at DATETIME
)
"""

_LEARNING_ITEMS_SQLITE = """
CREATE TABLE IF NOT EXISTS learning_plan_items (
    id CHAR(36) NOT NULL PRIMARY KEY,
    plan_id CHAR(36) NOT NULL,
    stream_skill_id CHAR(36) NOT NULL,
    current_proficiency VARCHAR(32),
    target_proficiency VARCHAR(32) NOT NULL DEFAULT 'proficient',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    due_date DATE,
    notes TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME
)
"""

_LEGAL_ENTITIES_PG = """
CREATE TABLE IF NOT EXISTS legal_entities (
    id UUID PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

_DOCUMENT_ASSETS_PG = """
CREATE TABLE IF NOT EXISTS document_assets (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL,
    entity_id UUID NOT NULL,
    title VARCHAR(255),
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(120),
    size_bytes INTEGER NOT NULL DEFAULT 0,
    storage_backend VARCHAR(32) NOT NULL DEFAULT 'local',
    storage_key VARCHAR(500) NOT NULL,
    checksum VARCHAR(128),
    uploaded_by_id UUID,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

_LEARNING_PLANS_PG = """
CREATE TABLE IF NOT EXISTS learning_plans (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    title VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_by_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

_LEARNING_ITEMS_PG = """
CREATE TABLE IF NOT EXISTS learning_plan_items (
    id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES learning_plans(id) ON DELETE CASCADE,
    stream_skill_id UUID NOT NULL,
    current_proficiency VARCHAR(32),
    target_proficiency VARCHAR(32) NOT NULL DEFAULT 'proficient',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    due_date DATE,
    notes TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""


def ensure_phase59_r4_enterprise_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            connection.execute(text(_LEGAL_ENTITIES_SQLITE))
            connection.execute(text(_DOCUMENT_ASSETS_SQLITE))
            connection.execute(text(_LEARNING_PLANS_SQLITE))
            connection.execute(text(_LEARNING_ITEMS_SQLITE))
            _add_column_sqlite(
                connection, engine, "projects", "qa_gate_enabled", "BOOLEAN NOT NULL DEFAULT 0"
            )
            _add_column_sqlite(
                connection,
                engine,
                "milestones",
                "qa_acknowledged",
                "BOOLEAN NOT NULL DEFAULT 0",
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_assets_entity "
                    "ON document_assets (entity_type, entity_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_learning_plans_user "
                    "ON learning_plans (user_id)"
                )
            )
        elif dialect == "postgresql":
            connection.execute(text(_LEGAL_ENTITIES_PG))
            connection.execute(text(_DOCUMENT_ASSETS_PG))
            connection.execute(text(_LEARNING_PLANS_PG))
            connection.execute(text(_LEARNING_ITEMS_PG))
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS "
                    "qa_gate_enabled BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE milestones ADD COLUMN IF NOT EXISTS "
                    "qa_acknowledged BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_assets_entity "
                    "ON document_assets (entity_type, entity_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_learning_plans_user "
                    "ON learning_plans (user_id)"
                )
            )
