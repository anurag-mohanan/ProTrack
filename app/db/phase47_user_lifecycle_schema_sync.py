"""Phase 47 — Dated user lifecycle history.

Adds two dated-history tables so person-level changes are recorded with an
effective date and applied forward:

* ``user_working_model_periods`` — dated person-level billing/working model
  (e.g. moving a resource from fixed-project billing to dedicated billing).
* ``user_job_events`` — dated audit log of transfers, promotions, and billing
  changes with before/after snapshots.

These tables only record history and drive the apply-forward sweep; they do not
alter existing finance primary-team homes.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
    return row is not None


def ensure_phase47_user_lifecycle_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "user_working_model_periods"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE user_working_model_periods (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            user_id CHAR(36) NOT NULL,
                            working_model_id CHAR(36) NULL,
                            effective_from DATE NOT NULL,
                            effective_to DATE NULL,
                            source_request_id CHAR(36) NULL,
                            notes TEXT NULL,
                            created_at DATETIME,
                            updated_at DATETIME,
                            FOREIGN KEY(user_id) REFERENCES users (id),
                            FOREIGN KEY(working_model_id) REFERENCES working_models (id)
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX ix_uwmp_user_id ON user_working_model_periods (user_id)"
                    )
                )
            if not _sqlite_has_table(engine, "user_job_events"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE user_job_events (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            user_id CHAR(36) NOT NULL,
                            event_type VARCHAR(32) NOT NULL,
                            effective_date DATE NOT NULL,
                            from_value TEXT NULL,
                            to_value TEXT NULL,
                            source_request_id CHAR(36) NULL,
                            created_by_id CHAR(36) NULL,
                            applied_at DATETIME NULL,
                            notes TEXT NULL,
                            created_at DATETIME,
                            updated_at DATETIME,
                            FOREIGN KEY(user_id) REFERENCES users (id),
                            FOREIGN KEY(created_by_id) REFERENCES users (id)
                        )
                        """
                    )
                )
                connection.execute(
                    text("CREATE INDEX ix_uje_user_id ON user_job_events (user_id)")
                )
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_working_model_periods (
                        id UUID PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES users(id),
                        working_model_id UUID NULL REFERENCES working_models(id),
                        effective_from DATE NOT NULL,
                        effective_to DATE NULL,
                        source_request_id UUID NULL,
                        notes TEXT NULL,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_uwmp_user_id "
                    "ON user_working_model_periods (user_id)"
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_job_events (
                        id UUID PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES users(id),
                        event_type VARCHAR(32) NOT NULL,
                        effective_date DATE NOT NULL,
                        from_value TEXT NULL,
                        to_value TEXT NULL,
                        source_request_id UUID NULL,
                        created_by_id UUID NULL REFERENCES users(id),
                        applied_at TIMESTAMP NULL,
                        notes TEXT NULL,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_uje_user_id "
                    "ON user_job_events (user_id)"
                )
            )
