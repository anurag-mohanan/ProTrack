"""Phase 110 — Smart template reconciliation and workflow automation.

Additive only. ``project_template_reconciliations``, ``automation_rules`` and
``automation_executions`` are created by ``create_all``; this step adds columns to
existing tables.

Backfill rules (nothing is invented):

* Every existing milestone becomes ``lifecycle_state = active``: it keeps counting
  exactly as before. No status, date, assignment or estimate is touched.
* ``projects.milestone_plan_version`` starts at 0.
* ``project_template_milestones.lineage_id`` stays empty on existing rows; readers
  fall back to the row id, and matching across versions uses template family and
  milestone name instead.

Rollback: the new columns are nullable or defaulted and older code ignores them.
To remove the schema, drop the three new tables (and, on PostgreSQL, the added
columns). Milestones that were merged, superseded or archived would then count
again as ordinary milestones, so restore them first if they matter.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_UUID_SQLITE = "CHAR(32) NULL"


def _uuid_pg(ref: str | None = None) -> str:
    return f"UUID NULL REFERENCES {ref}(id)" if ref else "UUID NULL"


_COLUMNS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "milestones": (
        (
            "lifecycle_state",
            "VARCHAR(20) NOT NULL DEFAULT 'active'",
            "VARCHAR(20) NOT NULL DEFAULT 'active'",
        ),
        ("merged_into_id", _UUID_SQLITE, _uuid_pg("milestones")),
        ("lifecycle_changed_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("lifecycle_changed_by_id", _UUID_SQLITE, _uuid_pg("users")),
        ("lifecycle_reason", "TEXT NULL", "TEXT NULL"),
        ("reconciliation_id", _UUID_SQLITE, _uuid_pg()),
    ),
    "projects": (
        (
            "milestone_plan_version",
            "INTEGER NOT NULL DEFAULT 0",
            "INTEGER NOT NULL DEFAULT 0",
        ),
    ),
    "project_template_milestones": (("lineage_id", _UUID_SQLITE, _uuid_pg()),),
}

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_milestones_lifecycle_state ON milestones (lifecycle_state)",
    "CREATE INDEX IF NOT EXISTS ix_milestones_merged_into_id ON milestones (merged_into_id)",
    "CREATE INDEX IF NOT EXISTS ix_project_template_milestones_lineage_id "
    "ON project_template_milestones (lineage_id)",
)

_ENUM_VALUES = (
    ("activity_action", "project_template_reconciled"),
    ("activity_action", "milestone_lifecycle_changed"),
    ("activity_action", "automation_rule_changed"),
    ("notification_type", "workflow_automation"),
)


def _ensure_pg_enum_value(engine: Engine, enum_name: str, value: str) -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                "SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = :enum_name AND e.enumlabel = :value"
            ),
            {"enum_name": enum_name, "value": value},
        ).scalar()
        if not exists:
            connection.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def ensure_phase110_workflow_reconciliation_foundation(engine: Engine) -> None:
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
        if inspector.has_table("milestones") and inspector.has_table("project_template_milestones"):
            for statement in _INDEXES:
                connection.execute(text(statement))
    if dialect == "postgresql":
        for enum_name, value in _ENUM_VALUES:
            _ensure_pg_enum_value(engine, enum_name, value)
