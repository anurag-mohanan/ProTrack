"""Phase 97 — Durable computer-name history (never rewrite names)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.it_operations import Computer, ComputerNameHistory
from app.models.models import User


def ensure_phase97_it_computer_name_history_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[ComputerNameHistory.__table__],
    )
    _backfill_current_names(engine)


def _backfill_current_names(engine: Engine) -> None:
    with Session(engine) as db:
        actor = db.scalar(
            select(User).where(User.is_deleted.is_(False), User.is_active.is_(True)).limit(1)
        )
        if actor is None:
            return
        open_ids = set(
            db.scalars(
                select(ComputerNameHistory.computer_id).where(
                    ComputerNameHistory.effective_to.is_(None)
                )
            ).all()
        )
        today = date.today()
        for computer in db.scalars(select(Computer)).all():
            if computer.id in open_ids:
                continue
            name = (computer.computer_name or "").strip()
            if not name:
                continue
            start = computer.created_at.date() if computer.created_at else today
            db.add(
                ComputerNameHistory(
                    computer_id=computer.id,
                    computer_name=name,
                    effective_from=start,
                    effective_to=None,
                    changed_by_user_id=actor.id,
                    reason="backfill_current",
                )
            )
        db.commit()
