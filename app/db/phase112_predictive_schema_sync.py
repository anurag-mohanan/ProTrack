"""Phase 112 — Predictive engineering intelligence.

Additive only. ``prediction_settings``, ``prediction_model_versions``, ``prediction_runs``,
``predictions`` and ``prediction_scenarios`` are created by ``create_all``; this step adds
triage columns to ``project_risk_findings`` and the new Activity enum values on PostgreSQL.

Backfill: every existing finding becomes ``source = operational`` (which it is); the other new
columns stay empty. No business record is read or changed.

Rollback: drop the five ``prediction*`` tables; the added finding columns are nullable or
defaulted and older code ignores them. The added enum values are harmless if left.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_UUID_SQLITE = "CHAR(32) NULL"


def _uuid_pg(ref: str | None = None) -> str:
    return f"UUID NULL REFERENCES {ref}(id) ON DELETE SET NULL" if ref else "UUID NULL"


_COLUMNS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "project_risk_findings": (
        (
            "source",
            "VARCHAR(20) NOT NULL DEFAULT 'operational'",
            "VARCHAR(20) NOT NULL DEFAULT 'operational'",
        ),
        ("prediction_id", _UUID_SQLITE, _uuid_pg("predictions")),
        ("triage_status", "VARCHAR(20) NULL", "VARCHAR(20) NULL"),
        ("triage_note", "VARCHAR(500) NULL", "VARCHAR(500) NULL"),
        ("triaged_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("triaged_by_id", _UUID_SQLITE, "UUID NULL REFERENCES users(id)"),
        ("recommendation_id", _UUID_SQLITE, _uuid_pg("ai_recommendations")),
    ),
}

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_project_risk_findings_source ON project_risk_findings (source)",
)

_ENUM_VALUES = (
    ("activity_action", "prediction_setting_changed"),
    ("activity_action", "prediction_model_activated"),
    ("activity_action", "prediction_scenario_saved"),
    ("activity_action", "prediction_scenario_deleted"),
    ("activity_action", "risk_finding_triaged"),
    ("entity_type", "prediction_setting"),
    ("entity_type", "prediction_model"),
    ("entity_type", "prediction_scenario"),
    ("entity_type", "risk_finding"),
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


def ensure_phase112_predictive_foundation(engine: Engine) -> None:
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
        if inspector.has_table("project_risk_findings"):
            for statement in _INDEXES:
                connection.execute(text(statement))
    if dialect == "postgresql":
        for enum_name, value in _ENUM_VALUES:
            _ensure_pg_enum_value(engine, enum_name, value)
