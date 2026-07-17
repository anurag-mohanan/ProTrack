"""Phase 46 — Organization departments for hierarchical org chart.

Seeds Management / Engineering / Sales / HR / Administration / IT and links
teams + users for chart placement without changing finance primary-team homes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.phase23_finance_team_scope_schema_sync import CORPORATE_TEAM_NAME

ORG_DEPARTMENT_SEED: list[tuple[str, str, str, str, int]] = [
    ("management", "Management", "Executive and corporate leadership", "#455a64", 10),
    ("engineering", "Engineering", "Delivery teams, EM, and design leadership", "#1565c0", 20),
    ("sales", "Sales", "Commercial and business development", "#6a1b9a", 30),
    ("hr_admin", "HR / Administration", "People operations and office administration", "#00695c", 40),
    ("it", "IT", "Systems, platforms, and infrastructure", "#ef6c00", 50),
]


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


def _add_column_sqlite(connection, table: str, column: str, ddl: str, engine: Engine) -> None:
    if not _sqlite_has_column(engine, table, column):
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")


def ensure_phase46_org_department_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "org_departments"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE org_departments (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            code VARCHAR(40) NOT NULL UNIQUE,
                            name VARCHAR(120) NOT NULL UNIQUE,
                            description TEXT NULL,
                            colour VARCHAR(20) NOT NULL DEFAULT '#1976d2',
                            sort_order INTEGER NOT NULL DEFAULT 100,
                            head_user_id CHAR(36) NULL,
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            created_at DATETIME,
                            updated_at DATETIME,
                            FOREIGN KEY(head_user_id) REFERENCES users (id)
                        )
                        """
                    )
                )
            _add_column_sqlite(
                connection, "teams", "org_department_id", "CHAR(36) NULL", engine
            )
            _add_column_sqlite(
                connection, "users", "org_department_id", "CHAR(36) NULL", engine
            )
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS org_departments (
                        id UUID PRIMARY KEY,
                        code VARCHAR(40) NOT NULL UNIQUE,
                        name VARCHAR(120) NOT NULL UNIQUE,
                        description TEXT NULL,
                        colour VARCHAR(20) NOT NULL DEFAULT '#1976d2',
                        sort_order INTEGER NOT NULL DEFAULT 100,
                        head_user_id UUID NULL REFERENCES users(id),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE teams ADD COLUMN IF NOT EXISTS org_department_id UUID NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS org_department_id UUID NULL"
                )
            )

        now = _now()
        dept_ids: dict[str, str] = {}
        for code, name, description, colour, sort_order in ORG_DEPARTMENT_SEED:
            existing = connection.execute(
                text("SELECT id FROM org_departments WHERE code = :code"),
                {"code": code},
            ).fetchone()
            if existing is not None:
                dept_ids[code] = str(existing[0])
                connection.execute(
                    text(
                        """
                        UPDATE org_departments
                        SET name = :name,
                            description = :description,
                            colour = :colour,
                            sort_order = :sort_order,
                            is_active = 1,
                            updated_at = :updated_at
                        WHERE code = :code
                        """
                    ),
                    {
                        "code": code,
                        "name": name,
                        "description": description,
                        "colour": colour,
                        "sort_order": sort_order,
                        "updated_at": now,
                    },
                )
            else:
                dept_id = str(uuid.uuid4())
                dept_ids[code] = dept_id
                connection.execute(
                    text(
                        """
                        INSERT INTO org_departments (
                            id, code, name, description, colour, sort_order,
                            head_user_id, is_active, created_at, updated_at
                        ) VALUES (
                            :id, :code, :name, :description, :colour, :sort_order,
                            NULL, 1, :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "id": dept_id,
                        "code": code,
                        "name": name,
                        "description": description,
                        "colour": colour,
                        "sort_order": sort_order,
                        "created_at": now,
                        "updated_at": now,
                    },
                )

        engineering_id = dept_ids.get("engineering")
        management_id = dept_ids.get("management")
        hr_id = dept_ids.get("hr_admin")

        if management_id:
            connection.execute(
                text(
                    """
                    UPDATE teams
                    SET org_department_id = :dept_id
                    WHERE name = :corporate_name
                      AND (org_department_id IS NULL OR org_department_id = '')
                    """
                ),
                {"dept_id": management_id, "corporate_name": CORPORATE_TEAM_NAME},
            )
        if engineering_id:
            connection.execute(
                text(
                    """
                    UPDATE teams
                    SET org_department_id = :dept_id
                    WHERE is_active = 1
                      AND name != :corporate_name
                      AND (org_department_id IS NULL OR org_department_id = '')
                    """
                ),
                {"dept_id": engineering_id, "corporate_name": CORPORATE_TEAM_NAME},
            )

        # Chandrashekhar / Office Administrator → HR / Administration
        if hr_id:
            connection.execute(
                text(
                    """
                    UPDATE users
                    SET org_department_id = :dept_id
                    WHERE is_deleted = 0
                      AND (
                        lower(first_name) LIKE 'chandrashekhar%'
                        OR lower(coalesce(designation, '')) LIKE '%office administrator%'
                        OR role_id IN (
                            SELECT id FROM roles
                            WHERE lower(name) IN ('office administrator', 'hr')
                        )
                      )
                    """
                ),
                {"dept_id": hr_id},
            )

        # Remaining active users without a department → Engineering
        if engineering_id:
            connection.execute(
                text(
                    """
                    UPDATE users
                    SET org_department_id = :dept_id
                    WHERE is_deleted = 0
                      AND is_active = 1
                      AND (org_department_id IS NULL OR org_department_id = '')
                    """
                ),
                {"dept_id": engineering_id},
            )

        # Prefer Engineering Manager as Engineering department head when unset
        if engineering_id:
            head = connection.execute(
                text("SELECT head_user_id FROM org_departments WHERE code = 'engineering'")
            ).fetchone()
            if head is not None and head[0] is None:
                em = connection.execute(
                    text(
                        """
                        SELECT u.id FROM users u
                        JOIN roles r ON r.id = u.role_id
                        WHERE u.is_deleted = 0 AND u.is_active = 1
                          AND lower(r.name) = 'engineering manager'
                        ORDER BY u.first_name, u.last_name
                        LIMIT 1
                        """
                    )
                ).fetchone()
                if em is not None:
                    connection.execute(
                        text(
                            """
                            UPDATE org_departments
                            SET head_user_id = :user_id, updated_at = :updated_at
                            WHERE code = 'engineering'
                            """
                        ),
                        {"user_id": str(em[0]), "updated_at": now},
                    )
