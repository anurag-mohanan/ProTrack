"""Phase 102 — IT provisioning requests, hardware requirements, assignment types."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table_name},
        ).fetchone()
    return row is not None


def ensure_phase102_it_provisioning_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        assignment_cols = {
            "assignment_type": "VARCHAR(20) NOT NULL DEFAULT 'PRIMARY'",
            "override_reason": "VARCHAR(500)",
        }
        sw_req_cols = {
            "provisioning_request_id": "CHAR(36)",
            "license_required": "BOOLEAN NOT NULL DEFAULT 1",
            "priority": "VARCHAR(20) NOT NULL DEFAULT 'medium'",
            "purpose": "VARCHAR(500)",
            "requested_by_id": "CHAR(36)",
            "status": "VARCHAR(40) NOT NULL DEFAULT 'REQUESTED'",
        }

        if dialect == "sqlite":
            for col, ddl in assignment_cols.items():
                if not _sqlite_has_column(engine, "asset_assignments", col):
                    connection.execute(
                        text(f"ALTER TABLE asset_assignments ADD COLUMN {col} {ddl}")
                    )
            for col, ddl in sw_req_cols.items():
                if not _sqlite_has_column(engine, "employee_software_requirements", col):
                    connection.execute(
                        text(
                            f"ALTER TABLE employee_software_requirements ADD COLUMN {col} {ddl}"
                        )
                    )

            if not _sqlite_has_table(engine, "it_provisioning_requests"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE it_provisioning_requests (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            tenant_id CHAR(36) NOT NULL,
                            user_id CHAR(36) NOT NULL,
                            checklist_id CHAR(36),
                            ticket_id CHAR(36),
                            shift_id CHAR(36),
                            required_by DATE,
                            priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                            status VARCHAR(40) NOT NULL DEFAULT 'OPEN',
                            assigned_it_user_id CHAR(36),
                            processing_started_at DATETIME,
                            completed_at DATETIME,
                            notes TEXT,
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_prov_req_user "
                        "ON it_provisioning_requests (user_id)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_prov_req_status "
                        "ON it_provisioning_requests (status)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_prov_req_ticket "
                        "ON it_provisioning_requests (ticket_id)"
                    )
                )

            if not _sqlite_has_table(engine, "it_provisioning_hardware"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE it_provisioning_hardware (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            tenant_id CHAR(36) NOT NULL,
                            provisioning_request_id CHAR(36) NOT NULL UNIQUE,
                            computer_required BOOLEAN NOT NULL DEFAULT 1,
                            computer_type VARCHAR(40),
                            computer_is_required BOOLEAN NOT NULL DEFAULT 1,
                            monitor_quantity INTEGER NOT NULL DEFAULT 0,
                            monitor_is_required BOOLEAN NOT NULL DEFAULT 1,
                            mouse_3d_required BOOLEAN NOT NULL DEFAULT 0,
                            mouse_3d_is_required BOOLEAN NOT NULL DEFAULT 0,
                            mouse_3d_model_hint VARCHAR(200),
                            mouse_3d_asset_type_id CHAR(36),
                            wireless_mouse_required BOOLEAN NOT NULL DEFAULT 0,
                            laptop_dock_required BOOLEAN NOT NULL DEFAULT 0,
                            laptop_bag_required BOOLEAN NOT NULL DEFAULT 0,
                            headset_required BOOLEAN NOT NULL DEFAULT 0,
                            wireless_keyboard_required BOOLEAN NOT NULL DEFAULT 0,
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
        else:
            for table, cols in (
                ("asset_assignments", assignment_cols),
                ("employee_software_requirements", sw_req_cols),
            ):
                for col, ddl in cols.items():
                    connection.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl}"
                        )
                    )

            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS it_provisioning_requests (
                        id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL,
                        user_id UUID NOT NULL,
                        checklist_id UUID,
                        ticket_id UUID,
                        shift_id UUID,
                        required_by DATE,
                        priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                        status VARCHAR(40) NOT NULL DEFAULT 'OPEN',
                        assigned_it_user_id UUID,
                        processing_started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        notes TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_it_prov_req_user "
                    "ON it_provisioning_requests (user_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_it_prov_req_status "
                    "ON it_provisioning_requests (status)"
                )
            )

            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS it_provisioning_hardware (
                        id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL,
                        provisioning_request_id UUID NOT NULL UNIQUE,
                        computer_required BOOLEAN NOT NULL DEFAULT TRUE,
                        computer_type VARCHAR(40),
                        computer_is_required BOOLEAN NOT NULL DEFAULT TRUE,
                        monitor_quantity INTEGER NOT NULL DEFAULT 0,
                        monitor_is_required BOOLEAN NOT NULL DEFAULT TRUE,
                        mouse_3d_required BOOLEAN NOT NULL DEFAULT FALSE,
                        mouse_3d_is_required BOOLEAN NOT NULL DEFAULT FALSE,
                        mouse_3d_model_hint VARCHAR(200),
                        mouse_3d_asset_type_id UUID,
                        wireless_mouse_required BOOLEAN NOT NULL DEFAULT FALSE,
                        laptop_dock_required BOOLEAN NOT NULL DEFAULT FALSE,
                        laptop_bag_required BOOLEAN NOT NULL DEFAULT FALSE,
                        headset_required BOOLEAN NOT NULL DEFAULT FALSE,
                        wireless_keyboard_required BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
