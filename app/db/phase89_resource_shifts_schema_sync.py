"""Phase 89 — Resource Planning shifts (masters + effective-dated assignments)."""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.resource_shifts import ResourceShift, ResourceShiftAssignment
from app.services.resource_shift_service import seed_default_shifts


def ensure_phase89_resource_shifts_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ResourceShift.__table__,
            ResourceShiftAssignment.__table__,
        ],
    )
    try:
        _seed(engine)
    except Exception:
        # Seeding is best-effort; the tables are usable empty.
        pass


def _seed(engine: Engine) -> None:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        seed_default_shifts(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
