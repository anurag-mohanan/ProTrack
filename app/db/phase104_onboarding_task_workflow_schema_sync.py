"""Phase 104 — Onboarding task workflow (explicit statuses, reasons, request linkage).

Additive only: new nullable columns on ``onboarding_checklist_items`` plus an
in-place mapping of the legacy ``pending`` / ``not_applicable`` values. No rows
are deleted and IDs, foreign keys and timestamps are untouched.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_TABLE = "onboarding_checklist_items"

_COLUMNS = (
    ("due_date", "DATE NULL", "DATE NULL"),
    ("requires_request", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("validation_rule", "VARCHAR(40) NULL", "VARCHAR(40) NULL"),
    ("status_reason", "TEXT NULL", "TEXT NULL"),
    ("status_changed_at", "DATETIME NULL", "TIMESTAMP NULL"),
    ("status_changed_by_id", "CHAR(36) NULL", "UUID NULL REFERENCES users(id)"),
    ("completed_at", "DATETIME NULL", "TIMESTAMP NULL"),
    ("completion_type", "VARCHAR(30) NULL", "VARCHAR(30) NULL"),
)

WORKSTATION_ITEM_TEXT = "Workstation, 3D mouse & license ready"


def _ensure_pg_enum_value(engine: Engine, enum_name: str, value: str) -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                """
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = :enum_name AND e.enumlabel = :value
                """
            ),
            {"enum_name": enum_name, "value": value},
        ).fetchone()
        if exists:
            return
        connection.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def ensure_phase104_onboarding_task_workflow_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "postgresql":
        _ensure_pg_enum_value(engine, "activity_action", "onboarding_task_status_changed")
        _ensure_pg_enum_value(engine, "activity_action", "onboarding_task_request_linked")
        _ensure_pg_enum_value(engine, "entity_type", "onboarding_task")
        _ensure_pg_enum_value(engine, "notification_entity_type", "onboarding_task")

    if not inspect(engine).has_table(_TABLE):
        return
    existing = {col["name"] for col in inspect(engine).get_columns(_TABLE)}
    with engine.begin() as connection:
        for column, sqlite_ddl, pg_ddl in _COLUMNS:
            if column in existing:
                continue
            ddl = pg_ddl if dialect == "postgresql" else sqlite_ddl
            connection.execute(text(f"ALTER TABLE {_TABLE} ADD COLUMN {column} {ddl}"))

        connection.execute(
            text(f"UPDATE {_TABLE} SET status = 'not_started' WHERE status = 'pending'")
        )
        connection.execute(
            text(f"UPDATE {_TABLE} SET status = 'not_required' WHERE status = 'not_applicable'")
        )
        connection.execute(
            text(
                f"UPDATE {_TABLE} SET requires_request = :yes, "
                "validation_rule = COALESCE(validation_rule, 'workstation_assigned') "
                "WHERE item_text = :text"
            ),
            {"yes": True, "text": WORKSTATION_ITEM_TEXT},
        )
        connection.execute(
            text(
                f"UPDATE {_TABLE} SET completed_at = completion_date "
                "WHERE completed_at IS NULL AND completion_date IS NOT NULL "
                "AND status = 'completed'"
            )
        )
        connection.execute(
            text(f"CREATE INDEX IF NOT EXISTS ix_{_TABLE}_help_ticket_id ON {_TABLE} (help_ticket_id)")
        )
