"""Phase 70 — add tenant_id to business tables and backfill Prosohm (R10 M1)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.tenant_scoped_tables import TENANT_SCOPED_TABLES
from app.models.commercial import PROSOHM_TENANT_ID

# Dashed form for Postgres; hex form matches SQLAlchemy Uuid on SQLite.
_PROSOHM = str(PROSOHM_TENANT_ID)
_PROSOHM_SQLITE = PROSOHM_TENANT_ID.hex



def _sqlite_table_exists_conn(connection, table_name: str) -> bool:
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone()
    return row is not None


def _pg_table_exists(connection, table_name: str) -> bool:
    row = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": table_name},
    ).fetchone()
    return row is not None


def _ensure_prosohm_via_orm(engine: Engine) -> None:
    """Seed Prosohm with ORM so UUID storage matches other Uuid columns."""
    from app.services import tenant_service

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        tenant_service.ensure_prosohm_tenant(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_phase70_tenant_id_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    _ensure_prosohm_via_orm(engine)
    with engine.begin() as connection:
        for table in TENANT_SCOPED_TABLES:
            if dialect == "sqlite":
                if not _sqlite_table_exists_conn(connection, table):
                    continue
                cols = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
                has_col = any(row[1] == "tenant_id" for row in cols)
                if not has_col:
                    connection.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN tenant_id CHAR(32) "
                            f"NOT NULL DEFAULT '{_PROSOHM_SQLITE}'"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            f"UPDATE {table} SET tenant_id = :tid "
                            "WHERE tenant_id IS NULL OR tenant_id = '' "
                            "OR tenant_id = :dashed"
                        ),
                        {"tid": _PROSOHM_SQLITE, "dashed": _PROSOHM},
                    )
                connection.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id "
                        f"ON {table} (tenant_id)"
                    )
                )
            else:
                if not _pg_table_exists(connection, table):
                    continue
                connection.execute(
                    text(
                        f"ALTER TABLE {table} "
                        f"ADD COLUMN IF NOT EXISTS tenant_id UUID "
                        f"DEFAULT '{_PROSOHM}'::uuid"
                    )
                )
                connection.execute(
                    text(
                        f"UPDATE {table} SET tenant_id = CAST(:tid AS uuid) "
                        "WHERE tenant_id IS NULL"
                    ),
                    {"tid": _PROSOHM},
                )
                connection.execute(
                    text(
                        f"ALTER TABLE {table} "
                        "ALTER COLUMN tenant_id SET DEFAULT "
                        f"'{_PROSOHM}'::uuid"
                    )
                )
                try:
                    connection.execute(
                        text(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL")
                    )
                except Exception:
                    pass
                connection.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id "
                        f"ON {table} (tenant_id)"
                    )
                )
                try:
                    connection.execute(
                        text(
                            f"DO $$ BEGIN "
                            f"ALTER TABLE {table} "
                            f"ADD CONSTRAINT fk_{table}_tenant_id "
                            "FOREIGN KEY (tenant_id) REFERENCES tenants (id) "
                            "ON DELETE RESTRICT; "
                            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
                        )
                    )
                except Exception:
                    pass
