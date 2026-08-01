"""R10 optional PG RLS helpers (SQLite no-op)."""

import os

from app.db import pg_rls
from app.db.phase74_pg_rls_schema_sync import ensure_phase74_pg_rls_foundation
from app.db.tenant_scoped_tables import TENANT_SCOPED_TABLES
from app.models.commercial import PROSOHM_TENANT_ID


def test_pg_rls_disabled_by_default():
    assert pg_rls.pg_rls_enabled() is False


def test_rls_table_catalog_includes_core_and_flags():
    names = pg_rls.rls_table_names()
    assert "projects" in names
    assert "users" in names
    assert "api_keys" in names
    assert "feature_flags" in names
    assert "tenants" not in names
    assert set(TENANT_SCOPED_TABLES).issubset(set(names))


def test_phase74_noop_on_sqlite(test_engine):
    # Default env: RLS off — still safe to call
    ensure_phase74_pg_rls_foundation(test_engine)
    os.environ["PROTRACK_ENABLE_PG_RLS"] = "true"
    try:
        # SQLite must not raise even if flag on
        ensure_phase74_pg_rls_foundation(test_engine)
        from app.db.session import SessionLocal
        from app.db.pg_rls import sync_session_rls

        db = SessionLocal()
        try:
            sync_session_rls(db)
        finally:
            db.close()
    finally:
        os.environ.pop("PROTRACK_ENABLE_PG_RLS", None)


def test_sync_session_rls_respects_prosohm_default(test_engine):
    from app.core.request_context import set_tenant_id
    from app.db.pg_rls import sync_session_rls
    from app.db.session import SessionLocal

    set_tenant_id(PROSOHM_TENANT_ID)
    db = SessionLocal()
    try:
        sync_session_rls(db)  # no-op without flag / on sqlite
    finally:
        db.close()
