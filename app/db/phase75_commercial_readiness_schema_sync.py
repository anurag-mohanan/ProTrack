"""Phase 75 — commercial readiness tables + require_sso_for_admins column."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.models.commercial import PROSOHM_TENANT_ID

_PROSOHM_SQLITE = PROSOHM_TENANT_ID.hex
_PROSOHM = str(PROSOHM_TENANT_ID)


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


_SQLITE_TABLES = (
    """
CREATE TABLE IF NOT EXISTS commercial_signoffs (
    id CHAR(36) NOT NULL PRIMARY KEY,
    key VARCHAR(80) NOT NULL,
    signer_name VARCHAR(200) NOT NULL,
    signer_role VARCHAR(80) NOT NULL,
    signed_at DATETIME NOT NULL,
    notes TEXT,
    evidence_url VARCHAR(500),
    created_at DATETIME,
    updated_at DATETIME,
    tenant_id CHAR(36) NOT NULL DEFAULT '{prosohm}'
)
""".format(prosohm=_PROSOHM_SQLITE),
    """
CREATE TABLE IF NOT EXISTS design_partners (
    id CHAR(36) NOT NULL PRIMARY KEY,
    icp VARCHAR(32) NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    contact_name VARCHAR(200),
    contact_email VARCHAR(255),
    loi_doc_ref VARCHAR(255),
    loi_sent_at DATETIME,
    loi_signed_at DATETIME,
    notes TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    tenant_id CHAR(36) NOT NULL DEFAULT '{prosohm}'
)
""".format(prosohm=_PROSOHM_SQLITE),
    """
CREATE TABLE IF NOT EXISTS trust_control_checks (
    id CHAR(36) NOT NULL PRIMARY KEY,
    control_id VARCHAR(16) NOT NULL,
    title VARCHAR(200) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'med',
    must_fix BOOLEAN NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    owner VARCHAR(120),
    evidence_notes TEXT,
    doc_path VARCHAR(255),
    completed_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME,
    tenant_id CHAR(36) NOT NULL DEFAULT '{prosohm}'
)
""".format(prosohm=_PROSOHM_SQLITE),
)

_PG_TABLES = (
    """
CREATE TABLE IF NOT EXISTS commercial_signoffs (
    id UUID PRIMARY KEY,
    key VARCHAR(80) NOT NULL,
    signer_name VARCHAR(200) NOT NULL,
    signer_role VARCHAR(80) NOT NULL,
    signed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    notes TEXT,
    evidence_url VARCHAR(500),
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    tenant_id UUID NOT NULL DEFAULT '{prosohm}'::uuid
)
""".format(prosohm=_PROSOHM),
    """
CREATE TABLE IF NOT EXISTS design_partners (
    id UUID PRIMARY KEY,
    icp VARCHAR(32) NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    contact_name VARCHAR(200),
    contact_email VARCHAR(255),
    loi_doc_ref VARCHAR(255),
    loi_sent_at TIMESTAMP WITHOUT TIME ZONE,
    loi_signed_at TIMESTAMP WITHOUT TIME ZONE,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    tenant_id UUID NOT NULL DEFAULT '{prosohm}'::uuid
)
""".format(prosohm=_PROSOHM),
    """
CREATE TABLE IF NOT EXISTS trust_control_checks (
    id UUID PRIMARY KEY,
    control_id VARCHAR(16) NOT NULL,
    title VARCHAR(200) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'med',
    must_fix BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    owner VARCHAR(120),
    evidence_notes TEXT,
    doc_path VARCHAR(255),
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    tenant_id UUID NOT NULL DEFAULT '{prosohm}'::uuid
)
""".format(prosohm=_PROSOHM),
)


def ensure_phase75_commercial_readiness_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            for ddl in _SQLITE_TABLES:
                connection.execute(text(ddl))
            if _sqlite_has_column(engine, "security_policy_settings", "id") and not _sqlite_has_column(
                engine, "security_policy_settings", "require_sso_for_admins"
            ):
                connection.execute(
                    text(
                        "ALTER TABLE security_policy_settings "
                        "ADD COLUMN require_sso_for_admins BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_commercial_signoffs_tenant_key "
                    "ON commercial_signoffs (tenant_id, key)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_trust_control_tenant_id "
                    "ON trust_control_checks (tenant_id, control_id)"
                )
            )
        else:
            for ddl in _PG_TABLES:
                connection.execute(text(ddl))
            connection.execute(
                text(
                    "ALTER TABLE security_policy_settings "
                    "ADD COLUMN IF NOT EXISTS require_sso_for_admins "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            try:
                connection.execute(
                    text(
                        "ALTER TABLE commercial_signoffs "
                        "ADD CONSTRAINT uq_commercial_signoffs_tenant_key "
                        "UNIQUE (tenant_id, key)"
                    )
                )
            except Exception:
                pass
            try:
                connection.execute(
                    text(
                        "ALTER TABLE trust_control_checks "
                        "ADD CONSTRAINT uq_trust_control_tenant_id "
                        "UNIQUE (tenant_id, control_id)"
                    )
                )
            except Exception:
                pass
