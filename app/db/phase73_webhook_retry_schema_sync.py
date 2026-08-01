"""Phase 73 — webhook delivery retry columns (next_attempt_at, max_attempts)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase73_webhook_retry_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "webhook_deliveries", "next_attempt_at"):
                connection.execute(
                    text(
                        "ALTER TABLE webhook_deliveries "
                        "ADD COLUMN next_attempt_at DATETIME"
                    )
                )
            if not _sqlite_has_column(engine, "webhook_deliveries", "max_attempts"):
                connection.execute(
                    text(
                        "ALTER TABLE webhook_deliveries "
                        "ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 5"
                    )
                )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_next_attempt "
                    "ON webhook_deliveries (status, next_attempt_at)"
                )
            )
        else:
            connection.execute(
                text(
                    "ALTER TABLE webhook_deliveries "
                    "ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMP WITHOUT TIME ZONE"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE webhook_deliveries "
                    "ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 5"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_next_attempt "
                    "ON webhook_deliveries (status, next_attempt_at)"
                )
            )
