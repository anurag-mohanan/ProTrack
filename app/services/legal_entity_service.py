"""Legal entity prep helpers (R4, single-tenant)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enterprise import LegalEntity


def ensure_default_legal_entity(db: Session) -> LegalEntity:
    existing = db.scalar(select(LegalEntity).where(LegalEntity.is_default.is_(True)).limit(1))
    if existing:
        return existing
    any_row = db.scalar(select(LegalEntity).limit(1))
    if any_row:
        any_row.is_default = True
        db.add(any_row)
        db.commit()
        db.refresh(any_row)
        return any_row
    row = LegalEntity(
        code="PROSOHM",
        name="Prosohm",
        currency_code="INR",
        is_default=True,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_legal_entities(db: Session) -> list[LegalEntity]:
    ensure_default_legal_entity(db)
    return list(
        db.scalars(
            select(LegalEntity).order_by(LegalEntity.is_default.desc(), LegalEntity.name)
        ).all()
    )
