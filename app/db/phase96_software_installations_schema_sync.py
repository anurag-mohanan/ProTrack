"""Phase 96 — Software installation history (installed vs licensed)."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from app.db.base import Base
from app.models.it_operations import SoftwareInstallation


def ensure_phase96_software_installations_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[SoftwareInstallation.__table__],
    )
