"""Phase 113 — Business intelligence and strategic management.

Additive only. ``strategic_objectives``, ``objective_measurements``, ``strategic_initiatives``,
``management_reviews``, ``management_actions`` and ``management_events`` are created by
``create_all``; this step adds the new Activity and Notification enum values on PostgreSQL
(SQLite stores enums as text and needs nothing).

Backfill: none. No existing record is read or changed.

Rollback: drop the six tables above; nothing else references them. The added enum values are
harmless if left.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

_ENUM_VALUES = (
    ("activity_action", "strategy_objective_changed"),
    ("activity_action", "strategy_target_changed"),
    ("activity_action", "strategy_initiative_changed"),
    ("activity_action", "management_review_changed"),
    ("activity_action", "management_action_changed"),
    ("entity_type", "strategic_objective"),
    ("entity_type", "strategic_initiative"),
    ("entity_type", "management_review"),
    ("entity_type", "management_action"),
    ("notification_type", "management_action_assigned"),
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


def ensure_phase113_management_foundation(engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        for enum_name, value in _ENUM_VALUES:
            _ensure_pg_enum_value(engine, enum_name, value)
