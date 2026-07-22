"""Phase 54 — Onboarding checklists (PP-HRD-FO-14).

Creates ``onboarding_checklist_templates``, ``onboarding_checklists``, and
``onboarding_checklist_items``. Seeds the company form PP-HRD-FO-14 from the
existing Excel onboarding checklist. Idempotent for SQLite and PostgreSQL.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.onboarding_checklist_service import (
    FORM_CODE,
    FORM_TITLE,
    PP_HRD_FO_14_STRUCTURE,
)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
    return row is not None


_SQLITE_TEMPLATES = """
CREATE TABLE IF NOT EXISTS onboarding_checklist_templates (
    id CHAR(36) NOT NULL PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    structure_json TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME
)
"""

_SQLITE_CHECKLISTS = """
CREATE TABLE IF NOT EXISTS onboarding_checklists (
    id CHAR(36) NOT NULL PRIMARY KEY,
    template_id CHAR(36) NULL,
    employee_user_id CHAR(36) NULL,
    employee_name VARCHAR(200) NOT NULL,
    employee_code VARCHAR(40) NULL,
    joining_date DATE NULL,
    designation VARCHAR(120) NULL,
    department_name VARCHAR(120) NULL,
    org_department_id CHAR(36) NULL,
    team_id CHAR(36) NULL,
    team_name VARCHAR(120) NULL,
    role_id CHAR(36) NULL,
    role_name VARCHAR(120) NULL,
    reporting_manager_id CHAR(36) NULL,
    reporting_manager_name VARCHAR(200) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    notes TEXT NULL,
    created_by_id CHAR(36) NULL,
    completed_at DATETIME NULL,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(template_id) REFERENCES onboarding_checklist_templates (id),
    FOREIGN KEY(employee_user_id) REFERENCES users (id),
    FOREIGN KEY(org_department_id) REFERENCES org_departments (id),
    FOREIGN KEY(team_id) REFERENCES teams (id),
    FOREIGN KEY(role_id) REFERENCES roles (id),
    FOREIGN KEY(reporting_manager_id) REFERENCES users (id),
    FOREIGN KEY(created_by_id) REFERENCES users (id)
)
"""

_SQLITE_ITEMS = """
CREATE TABLE IF NOT EXISTS onboarding_checklist_items (
    id CHAR(36) NOT NULL PRIMARY KEY,
    checklist_id CHAR(36) NOT NULL,
    section VARCHAR(80) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    item_text VARCHAR(500) NOT NULL,
    responsibility VARCHAR(40) NOT NULL DEFAULT 'hr',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    owner_user_id CHAR(36) NULL,
    help_ticket_id CHAR(36) NULL,
    completed_by_id CHAR(36) NULL,
    completion_date DATE NULL,
    notes TEXT NULL,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(checklist_id) REFERENCES onboarding_checklists (id),
    FOREIGN KEY(owner_user_id) REFERENCES users (id),
    FOREIGN KEY(help_ticket_id) REFERENCES tickets (id),
    FOREIGN KEY(completed_by_id) REFERENCES users (id)
)
"""

_PG_TEMPLATES = """
CREATE TABLE IF NOT EXISTS onboarding_checklist_templates (
    id UUID PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    structure_json TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""

_PG_CHECKLISTS = """
CREATE TABLE IF NOT EXISTS onboarding_checklists (
    id UUID PRIMARY KEY,
    template_id UUID NULL REFERENCES onboarding_checklist_templates(id),
    employee_user_id UUID NULL REFERENCES users(id),
    employee_name VARCHAR(200) NOT NULL,
    employee_code VARCHAR(40) NULL,
    joining_date DATE NULL,
    designation VARCHAR(120) NULL,
    department_name VARCHAR(120) NULL,
    org_department_id UUID NULL REFERENCES org_departments(id),
    team_id UUID NULL REFERENCES teams(id),
    team_name VARCHAR(120) NULL,
    role_id UUID NULL REFERENCES roles(id),
    role_name VARCHAR(120) NULL,
    reporting_manager_id UUID NULL REFERENCES users(id),
    reporting_manager_name VARCHAR(200) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    notes TEXT NULL,
    created_by_id UUID NULL REFERENCES users(id),
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""

_PG_ITEMS = """
CREATE TABLE IF NOT EXISTS onboarding_checklist_items (
    id UUID PRIMARY KEY,
    checklist_id UUID NOT NULL REFERENCES onboarding_checklists(id),
    section VARCHAR(80) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    item_text VARCHAR(500) NOT NULL,
    responsibility VARCHAR(40) NOT NULL DEFAULT 'hr',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    owner_user_id UUID NULL REFERENCES users(id),
    help_ticket_id UUID NULL REFERENCES tickets(id),
    completed_by_id UUID NULL REFERENCES users(id),
    completion_date DATE NULL,
    notes TEXT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_onboarding_checklists_status ON onboarding_checklists (status)",
    "CREATE INDEX IF NOT EXISTS ix_onboarding_checklists_employee_user_id ON onboarding_checklists (employee_user_id)",
    "CREATE INDEX IF NOT EXISTS ix_onboarding_checklist_items_checklist_id ON onboarding_checklist_items (checklist_id)",
)


def _seed_default_template(engine: Engine) -> None:
    structure = json.dumps(PP_HRD_FO_14_STRUCTURE)
    now = datetime.utcnow().isoformat(sep=" ")
    row_id = str(uuid.uuid4()).replace("-", "") if engine.dialect.name == "sqlite" else str(uuid.uuid4())
    # Prefer dashed UUID for PG; for SQLite ProTrack often stores hex without dashes
    # for ORM Uuid(as_uuid=True). Match ORM style used elsewhere (hex for sqlite).
    if engine.dialect.name != "sqlite":
        row_id = str(uuid.uuid4())
    else:
        row_id = uuid.uuid4().hex

    with engine.begin() as connection:
        existing = connection.execute(
            text(
                "SELECT id FROM onboarding_checklist_templates WHERE code = :code LIMIT 1"
            ),
            {"code": FORM_CODE},
        ).fetchone()
        if existing is not None:
            return
        connection.execute(
            text(
                """
                INSERT INTO onboarding_checklist_templates
                    (id, code, name, version, structure_json, is_active, created_at, updated_at)
                VALUES
                    (:id, :code, :name, 1, :structure_json, :active, :created_at, :updated_at)
                """
            ),
            {
                "id": row_id,
                "code": FORM_CODE,
                "name": FORM_TITLE,
                "structure_json": structure,
                "active": True if engine.dialect.name != "sqlite" else 1,
                "created_at": now,
                "updated_at": now,
            },
        )


def _sqlite_has_column(engine: Engine, table: str, column: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


_PLACEMENT_COLUMNS = (
    ("org_department_id", "CHAR(36) NULL", "UUID NULL"),
    ("team_id", "CHAR(36) NULL", "UUID NULL"),
    ("team_name", "VARCHAR(120) NULL", "VARCHAR(120) NULL"),
    ("role_id", "CHAR(36) NULL", "UUID NULL"),
    ("role_name", "VARCHAR(120) NULL", "VARCHAR(120) NULL"),
)


def _ensure_placement_columns(engine: Engine) -> None:
    """Add department/team/role columns when upgrading an existing phase54 table."""
    if not _sqlite_has_table(engine, "onboarding_checklists") and engine.dialect.name == "sqlite":
        return
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            for column, ddl, _pg in _PLACEMENT_COLUMNS:
                if not _sqlite_has_column(engine, "onboarding_checklists", column):
                    connection.execute(
                        text(f"ALTER TABLE onboarding_checklists ADD COLUMN {column} {ddl}")
                    )
        else:
            for column, _sq, pg in _PLACEMENT_COLUMNS:
                connection.execute(
                    text(
                        f"ALTER TABLE onboarding_checklists "
                        f"ADD COLUMN IF NOT EXISTS {column} {pg}"
                    )
                )


_ITEM_COLUMNS = (
    ("owner_user_id", "CHAR(36) NULL", "UUID NULL"),
    ("help_ticket_id", "CHAR(36) NULL", "UUID NULL"),
)


def _ensure_item_columns(engine: Engine) -> None:
    if not _sqlite_has_table(engine, "onboarding_checklist_items") and engine.dialect.name == "sqlite":
        return
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            for column, ddl, _pg in _ITEM_COLUMNS:
                if not _sqlite_has_column(engine, "onboarding_checklist_items", column):
                    connection.execute(
                        text(
                            f"ALTER TABLE onboarding_checklist_items ADD COLUMN {column} {ddl}"
                        )
                    )
        else:
            for column, _sq, pg in _ITEM_COLUMNS:
                connection.execute(
                    text(
                        f"ALTER TABLE onboarding_checklist_items "
                        f"ADD COLUMN IF NOT EXISTS {column} {pg}"
                    )
                )


def ensure_phase54_onboarding_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "onboarding_checklist_templates"):
                connection.execute(text(_SQLITE_TEMPLATES))
            if not _sqlite_has_table(engine, "onboarding_checklists"):
                connection.execute(text(_SQLITE_CHECKLISTS))
            if not _sqlite_has_table(engine, "onboarding_checklist_items"):
                connection.execute(text(_SQLITE_ITEMS))
        else:
            connection.execute(text(_PG_TEMPLATES))
            connection.execute(text(_PG_CHECKLISTS))
            connection.execute(text(_PG_ITEMS))
        for statement in _INDEXES:
            connection.execute(text(statement))

    _ensure_placement_columns(engine)
    _ensure_item_columns(engine)
    _seed_default_template(engine)
