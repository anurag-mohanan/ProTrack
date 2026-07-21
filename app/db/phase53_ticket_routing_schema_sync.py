"""Phase 53 — Per-category ticket routing (admin-set contact / owner).

Creates ``ticket_category_routes`` so administrators can nominate a specific
person to receive each ticket category (IT, Facility, Admin, HR, Other). New
tickets are auto-assigned to that contact; when unset, tickets fall back to the
role-based responder queues. ``Base.metadata.create_all`` also creates this
table, so the statements here are idempotent (``IF NOT EXISTS`` / guarded).
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


_SQLITE_TABLE = """
CREATE TABLE IF NOT EXISTS ticket_category_routes (
    id CHAR(36) NOT NULL PRIMARY KEY,
    category VARCHAR(20) NOT NULL UNIQUE,
    assignee_user_id CHAR(36) NULL,
    org_department_id CHAR(36) NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(assignee_user_id) REFERENCES users (id),
    FOREIGN KEY(org_department_id) REFERENCES org_departments (id)
)
"""

_PG_TABLE = """
CREATE TABLE IF NOT EXISTS ticket_category_routes (
    id UUID PRIMARY KEY,
    category VARCHAR(20) NOT NULL UNIQUE,
    assignee_user_id UUID NULL REFERENCES users(id),
    org_department_id UUID NULL REFERENCES org_departments(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def ensure_phase53_ticket_routing_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "ticket_category_routes"):
                connection.execute(text(_SQLITE_TABLE))
        else:
            connection.execute(text(_PG_TABLE))
