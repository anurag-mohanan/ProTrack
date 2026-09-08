"""Phase 95 — Durable asset-number history (never rewrite or recycle numbers)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.it_operations import Asset, AssetNumberHistory
from app.models.models import User


def ensure_phase95_it_asset_number_history_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[AssetNumberHistory.__table__],
    )
    _backfill_current_numbers(engine)


def _backfill_current_numbers(engine: Engine) -> None:
    """Open a current-number period for assets that have none yet.

    If ``legacy_asset_number`` differs from the current number, record it as a
    closed prior period. Rows are never rewritten after insert.
    """
    with Session(engine) as db:
        actor = db.scalar(
            select(User).where(User.is_deleted.is_(False), User.is_active.is_(True)).limit(1)
        )
        if actor is None:
            return
        open_ids = set(
            db.scalars(
                select(AssetNumberHistory.asset_id).where(
                    AssetNumberHistory.effective_to.is_(None)
                )
            ).all()
        )
        assets = list(db.scalars(select(Asset)).all())
        today = date.today()
        for asset in assets:
            if asset.id in open_ids:
                continue
            start = asset.created_at.date() if asset.created_at else today
            legacy = (asset.legacy_asset_number or "").strip() or None
            current = (asset.asset_number or "").strip()
            if not current:
                continue
            if legacy and legacy != current:
                db.add(
                    AssetNumberHistory(
                        asset_id=asset.id,
                        asset_number=legacy,
                        effective_from=start,
                        effective_to=start,
                        changed_by_user_id=actor.id,
                        reason="backfill_legacy",
                    )
                )
            db.add(
                AssetNumberHistory(
                    asset_id=asset.id,
                    asset_number=current,
                    effective_from=start,
                    effective_to=None,
                    changed_by_user_id=actor.id,
                    reason="backfill_current",
                )
            )
        db.commit()
