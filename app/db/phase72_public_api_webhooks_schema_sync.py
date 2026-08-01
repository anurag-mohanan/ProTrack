"""Phase 72 — public API keys + webhook tables (R10 draft)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.models.commercial import PROSOHM_TENANT_ID

_PROSOHM = str(PROSOHM_TENANT_ID)
_PROSOHM_SQLITE = PROSOHM_TENANT_ID.hex

_TABLES = (
    """
CREATE TABLE IF NOT EXISTS api_keys (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    key_prefix VARCHAR(24) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    scopes_json TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    last_used_at DATETIME,
    created_by_id CHAR(36),
    notes VARCHAR(255),
    created_at DATETIME,
    updated_at DATETIME,
    tenant_id CHAR(36) NOT NULL DEFAULT '{prosohm}'
)
""".format(
        prosohm=_PROSOHM_SQLITE
    ),
    """
CREATE TABLE IF NOT EXISTS webhook_endpoints (
    id CHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(120) NOT NULL,
    events_json TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    description VARCHAR(255),
    created_at DATETIME,
    updated_at DATETIME,
    tenant_id CHAR(36) NOT NULL DEFAULT '{prosohm}'
)
""".format(
        prosohm=_PROSOHM_SQLITE
    ),
    """
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id CHAR(36) NOT NULL PRIMARY KEY,
    endpoint_id CHAR(36) NOT NULL,
    event VARCHAR(80) NOT NULL,
    payload_json TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    http_status INTEGER,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    delivered_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME,
    tenant_id CHAR(36) NOT NULL DEFAULT '{prosohm}'
)
""".format(
        prosohm=_PROSOHM_SQLITE
    ),
)

_PG = (
    """
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    key_prefix VARCHAR(24) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    scopes_json TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMP WITHOUT TIME ZONE,
    created_by_id UUID,
    notes VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    tenant_id UUID NOT NULL DEFAULT '{prosohm}'::uuid
)
""".format(
        prosohm=_PROSOHM
    ),
    """
CREATE TABLE IF NOT EXISTS webhook_endpoints (
    id UUID PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(120) NOT NULL,
    events_json TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    description VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    tenant_id UUID NOT NULL DEFAULT '{prosohm}'::uuid
)
""".format(
        prosohm=_PROSOHM
    ),
    """
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY,
    endpoint_id UUID NOT NULL REFERENCES webhook_endpoints (id) ON DELETE CASCADE,
    event VARCHAR(80) NOT NULL,
    payload_json TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    http_status INTEGER,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    delivered_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    tenant_id UUID NOT NULL DEFAULT '{prosohm}'::uuid
)
""".format(
        prosohm=_PROSOHM
    ),
)


def ensure_phase72_public_api_webhooks_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            for ddl in _TABLES:
                connection.execute(text(ddl))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id ON api_keys (tenant_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_webhook_endpoints_tenant_id "
                    "ON webhook_endpoints (tenant_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_endpoint_id "
                    "ON webhook_deliveries (endpoint_id)"
                )
            )
        else:
            for ddl in _PG:
                connection.execute(text(ddl))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id ON api_keys (tenant_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_webhook_endpoints_tenant_id "
                    "ON webhook_endpoints (tenant_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_endpoint_id "
                    "ON webhook_deliveries (endpoint_id)"
                )
            )
            try:
                connection.execute(
                    text(
                        "ALTER TABLE api_keys "
                        "ADD CONSTRAINT uq_api_keys_tenant_prefix "
                        "UNIQUE (tenant_id, key_prefix)"
                    )
                )
            except Exception:
                pass
