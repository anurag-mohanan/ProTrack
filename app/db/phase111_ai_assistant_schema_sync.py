"""Phase 111 — Engineering management assistant.

Additive only. ``ai_conversations``, ``ai_messages``, ``ai_recommendations`` and
``ai_tool_executions`` are created by ``create_all``; no existing table or column is
changed and nothing is backfilled.

This step adds the new Activity enum values on PostgreSQL (SQLite stores enums as text).

Rollback: drop the four ``ai_*`` tables. The added enum values are harmless if left.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

_ENUM_VALUES = (
    ("activity_action", "ai_recommendation_decided"),
    ("entity_type", "ai_recommendation"),
)


def ensure_phase111_ai_assistant_foundation(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    for enum_name, value in _ENUM_VALUES:
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
