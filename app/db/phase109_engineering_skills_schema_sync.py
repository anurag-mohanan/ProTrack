"""Phase 109 — Engineering skills taxonomy, verified skill profiles and planning.

Additive only. New tables (``skill_proficiency_levels``, ``skill_relationships``,
``user_skill_events``, ``user_skill_evidence``, ``project_skill_requirements``,
``skill_development_plans``) are created by ``create_all``; this step adds
columns to the existing ``skills`` and ``user_skills`` tables.

Backfill rules (nothing is invented):

* Existing ``user_skills`` rows were entered by an administrator through the
  legacy settings endpoint. They become ``origin = legacy`` and
  ``status = pending_verification``: recorded, never verified. Their legacy
  four-value ``proficiency`` stays as it is; the 1–5 ``declared_level`` stays
  empty because the old scale does not map onto the new one.
* Existing skills keep their name, category and active flag; the new
  classification fields stay empty until an administrator sets them.

Rollback: the new columns are nullable or defaulted and are ignored by older
code, so rolling back the application is enough. To remove the schema, drop the
six new tables and (on PostgreSQL) the added columns; no existing column,
table or value is altered.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_UUID_SQLITE = "CHAR(32) NULL"


def _uuid_pg(ref: str | None = None) -> str:
    return f"UUID NULL REFERENCES {ref}(id)" if ref else "UUID NULL"


_COLUMNS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "skills": (
        ("kind", "VARCHAR(30) NULL", "VARCHAR(30) NULL"),
        ("description", "TEXT NULL", "TEXT NULL"),
        ("aliases", "TEXT NULL", "TEXT NULL"),
        ("discipline_id", _UUID_SQLITE, _uuid_pg("engineering_disciplines")),
        ("customer_id", _UUID_SQLITE, _uuid_pg("customers")),
        ("is_critical", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("min_verified_coverage", "INTEGER NULL", "INTEGER NULL"),
        ("specialist_level", "INTEGER NULL", "INTEGER NULL"),
        ("reassessment_months", "INTEGER NULL", "INTEGER NULL"),
        ("sort_order", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
    ),
    "user_skills": (
        (
            "status",
            "VARCHAR(30) NOT NULL DEFAULT 'pending_verification'",
            "VARCHAR(30) NOT NULL DEFAULT 'pending_verification'",
        ),
        ("origin", "VARCHAR(20) NOT NULL DEFAULT 'legacy'", "VARCHAR(20) NOT NULL DEFAULT 'legacy'"),
        ("declared_level", "INTEGER NULL", "INTEGER NULL"),
        ("verified_level", "INTEGER NULL", "INTEGER NULL"),
        ("verification_method", "VARCHAR(30) NULL", "VARCHAR(30) NULL"),
        ("verified_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("verified_by_id", _UUID_SQLITE, _uuid_pg("users")),
        ("last_assessed_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("last_assessed_by_id", _UUID_SQLITE, _uuid_pg("users")),
        ("years_experience", "NUMERIC(4, 1) NULL", "NUMERIC(4, 1) NULL"),
        ("last_used_on", "DATE NULL", "DATE NULL"),
        ("employee_note", "TEXT NULL", "TEXT NULL"),
        ("assessment_feedback", "TEXT NULL", "TEXT NULL"),
        ("confidential_notes", "TEXT NULL", "TEXT NULL"),
        ("status_changed_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("updated_by_id", _UUID_SQLITE, _uuid_pg("users")),
    ),
}

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_user_skills_status ON user_skills (status)",
    "CREATE INDEX IF NOT EXISTS ix_user_skills_skill_id ON user_skills (skill_id)",
)

_ACTIVITY_ACTIONS = ("skill_profile_changed", "skill_taxonomy_changed")


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


def ensure_phase109_engineering_skills_foundation(engine: Engine) -> None:
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
        if inspector.has_table("user_skills"):
            for statement in _INDEXES:
                connection.execute(text(statement))
    if dialect == "postgresql":
        for value in _ACTIVITY_ACTIONS:
            _ensure_pg_enum_value(engine, "activity_action", value)
