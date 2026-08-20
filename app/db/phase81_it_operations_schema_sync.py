"""Phase 81 — IT Operations module tables."""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    Computer,
    IPAddress,
    IPAssignmentHistory,
    ITSettings,
    ITUserAccount,
    Network,
)

DEFAULT_ASSET_TYPES = [
    ("LAPTOP", "Laptop", "computer", "PRO-LT"),
    ("DESKTOP", "Desktop", "computer", "PRO-DT"),
    ("MONITOR", "Monitor", "peripheral", "PRO-MN"),
    ("KEYBOARD", "Keyboard", "peripheral", "PRO-KB"),
    ("MOUSE", "Mouse", "peripheral", "PRO-MS"),
    ("HEADSET", "Headset", "peripheral", "PRO-HS"),
    ("SERVER", "Server", "network_equipment", "PRO-SV"),
    ("SWITCH", "Network Switch", "network_equipment", "PRO-SW"),
    ("ROUTER", "Router", "network_equipment", "PRO-RT"),
    ("OTHER", "Other", "other", "PRO-OT"),
]


def ensure_phase81_it_operations_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ITSettings.__table__,
            AssetType.__table__,
            Asset.__table__,
            Computer.__table__,
            AssetAssignment.__table__,
            Network.__table__,
            IPAddress.__table__,
            IPAssignmentHistory.__table__,
            ITUserAccount.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        if session.query(ITSettings).count() == 0:
            session.add(
                ITSettings(
                    asset_numbering_pattern="{prefix}-{seq:04d}",
                    computer_naming_pattern="PRO-{type}{seq:03d}",
                    ip_allocation_strategy="sequential",
                    next_asset_seq=1,
                    next_computer_seq=1,
                )
            )
        if session.query(AssetType).count() == 0:
            for code, name, category, prefix in DEFAULT_ASSET_TYPES:
                session.add(
                    AssetType(
                        code=code,
                        name=name,
                        category=category,
                        numbering_prefix=prefix,
                        is_active=True,
                    )
                )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
