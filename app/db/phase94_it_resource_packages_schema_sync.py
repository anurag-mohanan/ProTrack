"""Phase 94 — Resource package templates (requirement, not inventory)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.it_operations import (
    ResourcePackage,
    ResourcePackageHardwareLine,
    ResourcePackageSoftwareLine,
)


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


def ensure_phase94_it_resource_packages_foundation(engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        _ensure_pg_enum_value(engine, "activity_action", "it_resource_package_assigned")
        _ensure_pg_enum_value(engine, "entity_type", "it_resource_package")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ResourcePackage.__table__,
            ResourcePackageHardwareLine.__table__,
            ResourcePackageSoftwareLine.__table__,
        ],
    )
