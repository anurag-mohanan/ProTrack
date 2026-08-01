"""Phase 69 — commercial tenants + feature flags (R10 spine)."""

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


_SQLITE_TENANTS = """
CREATE TABLE IF NOT EXISTS tenants (
    id CHAR(36) NOT NULL PRIMARY KEY,
    slug VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    edition VARCHAR(32) NOT NULL DEFAULT 'enterprise',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    terminology_json TEXT,
    numbering_policy_json TEXT,
    notes TEXT,
    created_at DATETIME,
    updated_at DATETIME
)
"""

_SQLITE_FLAGS = """
CREATE TABLE IF NOT EXISTS feature_flags (
    id CHAR(36) NOT NULL PRIMARY KEY,
    tenant_id CHAR(36) NOT NULL,
    key VARCHAR(80) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT 0,
    description VARCHAR(255),
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
    UNIQUE (tenant_id, key)
)
"""

_PG_TENANTS = """
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY,
    slug VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    edition VARCHAR(32) NOT NULL DEFAULT 'enterprise',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    terminology_json TEXT,
    numbering_policy_json TEXT,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE
)
"""

_PG_FLAGS = """
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    key VARCHAR(80) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    description VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT uq_feature_flag_tenant_key UNIQUE (tenant_id, key)
)
"""


def ensure_phase69_commercial_tenancy_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "tenants"):
                connection.execute(text(_SQLITE_TENANTS))
            if not _sqlite_has_table(engine, "feature_flags"):
                connection.execute(text(_SQLITE_FLAGS))
        else:
            connection.execute(text(_PG_TENANTS))
            connection.execute(text(_PG_FLAGS))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_feature_flags_tenant_id "
                    "ON feature_flags (tenant_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_feature_flags_key "
                    "ON feature_flags (key)"
                )
            )
