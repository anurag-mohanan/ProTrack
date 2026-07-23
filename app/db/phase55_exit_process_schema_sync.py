"""Phase 55 — Exit interviews (PP-HRD-FO-30).

Creates ``exit_interviews`` for the generic employee exit interview form.
Idempotent for SQLite and PostgreSQL.
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


_SQLITE_EXIT = """
CREATE TABLE IF NOT EXISTS exit_interviews (
    id CHAR(36) NOT NULL PRIMARY KEY,
    form_code VARCHAR(40) NOT NULL DEFAULT 'PP-HRD-FO-30',
    employee_user_id CHAR(36) NULL,
    employee_name VARCHAR(200) NOT NULL,
    employee_code VARCHAR(40) NULL,
    designation VARCHAR(120) NULL,
    department_name VARCHAR(120) NULL,
    org_department_id CHAR(36) NULL,
    team_id CHAR(36) NULL,
    team_name VARCHAR(120) NULL,
    role_id CHAR(36) NULL,
    role_name VARCHAR(120) NULL,
    reporting_manager_id CHAR(36) NULL,
    reporting_manager_name VARCHAR(200) NULL,
    last_working_date DATE NULL,
    resignation_date DATE NULL,
    interview_date DATE NULL,
    interviewer_user_id CHAR(36) NULL,
    interviewer_name VARCHAR(200) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    answers_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT NULL,
    created_by_id CHAR(36) NULL,
    completed_at DATETIME NULL,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(employee_user_id) REFERENCES users (id),
    FOREIGN KEY(org_department_id) REFERENCES org_departments (id),
    FOREIGN KEY(team_id) REFERENCES teams (id),
    FOREIGN KEY(role_id) REFERENCES roles (id),
    FOREIGN KEY(reporting_manager_id) REFERENCES users (id),
    FOREIGN KEY(interviewer_user_id) REFERENCES users (id),
    FOREIGN KEY(created_by_id) REFERENCES users (id)
)
"""

_PG_EXIT = """
CREATE TABLE IF NOT EXISTS exit_interviews (
    id UUID PRIMARY KEY,
    form_code VARCHAR(40) NOT NULL DEFAULT 'PP-HRD-FO-30',
    employee_user_id UUID NULL REFERENCES users (id),
    employee_name VARCHAR(200) NOT NULL,
    employee_code VARCHAR(40) NULL,
    designation VARCHAR(120) NULL,
    department_name VARCHAR(120) NULL,
    org_department_id UUID NULL REFERENCES org_departments (id),
    team_id UUID NULL REFERENCES teams (id),
    team_name VARCHAR(120) NULL,
    role_id UUID NULL REFERENCES roles (id),
    role_name VARCHAR(120) NULL,
    reporting_manager_id UUID NULL REFERENCES users (id),
    reporting_manager_name VARCHAR(200) NULL,
    last_working_date DATE NULL,
    resignation_date DATE NULL,
    interview_date DATE NULL,
    interviewer_user_id UUID NULL REFERENCES users (id),
    interviewer_name VARCHAR(200) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    answers_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT NULL,
    created_by_id UUID NULL REFERENCES users (id),
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def ensure_phase55_exit_process_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "exit_interviews"):
                connection.execute(text(_SQLITE_EXIT))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exit_interviews_status "
                    "ON exit_interviews (status)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exit_interviews_employee_user_id "
                    "ON exit_interviews (employee_user_id)"
                )
            )
        else:
            connection.execute(text(_PG_EXIT))
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exit_interviews_status "
                    "ON exit_interviews (status)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exit_interviews_employee_user_id "
                    "ON exit_interviews (employee_user_id)"
                )
            )
