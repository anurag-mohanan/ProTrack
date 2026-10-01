"""Phase 106 — Shift-aware resource allocation (assets, licenses, reservations).

Additive only. ``it_resource_reservations`` and ``it_license_usage_sessions`` are
created by ``create_all``; this step adds the scheduling columns to the existing
assignment tables, the sharing-policy columns to asset types and registers
PostgreSQL enum values.

Existing assignments are preserved exactly: no dates or shifts are invented. Open
asset assignments without a shift or window remain "legacy — needs review" and are
listed in the reconciliation view; unscheduled floating-license assignments are
authorizations.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.phase104_onboarding_task_workflow_schema_sync import _ensure_pg_enum_value

_UUID = ("CHAR(36) NULL", "UUID NULL REFERENCES {ref}(id)")

_COLUMNS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "asset_assignments": (
        ("planned_end_date", "DATE NULL", "DATE NULL"),
        ("start_time", "VARCHAR(5) NULL", "VARCHAR(5) NULL"),
        ("end_time", "VARCHAR(5) NULL", "VARCHAR(5) NULL"),
        ("purpose", "VARCHAR(200) NULL", "VARCHAR(200) NULL"),
        ("released_by_user_id", _UUID[0], _UUID[1].format(ref="users")),
        ("released_at", "TIMESTAMP NULL", "TIMESTAMP NULL"),
    ),
    "software_assignments": (
        ("shift_id", _UUID[0], _UUID[1].format(ref="rp_shifts")),
        ("start_time", "VARCHAR(5) NULL", "VARCHAR(5) NULL"),
        ("end_time", "VARCHAR(5) NULL", "VARCHAR(5) NULL"),
        ("planned_end_date", "DATE NULL", "DATE NULL"),
        ("purpose", "VARCHAR(200) NULL", "VARCHAR(200) NULL"),
        ("assigned_by_user_id", _UUID[0], _UUID[1].format(ref="users")),
        ("released_by_user_id", _UUID[0], _UUID[1].format(ref="users")),
        ("override_reason", "VARCHAR(500) NULL", "VARCHAR(500) NULL"),
    ),
    "asset_types": (
        ("is_shareable", "BOOLEAN NULL", "BOOLEAN NULL"),
        ("requires_shift", "BOOLEAN NULL", "BOOLEAN NULL"),
    ),
}

_ACTIVITY_ACTIONS = (
    "it_license_assigned",
    "it_license_released",
    "it_license_checked_out",
    "it_license_checked_in",
    "it_license_metric_changed",
    "it_reservation_created",
    "it_reservation_released",
    "it_assignment_reviewed",
    "it_sharing_policy_updated",
    "it_setup_assigned",
)
_ENTITY_TYPES = ("it_license_pool", "it_reservation")


def ensure_phase106_shift_aware_allocation_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "postgresql":
        for value in _ACTIVITY_ACTIONS:
            _ensure_pg_enum_value(engine, "activity_action", value)
        for value in _ENTITY_TYPES:
            _ensure_pg_enum_value(engine, "entity_type", value)

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
        if inspector.has_table("software_assignments"):
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_software_assignments_shift_id "
                    "ON software_assignments (shift_id)"
                )
            )
