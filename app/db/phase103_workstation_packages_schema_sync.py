"""Phase 103 — physical workstation equipment packages + package assignments."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table_name},
        ).fetchone()
    return row is not None


def ensure_phase103_workstation_packages_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "it_workstation_packages"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE it_workstation_packages (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            tenant_id CHAR(36) NOT NULL,
                            code VARCHAR(60) NOT NULL,
                            name VARCHAR(200) NOT NULL,
                            primary_computer_asset_id CHAR(36) NOT NULL,
                            computer_type VARCHAR(40),
                            status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
                            notes TEXT,
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_it_ws_pkg_tenant_code "
                        "ON it_workstation_packages (tenant_id, code)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_ws_pkg_computer "
                        "ON it_workstation_packages (primary_computer_asset_id)"
                    )
                )

            if not _sqlite_has_table(engine, "it_workstation_package_members"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE it_workstation_package_members (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            tenant_id CHAR(36) NOT NULL,
                            package_id CHAR(36) NOT NULL,
                            asset_id CHAR(36) NOT NULL,
                            role VARCHAR(40) NOT NULL,
                            is_required BOOLEAN NOT NULL DEFAULT 1,
                            follows_workstation BOOLEAN NOT NULL DEFAULT 1,
                            effective_from DATE NOT NULL,
                            effective_to DATE,
                            removed_reason VARCHAR(200),
                            notes TEXT,
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_ws_pkg_mem_pkg "
                        "ON it_workstation_package_members (package_id)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_ws_pkg_mem_asset "
                        "ON it_workstation_package_members (asset_id)"
                    )
                )

            if not _sqlite_has_table(engine, "it_workstation_package_assignments"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE it_workstation_package_assignments (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            tenant_id CHAR(36) NOT NULL,
                            package_id CHAR(36) NOT NULL,
                            user_id CHAR(36) NOT NULL,
                            shift_id CHAR(36) NOT NULL,
                            assigned_by_user_id CHAR(36) NOT NULL,
                            effective_from DATE NOT NULL,
                            effective_to DATE,
                            status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
                            notes TEXT,
                            override_reason VARCHAR(500),
                            provisioning_request_id CHAR(36),
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_ws_pkg_asg_pkg "
                        "ON it_workstation_package_assignments (package_id)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_ws_pkg_asg_user "
                        "ON it_workstation_package_assignments (user_id)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_it_ws_pkg_asg_shift "
                        "ON it_workstation_package_assignments (shift_id)"
                    )
                )
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS it_workstation_packages (
                        id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL,
                        code VARCHAR(60) NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        primary_computer_asset_id UUID NOT NULL,
                        computer_type VARCHAR(40),
                        status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
                        notes TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        UNIQUE (tenant_id, code)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS it_workstation_package_members (
                        id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL,
                        package_id UUID NOT NULL,
                        asset_id UUID NOT NULL,
                        role VARCHAR(40) NOT NULL,
                        is_required BOOLEAN NOT NULL DEFAULT TRUE,
                        follows_workstation BOOLEAN NOT NULL DEFAULT TRUE,
                        effective_from DATE NOT NULL,
                        effective_to DATE,
                        removed_reason VARCHAR(200),
                        notes TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS it_workstation_package_assignments (
                        id UUID PRIMARY KEY,
                        tenant_id UUID NOT NULL,
                        package_id UUID NOT NULL,
                        user_id UUID NOT NULL,
                        shift_id UUID NOT NULL,
                        assigned_by_user_id UUID NOT NULL,
                        effective_from DATE NOT NULL,
                        effective_to DATE,
                        status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
                        notes TEXT,
                        override_reason VARCHAR(500),
                        provisioning_request_id UUID,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
