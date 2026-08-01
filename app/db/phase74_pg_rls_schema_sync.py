"""Phase 74 — optional PostgreSQL RLS policies (R10).

No-op unless ``PROTRACK_ENABLE_PG_RLS=true`` and dialect is postgresql.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.pg_rls import ensure_pg_rls_on_engine, register_pg_rls_session_hooks


def ensure_phase74_pg_rls_foundation(engine: Engine) -> None:
    register_pg_rls_session_hooks()
    ensure_pg_rls_on_engine(engine)
