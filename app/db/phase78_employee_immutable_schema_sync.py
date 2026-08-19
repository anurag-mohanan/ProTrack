"""Phase 78 — activity_action for historical employee corrections."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


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
        connection.execute(
            text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
        )


def ensure_phase78_employee_immutable_foundation(engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        _ensure_pg_enum_value(engine, "activity_action", "user_historical_correction")
