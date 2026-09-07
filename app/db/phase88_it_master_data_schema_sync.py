"""Phase 88 — IT cascading master data (categories, makes, models) + asset FKs."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.it_operations import (
    Asset,
    AssetCategory,
    AssetMake,
    AssetMakeTypeLink,
    AssetModel,
    AssetType,
)


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table_name},
        ).fetchone()
    return row is not None


def _add_column(engine: Engine, table: str, name: str, ddl: str) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, table):
                return
            if not _sqlite_has_column(engine, table, name):
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        else:
            pg_ddl = ddl.replace("CHAR(36)", "UUID")
            connection.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_ddl}")
            )


def _normalize(value: str) -> str:
    return " ".join((value or "").strip().split()).casefold()


CATEGORY_LABELS = {
    "computer": "IT Hardware — Computers",
    "peripheral": "IT Hardware — Peripherals",
    "network_equipment": "Network Equipment",
    "other": "Other IT Assets",
}


def _backfill_masters(engine: Engine) -> None:
    """Seed categories from types; learn makes/models from existing free-text assets."""
    from uuid import uuid4

    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db: Session = SessionLocal()
    try:
        # Categories from existing asset types
        type_cats = {
            (t.category or "other").strip().lower()
            for t in db.query(AssetType).all()
            if (t.category or "").strip()
        }
        for code in sorted(type_cats | set(CATEGORY_LABELS)):
            code_n = code.strip().lower() or "other"
            existing = (
                db.query(AssetCategory).filter(AssetCategory.code == code_n).first()
            )
            if existing is None:
                db.add(
                    AssetCategory(
                        id=uuid4(),
                        code=code_n,
                        name=CATEGORY_LABELS.get(code_n, code_n.replace("_", " ").title()),
                        is_active=True,
                    )
                )
        db.flush()

        # Learn makes/models from free-text (non-destructive)
        for asset in db.query(Asset).filter(Asset.is_deleted.is_(False)).all():
            make_raw = (asset.make or "").strip()
            model_raw = (asset.model or "").strip()
            if not make_raw:
                continue
            norm = _normalize(make_raw)
            make = (
                db.query(AssetMake).filter(AssetMake.normalized_name == norm).first()
            )
            if make is None:
                make = AssetMake(
                    id=uuid4(),
                    name=make_raw,
                    normalized_name=norm,
                    is_active=True,
                )
                db.add(make)
                db.flush()
            if getattr(asset, "make_id", None) is None:
                asset.make_id = make.id
            link = (
                db.query(AssetMakeTypeLink)
                .filter(
                    AssetMakeTypeLink.make_id == make.id,
                    AssetMakeTypeLink.asset_type_id == asset.asset_type_id,
                )
                .first()
            )
            if link is None:
                db.add(
                    AssetMakeTypeLink(
                        id=uuid4(),
                        make_id=make.id,
                        asset_type_id=asset.asset_type_id,
                    )
                )
            if model_raw:
                mnorm = _normalize(model_raw)
                model = (
                    db.query(AssetModel)
                    .filter(
                        AssetModel.make_id == make.id,
                        AssetModel.asset_type_id == asset.asset_type_id,
                        AssetModel.normalized_name == mnorm,
                    )
                    .first()
                )
                if model is None:
                    model = AssetModel(
                        id=uuid4(),
                        make_id=make.id,
                        asset_type_id=asset.asset_type_id,
                        name=model_raw,
                        normalized_name=mnorm,
                        is_active=True,
                    )
                    db.add(model)
                    db.flush()
                if getattr(asset, "model_id", None) is None:
                    asset.model_id = model.id
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ensure_phase88_it_master_data_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            AssetCategory.__table__,
            AssetMake.__table__,
            AssetMakeTypeLink.__table__,
            AssetModel.__table__,
        ],
    )
    _add_column(engine, "assets", "make_id", "CHAR(36)")
    _add_column(engine, "assets", "model_id", "CHAR(36)")
    try:
        _backfill_masters(engine)
    except Exception:
        # Backfill is best-effort; tables still usable empty
        pass
