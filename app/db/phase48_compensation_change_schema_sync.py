"""Phase 48 — Compensation change requests (hike / promotion) with 2-level approval.

A Team Leader suggests a hike % (optionally carrying a promotion), which flows
through Engineering Manager (L1) then Director (L2) approval. On final approval
the change is applied on its effective date (apply-forward): the current
``employee_cost_profiles`` row is updated and a dated ``user_job_events`` audit
record is written.
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


def ensure_phase48_compensation_change_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "compensation_change_requests"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE compensation_change_requests (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            user_id CHAR(36) NOT NULL,
                            request_type VARCHAR(32) NOT NULL DEFAULT 'hike',
                            stage VARCHAR(32) NOT NULL DEFAULT 'suggested',
                            status VARCHAR(32) NOT NULL DEFAULT 'pending',
                            suggested_by_id CHAR(36) NULL,
                            hike_pct NUMERIC(6, 2) NULL,
                            currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
                            current_monthly_salary NUMERIC(14, 2) NULL,
                            proposed_monthly_salary NUMERIC(14, 2) NULL,
                            new_role_id CHAR(36) NULL,
                            new_designation VARCHAR(120) NULL,
                            new_working_model_id CHAR(36) NULL,
                            effective_date DATE NOT NULL,
                            justification TEXT NULL,
                            l1_approver_id CHAR(36) NULL,
                            l1_at DATETIME NULL,
                            l2_approver_id CHAR(36) NULL,
                            l2_at DATETIME NULL,
                            applied_at DATETIME NULL,
                            rejection_reason TEXT NULL,
                            created_at DATETIME,
                            updated_at DATETIME,
                            FOREIGN KEY(user_id) REFERENCES users (id),
                            FOREIGN KEY(suggested_by_id) REFERENCES users (id),
                            FOREIGN KEY(new_role_id) REFERENCES roles (id),
                            FOREIGN KEY(new_working_model_id) REFERENCES working_models (id),
                            FOREIGN KEY(l1_approver_id) REFERENCES users (id),
                            FOREIGN KEY(l2_approver_id) REFERENCES users (id)
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX ix_ccr_user_id ON compensation_change_requests (user_id)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX ix_ccr_stage ON compensation_change_requests (stage)"
                    )
                )
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS compensation_change_requests (
                        id UUID PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES users(id),
                        request_type VARCHAR(32) NOT NULL DEFAULT 'hike',
                        stage VARCHAR(32) NOT NULL DEFAULT 'suggested',
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        suggested_by_id UUID NULL REFERENCES users(id),
                        hike_pct NUMERIC(6, 2) NULL,
                        currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
                        current_monthly_salary NUMERIC(14, 2) NULL,
                        proposed_monthly_salary NUMERIC(14, 2) NULL,
                        new_role_id UUID NULL REFERENCES roles(id),
                        new_designation VARCHAR(120) NULL,
                        new_working_model_id UUID NULL REFERENCES working_models(id),
                        effective_date DATE NOT NULL,
                        justification TEXT NULL,
                        l1_approver_id UUID NULL REFERENCES users(id),
                        l1_at TIMESTAMP NULL,
                        l2_approver_id UUID NULL REFERENCES users(id),
                        l2_at TIMESTAMP NULL,
                        applied_at TIMESTAMP NULL,
                        rejection_reason TEXT NULL,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_ccr_user_id "
                    "ON compensation_change_requests (user_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_ccr_stage "
                    "ON compensation_change_requests (stage)"
                )
            )
