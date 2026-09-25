"""Phase 105 — Derived Virtual Seats + consumable stock control.

Additive only. New tables (virtual seats, stock locations/movements/reservations/
alerts, restock requests) are created by ``create_all``; this step adds columns to
existing tables, registers PostgreSQL enum values and backfills:

* ``inventory_items.on_hand_qty`` from the imported ``total_qty - issued_qty``
  snapshot (only when the column is first created).
* ``assets.computer_type`` from legacy workstation packages that declared one.

No rows are deleted and no statuses are reset.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.phase104_onboarding_task_workflow_schema_sync import _ensure_pg_enum_value

_INVENTORY_COLUMNS = (
    ("item_kind", "VARCHAR(40) NULL", "VARCHAR(40) NULL"),
    ("on_hand_qty", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
    ("min_stock", "INTEGER NULL", "INTEGER NULL"),
    ("reorder_point", "INTEGER NULL", "INTEGER NULL"),
    ("target_stock", "INTEGER NULL", "INTEGER NULL"),
    ("reorder_qty", "INTEGER NULL", "INTEGER NULL"),
    ("supplier_sku", "VARCHAR(80) NULL", "VARCHAR(80) NULL"),
    ("lead_time_days", "INTEGER NULL", "INTEGER NULL"),
    ("last_purchase_date", "DATE NULL", "DATE NULL"),
    ("last_purchase_cost", "NUMERIC(12,2) NULL", "NUMERIC(12,2) NULL"),
    ("is_returnable", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("location_id", "CHAR(36) NULL", "UUID NULL REFERENCES it_stock_locations(id)"),
)

_ACTIVITY_ACTIONS = (
    "it_virtual_seat_created",
    "it_virtual_seat_primary_changed",
    "it_virtual_seat_components_changed",
    "it_virtual_seat_ended",
    "it_stock_item_created",
    "it_stock_item_updated",
    "it_stock_movement",
    "it_stock_reserved",
    "it_stock_reservation_closed",
    "it_stock_alert_raised",
    "it_stock_alert_resolved",
    "it_restock_request_changed",
)
_ENTITY_TYPES = ("it_virtual_seat", "it_stock_item", "it_restock_request")


def ensure_phase105_inventory_virtual_seat_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "postgresql":
        for value in _ACTIVITY_ACTIONS:
            _ensure_pg_enum_value(engine, "activity_action", value)
        for value in _ENTITY_TYPES:
            _ensure_pg_enum_value(engine, "entity_type", value)
            _ensure_pg_enum_value(engine, "notification_entity_type", value)
        _ensure_pg_enum_value(engine, "notification_type", "it_low_stock")

    inspector = inspect(engine)
    with engine.begin() as connection:
        if inspector.has_table("assets"):
            asset_cols = {col["name"] for col in inspector.get_columns("assets")}
            if "computer_type" not in asset_cols:
                connection.execute(text("ALTER TABLE assets ADD COLUMN computer_type VARCHAR(40) NULL"))
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_assets_computer_type ON assets (computer_type)")
            )
            if inspector.has_table("it_workstation_packages"):
                connection.execute(
                    text(
                        "UPDATE assets SET computer_type = ("
                        " SELECT p.computer_type FROM it_workstation_packages p"
                        " WHERE p.primary_computer_asset_id = assets.id"
                        " AND p.computer_type IS NOT NULL LIMIT 1)"
                        " WHERE computer_type IS NULL AND EXISTS ("
                        " SELECT 1 FROM it_workstation_packages p"
                        " WHERE p.primary_computer_asset_id = assets.id"
                        " AND p.computer_type IS NOT NULL)"
                    )
                )

        if inspector.has_table("inventory_items"):
            existing = {col["name"] for col in inspector.get_columns("inventory_items")}
            created_on_hand = "on_hand_qty" not in existing
            for column, sqlite_ddl, pg_ddl in _INVENTORY_COLUMNS:
                if column in existing:
                    continue
                ddl = pg_ddl if dialect == "postgresql" else sqlite_ddl
                connection.execute(text(f"ALTER TABLE inventory_items ADD COLUMN {column} {ddl}"))
            if created_on_hand:
                connection.execute(
                    text(
                        "UPDATE inventory_items SET on_hand_qty = "
                        "CASE WHEN total_qty - issued_qty > 0 THEN total_qty - issued_qty ELSE 0 END"
                    )
                )
