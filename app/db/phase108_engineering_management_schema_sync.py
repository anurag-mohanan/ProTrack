"""Phase 108 — Engineering management: schedules, stage estimates, template versions.

Additive only. ``project_stage_estimates``, ``project_estimate_revisions`` and
``project_baseline_revisions`` are created by ``create_all``; this step adds the
new columns to existing tables.

Backfill rules (nothing is invented):

* Every existing template becomes version 1 of its own family.
* Project start, baseline, forecast and actual-start dates stay empty — legacy
  projects are reported as "not configured" until someone enters them.
* Milestone original estimates stay empty: the hours on legacy milestones are the
  current plan, and the original quote split was never recorded.
* ``teams.projects_enabled`` defaults to true for every existing team so no
  project table disappears; admins switch it off per team in Admin → Teams.
* ``users.user_type`` defaults to ``employee``; admins reclassify shared or
  system accounts explicitly in Admin → Users.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_UUID_SQLITE = "CHAR(32) NULL"


def _uuid_pg(ref: str | None = None) -> str:
    return f"UUID NULL REFERENCES {ref}(id)" if ref else "UUID NULL"


_COLUMNS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "users": (
        (
            "user_type",
            "VARCHAR(20) NOT NULL DEFAULT 'employee'",
            "VARCHAR(20) NOT NULL DEFAULT 'employee'",
        ),
    ),
    "teams": (
        ("projects_enabled", "BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ),
    "company_settings": (
        ("scheduling_effort_hours_per_day", "NUMERIC(4, 2) NULL", "NUMERIC(4, 2) NULL"),
    ),
    "project_templates": (
        ("template_family_id", _UUID_SQLITE, _uuid_pg()),
        ("version", "INTEGER NOT NULL DEFAULT 1", "INTEGER NOT NULL DEFAULT 1"),
        ("revision_note", "TEXT NULL", "TEXT NULL"),
        (
            "scheduling_mode",
            "VARCHAR(20) NOT NULL DEFAULT 'sequential'",
            "VARCHAR(20) NOT NULL DEFAULT 'sequential'",
        ),
        ("activated_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("created_by_id", _UUID_SQLITE, _uuid_pg("users")),
    ),
    "project_template_milestones": (("depends_on_ids", "TEXT NULL", "TEXT NULL"),),
    "projects": (
        ("start_date", "DATE NULL", "DATE NULL"),
        ("end_customer_id", _UUID_SQLITE, _uuid_pg("customers")),
        ("baseline_start_date", "DATE NULL", "DATE NULL"),
        ("baseline_completion_date", "DATE NULL", "DATE NULL"),
        ("baseline_version", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
        ("forecast_completion_date", "DATE NULL", "DATE NULL"),
        ("forecast_status", "VARCHAR(20) NULL", "VARCHAR(20) NULL"),
        ("forecast_note", "TEXT NULL", "TEXT NULL"),
        ("forecast_calculated_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("actual_start_date", "DATE NULL", "DATE NULL"),
    ),
    "milestones": (
        ("template_milestone_id", _UUID_SQLITE, _uuid_pg()),
        ("depends_on_ids", "TEXT NULL", "TEXT NULL"),
        ("original_planned_hours", "NUMERIC(8, 2) NULL", "NUMERIC(8, 2) NULL"),
        ("estimate_basis", "VARCHAR(30) NULL", "VARCHAR(30) NULL"),
        ("baseline_start_date", "DATE NULL", "DATE NULL"),
        ("baseline_finish_date", "DATE NULL", "DATE NULL"),
        ("forecast_start_date", "DATE NULL", "DATE NULL"),
        ("forecast_finish_date", "DATE NULL", "DATE NULL"),
        ("actual_start_date", "DATE NULL", "DATE NULL"),
        ("override_start_date", "DATE NULL", "DATE NULL"),
        ("override_finish_date", "DATE NULL", "DATE NULL"),
        ("override_reason", "TEXT NULL", "TEXT NULL"),
        ("override_by_id", _UUID_SQLITE, _uuid_pg("users")),
        ("override_at", "DATETIME NULL", "TIMESTAMP NULL"),
    ),
}

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_project_templates_template_family_id "
    "ON project_templates (template_family_id)",
    "CREATE INDEX IF NOT EXISTS ix_projects_end_customer_id ON projects (end_customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_projects_completed_at ON projects (completed_at)",
    "CREATE INDEX IF NOT EXISTS ix_milestones_template_milestone_id "
    "ON milestones (template_milestone_id)",
)


def ensure_phase108_engineering_management_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in _COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            for column, sqlite_ddl, pg_ddl in columns:
                if column in existing:
                    continue
                ddl = pg_ddl if dialect == "postgresql" else sqlite_ddl
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        if inspector.has_table("projects"):
            for statement in _INDEXES:
                connection.execute(text(statement))
        if inspector.has_table("project_templates"):
            connection.execute(
                text(
                    "UPDATE project_templates SET template_family_id = id "
                    "WHERE template_family_id IS NULL"
                )
            )
