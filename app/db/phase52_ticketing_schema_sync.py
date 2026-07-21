"""Phase 52 — Help-desk / ticketing system (IT, Facility, Admin, HR, …).

Creates the ``tickets`` and ``ticket_comments`` tables. ``Base.metadata.
create_all`` already creates missing tables on startup and in tests, so these
statements are idempotent (guarded / ``IF NOT EXISTS``) and mainly guarantee the
supporting indexes exist for the ticket queue queries. Workflow fields
(category / priority / status) are plain strings validated by the API schemas,
mirroring :class:`CompensationChangeRequest`.
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


_SQLITE_TICKETS = """
CREATE TABLE IF NOT EXISTS tickets (
    id CHAR(36) NOT NULL PRIMARY KEY,
    ticket_number VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'it',
    priority VARCHAR(16) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    requester_id CHAR(36) NOT NULL,
    assignee_id CHAR(36) NULL,
    org_department_id CHAR(36) NULL,
    location VARCHAR(120) NULL,
    due_date DATE NULL,
    resolution TEXT NULL,
    resolved_at DATETIME NULL,
    closed_at DATETIME NULL,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(requester_id) REFERENCES users (id),
    FOREIGN KEY(assignee_id) REFERENCES users (id),
    FOREIGN KEY(org_department_id) REFERENCES org_departments (id)
)
"""

_SQLITE_COMMENTS = """
CREATE TABLE IF NOT EXISTS ticket_comments (
    id CHAR(36) NOT NULL PRIMARY KEY,
    ticket_id CHAR(36) NOT NULL,
    author_id CHAR(36) NOT NULL,
    body TEXT NOT NULL,
    is_internal BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(ticket_id) REFERENCES tickets (id),
    FOREIGN KEY(author_id) REFERENCES users (id)
)
"""

_PG_TICKETS = """
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY,
    ticket_number VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'it',
    priority VARCHAR(16) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    requester_id UUID NOT NULL REFERENCES users(id),
    assignee_id UUID NULL REFERENCES users(id),
    org_department_id UUID NULL REFERENCES org_departments(id),
    location VARCHAR(120) NULL,
    due_date DATE NULL,
    resolution TEXT NULL,
    resolved_at TIMESTAMP NULL,
    closed_at TIMESTAMP NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""

_PG_COMMENTS = """
CREATE TABLE IF NOT EXISTS ticket_comments (
    id UUID PRIMARY KEY,
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    author_id UUID NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets (status)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_category ON tickets (category)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_requester_id ON tickets (requester_id)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_assignee_id ON tickets (assignee_id)",
    "CREATE INDEX IF NOT EXISTS ix_ticket_comments_ticket_id ON ticket_comments (ticket_id)",
)


def ensure_phase52_ticketing_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "tickets"):
                connection.execute(text(_SQLITE_TICKETS))
            if not _sqlite_has_table(engine, "ticket_comments"):
                connection.execute(text(_SQLITE_COMMENTS))
        else:
            connection.execute(text(_PG_TICKETS))
            connection.execute(text(_PG_COMMENTS))

        for statement in _INDEXES:
            connection.execute(text(statement))
