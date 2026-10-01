"""Phase 107 — Master ticket workflow (routing, lifecycle, provenance, onboarding config).

Additive only. ``ticket_routing_rules``, ``ticket_sla_policies``,
``ticket_assignment_history`` and ``ticket_notification_log`` are created by
``create_all``; this step adds columns to existing tables, registers PostgreSQL
enum values and derives provenance links that are already implied by existing
foreign keys:

* ``tickets.onboarding_item_id`` / ``affected_user_id`` / ``source_module`` from
  ``onboarding_checklist_items.help_ticket_id`` (only when exactly one task links
  to the ticket) and from ``it_provisioning_requests.ticket_id``.
* ``tickets.assignment_group`` from the existing ``category``.
* ``needs_owner`` for open tickets that have no assignee.
* ``needs_review`` for legacy grouped onboarding tickets linked to several tasks.

No owner, creation date, resolution or closure reason is invented, no status is
rewritten and nothing is deleted.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.phase104_onboarding_task_workflow_schema_sync import _ensure_pg_enum_value

_UUID_SQLITE = "CHAR(36) NULL"


def _uuid_pg(ref: str) -> str:
    return f"UUID NULL REFERENCES {ref}(id)"


_COLUMNS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "tickets": (
        ("subcategory", "VARCHAR(60) NULL", "VARCHAR(60) NULL"),
        ("source_module", "VARCHAR(40) NULL", "VARCHAR(40) NULL"),
        ("source_record_id", "VARCHAR(64) NULL", "VARCHAR(64) NULL"),
        ("idempotency_key", "VARCHAR(200) NULL", "VARCHAR(200) NULL"),
        ("affected_user_id", _UUID_SQLITE, _uuid_pg("users")),
        ("onboarding_item_id", _UUID_SQLITE, _uuid_pg("onboarding_checklist_items")),
        ("related_asset_id", _UUID_SQLITE, _uuid_pg("assets")),
        ("related_license_pool_id", _UUID_SQLITE, _uuid_pg("software_license_pools")),
        ("related_stock_item_id", _UUID_SQLITE, _uuid_pg("inventory_items")),
        ("assignment_group", "VARCHAR(40) NULL", "VARCHAR(40) NULL"),
        ("needs_owner", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("created_by_id", _UUID_SQLITE, _uuid_pg("users")),
        ("updated_by_id", _UUID_SQLITE, _uuid_pg("users")),
        ("work_performed", "TEXT NULL", "TEXT NULL"),
        ("resolution_category", "VARCHAR(40) NULL", "VARCHAR(40) NULL"),
        ("closure_reason", "VARCHAR(60) NULL", "VARCHAR(60) NULL"),
        ("cancellation_reason", "TEXT NULL", "TEXT NULL"),
        ("pending_reason", "TEXT NULL", "TEXT NULL"),
        ("assigned_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("started_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("first_response_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("sla_due_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("escalation_level", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
        ("escalated_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("last_activity_at", "DATETIME NULL", "TIMESTAMP NULL"),
        ("needs_review", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("review_note", "TEXT NULL", "TEXT NULL"),
    ),
    "ticket_category_routes": (
        ("backup_user_id", _UUID_SQLITE, _uuid_pg("users")),
        ("escalation_user_id", _UUID_SQLITE, _uuid_pg("users")),
        ("effective_from", "DATE NULL", "DATE NULL"),
    ),
    "onboarding_checklist_items": (
        ("execution_type", "VARCHAR(30) NULL", "VARCHAR(30) NULL"),
        ("mandatory", "BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("blocks_completion", "BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("evidence_required", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("reversible", "BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("task_priority", "VARCHAR(16) NULL", "VARCHAR(16) NULL"),
        ("ticket_category", "VARCHAR(20) NULL", "VARCHAR(20) NULL"),
        ("ticket_subcategory", "VARCHAR(60) NULL", "VARCHAR(60) NULL"),
        ("completion_rule", "VARCHAR(20) NULL", "VARCHAR(20) NULL"),
        ("owner_role", "VARCHAR(80) NULL", "VARCHAR(80) NULL"),
        ("confirm_by", "VARCHAR(20) NULL", "VARCHAR(20) NULL"),
        ("evidence_note", "TEXT NULL", "TEXT NULL"),
    ),
}

_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_tickets_tenant_idempotency_key "
    "ON tickets (tenant_id, idempotency_key)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_subcategory ON tickets (subcategory)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_source_module ON tickets (source_module)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_source_record_id ON tickets (source_record_id)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_affected_user_id ON tickets (affected_user_id)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_onboarding_item_id ON tickets (onboarding_item_id)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_related_asset_id ON tickets (related_asset_id)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_assignment_group ON tickets (assignment_group)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_sla_due_at ON tickets (sla_due_at)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_due_date ON tickets (due_date)",
    "CREATE INDEX IF NOT EXISTS ix_tickets_created_at ON tickets (created_at)",
)

_ACTIVITY_ACTIONS = (
    "ticket_cancelled",
    "ticket_transferred",
    "ticket_escalated",
    "ticket_linked",
    "ticket_routing_changed",
    "ticket_reviewed",
    "onboarding_template_updated",
)
_NOTIFICATION_TYPES = (
    "ticket_assigned",
    "ticket_status_changed",
    "ticket_comment",
    "ticket_due_soon",
    "ticket_overdue",
    "ticket_escalated",
    "ticket_needs_owner",
    "onboarding_task_update",
)


def _register_enums(engine: Engine) -> None:
    for value in _ACTIVITY_ACTIONS:
        _ensure_pg_enum_value(engine, "activity_action", value)
    for value in _NOTIFICATION_TYPES:
        _ensure_pg_enum_value(engine, "notification_type", value)
    for value in ("ticket", "onboarding_task", "onboarding_template"):
        _ensure_pg_enum_value(engine, "entity_type", value)
        _ensure_pg_enum_value(engine, "notification_entity_type", value)


def _backfill(connection) -> None:
    connection.execute(
        text("UPDATE tickets SET assignment_group = category WHERE assignment_group IS NULL")
    )
    connection.execute(
        text(
            "UPDATE tickets SET needs_owner = :yes WHERE assignee_id IS NULL "
            "AND status NOT IN ('resolved', 'closed', 'cancelled')"
        ),
        {"yes": True},
    )
    # One task -> one ticket: record the explicit source link.
    connection.execute(
        text(
            "UPDATE tickets SET "
            " onboarding_item_id = (SELECT i.id FROM onboarding_checklist_items i"
            "   WHERE i.help_ticket_id = tickets.id LIMIT 1),"
            " source_module = COALESCE(source_module, 'onboarding') "
            "WHERE onboarding_item_id IS NULL AND ("
            " SELECT COUNT(*) FROM onboarding_checklist_items i"
            " WHERE i.help_ticket_id = tickets.id) = 1"
        )
    )
    # Grouped legacy tickets: keep every link, flag for review.
    connection.execute(
        text(
            "UPDATE tickets SET needs_review = :yes, "
            " source_module = COALESCE(source_module, 'onboarding'), "
            " review_note = COALESCE(review_note, 'Legacy grouped onboarding ticket linked to several tasks; "
            "confirm each task outcome before closing.') "
            "WHERE onboarding_item_id IS NULL AND ("
            " SELECT COUNT(*) FROM onboarding_checklist_items i"
            " WHERE i.help_ticket_id = tickets.id) > 1"
        ),
        {"yes": True},
    )
    connection.execute(
        text(
            "UPDATE tickets SET affected_user_id = ("
            " SELECT c.employee_user_id FROM onboarding_checklist_items i"
            " JOIN onboarding_checklists c ON c.id = i.checklist_id"
            " WHERE i.help_ticket_id = tickets.id AND c.employee_user_id IS NOT NULL LIMIT 1) "
            "WHERE affected_user_id IS NULL AND EXISTS ("
            " SELECT 1 FROM onboarding_checklist_items i"
            " JOIN onboarding_checklists c ON c.id = i.checklist_id"
            " WHERE i.help_ticket_id = tickets.id AND c.employee_user_id IS NOT NULL)"
        )
    )


def _backfill_provisioning(connection) -> None:
    connection.execute(
        text(
            "UPDATE tickets SET "
            " source_module = COALESCE(source_module, 'it_provisioning'),"
            " affected_user_id = COALESCE(affected_user_id, ("
            "   SELECT r.user_id FROM it_provisioning_requests r WHERE r.ticket_id = tickets.id LIMIT 1)) "
            "WHERE EXISTS (SELECT 1 FROM it_provisioning_requests r WHERE r.ticket_id = tickets.id)"
        )
    )


def ensure_phase107_ticket_workflow_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "postgresql":
        _register_enums(engine)

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
        if not inspector.has_table("tickets"):
            return
        for statement in _INDEXES:
            connection.execute(text(statement))
        if inspector.has_table("onboarding_checklist_items"):
            _backfill(connection)
        if inspector.has_table("it_provisioning_requests"):
            _backfill_provisioning(connection)
