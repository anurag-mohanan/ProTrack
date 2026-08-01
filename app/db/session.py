import os
from typing import Any

from app.db.base import create_engine, sessionmaker
from app.db.pg_rls import register_pg_rls_session_hooks, sync_session_rls
from app.db.tenant_filter import register_tenant_filter

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./protrack.db")

_engine_kwargs: dict[str, Any] = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# R10 M1c — automatic SELECT tenant isolation (default Prosohm).
register_tenant_filter()
# R10 optional PG RLS — GUC binding when PROTRACK_ENABLE_PG_RLS=true.
register_pg_rls_session_hooks()


def get_db():
    db = SessionLocal()
    try:
        sync_session_rls(db)
        yield db
    finally:
        db.close()
