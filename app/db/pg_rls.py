"""Optional PostgreSQL row-level security (R10) — defense in depth under ORM filters.

Enable with ``PROTRACK_ENABLE_PG_RLS=true`` on Postgres only.
Policies allow rows when ``app.tenant_id`` matches, or ``app.bypass_rls=1``.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.db.tenant_filter import resolve_effective_tenant_id, tenant_filter_skipped
from app.db.tenant_scoped_tables import TENANT_SCOPED_TABLES
from app.models.commercial import PROSOHM_TENANT_ID

logger = logging.getLogger("protrack.pg_rls")

_after_begin_registered = False

# feature_flags is tenant-scoped but excluded from M1 backfill catalog.
_RLS_EXTRA_TABLES = ("feature_flags",)

POLICY_NAME = "protrack_tenant_isolation"


def pg_rls_enabled() -> bool:
    return os.getenv("PROTRACK_ENABLE_PG_RLS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def pg_rls_force() -> bool:
    """FORCE RLS so table owners are also constrained (recommended in prod)."""
    raw = os.getenv("PROTRACK_ENABLE_PG_RLS_FORCE", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def rls_table_names() -> tuple[str, ...]:
    return tuple(sorted({*TENANT_SCOPED_TABLES, *_RLS_EXTRA_TABLES}))


def apply_rls_policies(connection: Connection, *, force: bool | None = None) -> int:
    """ENABLE RLS + create/replace tenant isolation policy. Returns tables touched."""
    use_force = pg_rls_force() if force is None else force
    touched = 0
    for table in rls_table_names():
        exists = connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": table},
        ).scalar()
        if not exists:
            continue
        has_tenant = connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t "
                "AND column_name = 'tenant_id'"
            ),
            {"t": table},
        ).scalar()
        if not has_tenant:
            continue
        connection.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        if use_force:
            connection.execute(text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        else:
            connection.execute(
                text(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
            )
        connection.execute(text(f'DROP POLICY IF EXISTS {POLICY_NAME} ON "{table}"'))
        connection.execute(
            text(
                f"""
CREATE POLICY {POLICY_NAME} ON "{table}"
FOR ALL
USING (
  current_setting('app.bypass_rls', true) = '1'
  OR tenant_id::text = NULLIF(current_setting('app.tenant_id', true), '')
)
WITH CHECK (
  current_setting('app.bypass_rls', true) = '1'
  OR tenant_id::text = NULLIF(current_setting('app.tenant_id', true), '')
)
"""
            )
        )
        touched += 1
    return touched


def set_rls_guc(
    connection: Connection,
    *,
    tenant_id: UUID | None = None,
    bypass: bool = False,
) -> None:
    tid = tenant_id or resolve_effective_tenant_id() or PROSOHM_TENANT_ID
    connection.execute(
        text("SELECT set_config('app.bypass_rls', :bypass, true)"),
        {"bypass": "1" if bypass else "0"},
    )
    connection.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tid)},
    )


def sync_session_rls(session: Session, *, bypass: bool | None = None) -> None:
    """Apply tenant/bypass GUCs on the session connection (no-op if RLS off / SQLite)."""
    if not pg_rls_enabled():
        return
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    use_bypass = tenant_filter_skipped() if bypass is None else bypass
    # Ensure a transaction so SET LOCAL (via set_config third arg true) sticks.
    connection = session.connection()
    set_rls_guc(
        connection,
        tenant_id=resolve_effective_tenant_id(),
        bypass=use_bypass,
    )


def _on_after_begin(session: Session, _transaction: Any, connection: Connection) -> None:
    if not pg_rls_enabled():
        return
    if connection.dialect.name != "postgresql":
        return
    set_rls_guc(
        connection,
        tenant_id=resolve_effective_tenant_id(),
        bypass=tenant_filter_skipped(),
    )


def register_pg_rls_session_hooks() -> None:
    """Idempotent Session.after_begin hook for GUC binding."""
    global _after_begin_registered
    if _after_begin_registered:
        return
    event.listen(Session, "after_begin", _on_after_begin)
    _after_begin_registered = True


def ensure_pg_rls_on_engine(engine: Engine) -> None:
    """Startup: install policies when enabled on Postgres."""
    if not pg_rls_enabled():
        return
    if engine.dialect.name != "postgresql":
        logger.info("PG RLS enabled in config but dialect is %s — skipping", engine.dialect.name)
        return
    with engine.begin() as connection:
        # Bypass while installing policies / reading catalogs
        set_rls_guc(connection, tenant_id=PROSOHM_TENANT_ID, bypass=True)
        count = apply_rls_policies(connection)
    logger.info("PG RLS policies applied on %s tables (force=%s)", count, pg_rls_force())
