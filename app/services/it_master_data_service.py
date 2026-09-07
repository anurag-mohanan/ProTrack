"""IT cascading master data: categories, types, makes, models, suppliers."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.it_operations import (
    Asset,
    AssetCategory,
    AssetMake,
    AssetMakeTypeLink,
    AssetModel,
    AssetType,
    ITSupplier,
)
from app.models.models import User


def normalize_master_name(value: str) -> str:
    return " ".join((value or "").strip().split()).casefold()


def display_name(value: str) -> str:
    return " ".join((value or "").strip().split())


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def list_categories(db: Session, *, active_only: bool = True) -> list[AssetCategory]:
    stmt = select(AssetCategory).order_by(AssetCategory.name)
    if active_only:
        stmt = stmt.where(AssetCategory.is_active.is_(True))
    return list(db.scalars(stmt).all())


def get_or_create_category(
    db: Session, *, code: str | None = None, name: str, actor: User | None = None
) -> AssetCategory:
    name_clean = display_name(name)
    if not name_clean:
        raise ProTrackValidationError("Category name is required.")
    code_n = (code or name_clean).strip().lower().replace(" ", "_")
    existing = db.scalar(select(AssetCategory).where(AssetCategory.code == code_n))
    if existing is not None:
        return existing
    # Also match by normalized name
    for row in list_categories(db, active_only=False):
        if normalize_master_name(row.name) == normalize_master_name(name_clean):
            return row
    row = AssetCategory(
        id=uuid4(),
        code=code_n[:40],
        name=name_clean,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def category_to_dict(row: AssetCategory, *, usage: int = 0) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "is_active": row.is_active,
        "notes": row.notes,
        "usage_count": usage,
    }


# ---------------------------------------------------------------------------
# Types (filtered by category)
# ---------------------------------------------------------------------------


def list_types_for_category(
    db: Session, *, category: str | None = None, active_only: bool = True
) -> list[AssetType]:
    stmt = select(AssetType).order_by(AssetType.name)
    if active_only:
        stmt = stmt.where(AssetType.is_active.is_(True))
    if category:
        stmt = stmt.where(AssetType.category == category.strip().lower())
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Makes
# ---------------------------------------------------------------------------


def list_makes_for_type(
    db: Session, *, asset_type_id: UUID | None = None, active_only: bool = True
) -> list[AssetMake]:
    if asset_type_id is None:
        stmt = select(AssetMake).order_by(AssetMake.name)
        if active_only:
            stmt = stmt.where(AssetMake.is_active.is_(True))
        return list(db.scalars(stmt).all())
    stmt = (
        select(AssetMake)
        .join(AssetMakeTypeLink, AssetMakeTypeLink.make_id == AssetMake.id)
        .where(AssetMakeTypeLink.asset_type_id == asset_type_id)
        .order_by(AssetMake.name)
    )
    if active_only:
        stmt = stmt.where(AssetMake.is_active.is_(True))
    return list(db.scalars(stmt).all())


def get_or_create_make(
    db: Session,
    *,
    name: str,
    asset_type_id: UUID | None = None,
) -> AssetMake:
    name_clean = display_name(name)
    if not name_clean:
        raise ProTrackValidationError("Make / brand name is required.")
    norm = normalize_master_name(name_clean)
    make = db.scalar(select(AssetMake).where(AssetMake.normalized_name == norm))
    if make is None:
        make = AssetMake(
            id=uuid4(),
            name=name_clean,
            normalized_name=norm,
            is_active=True,
        )
        db.add(make)
        db.flush()
    if asset_type_id is not None:
        link = db.scalar(
            select(AssetMakeTypeLink).where(
                AssetMakeTypeLink.make_id == make.id,
                AssetMakeTypeLink.asset_type_id == asset_type_id,
            )
        )
        if link is None:
            if db.get(AssetType, asset_type_id) is None:
                raise ProTrackValidationError("Asset type not found.")
            db.add(
                AssetMakeTypeLink(
                    id=uuid4(),
                    make_id=make.id,
                    asset_type_id=asset_type_id,
                )
            )
            db.flush()
    return make


def make_to_dict(row: AssetMake, *, usage: int = 0) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "is_active": row.is_active,
        "notes": row.notes,
        "usage_count": usage,
    }


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def list_models_for_context(
    db: Session,
    *,
    make_id: UUID | None = None,
    asset_type_id: UUID | None = None,
    active_only: bool = True,
) -> list[AssetModel]:
    stmt = select(AssetModel).order_by(AssetModel.name)
    if make_id is not None:
        stmt = stmt.where(AssetModel.make_id == make_id)
    if asset_type_id is not None:
        stmt = stmt.where(AssetModel.asset_type_id == asset_type_id)
    if active_only:
        stmt = stmt.where(AssetModel.is_active.is_(True))
    return list(db.scalars(stmt).all())


def get_or_create_model(
    db: Session,
    *,
    name: str,
    make_id: UUID,
    asset_type_id: UUID,
) -> AssetModel:
    name_clean = display_name(name)
    if not name_clean:
        raise ProTrackValidationError("Model name is required.")
    if db.get(AssetMake, make_id) is None:
        raise ProTrackValidationError("Make not found.")
    if db.get(AssetType, asset_type_id) is None:
        raise ProTrackValidationError("Asset type not found.")
    # Ensure make↔type link
    get_or_create_make(
        db,
        name=db.get(AssetMake, make_id).name,  # type: ignore[union-attr]
        asset_type_id=asset_type_id,
    )
    norm = normalize_master_name(name_clean)
    model = db.scalar(
        select(AssetModel).where(
            AssetModel.make_id == make_id,
            AssetModel.asset_type_id == asset_type_id,
            AssetModel.normalized_name == norm,
        )
    )
    if model is not None:
        return model
    model = AssetModel(
        id=uuid4(),
        make_id=make_id,
        asset_type_id=asset_type_id,
        name=name_clean,
        normalized_name=norm,
        is_active=True,
    )
    db.add(model)
    db.flush()
    return model


def model_to_dict(row: AssetModel, *, usage: int = 0) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "make_id": row.make_id,
        "asset_type_id": row.asset_type_id,
        "is_active": row.is_active,
        "notes": row.notes,
        "usage_count": usage,
    }


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


def list_suppliers(db: Session, *, active_only: bool = True, search: str | None = None) -> list[ITSupplier]:
    stmt = select(ITSupplier).order_by(ITSupplier.name)
    if active_only:
        stmt = stmt.where(ITSupplier.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(ITSupplier.name.ilike(like))
    return list(db.scalars(stmt).all())


def get_or_create_supplier(db: Session, *, name: str, **extra) -> ITSupplier:
    name_clean = display_name(name)
    if not name_clean:
        raise ProTrackValidationError("Supplier name is required.")
    norm = normalize_master_name(name_clean)
    for row in db.scalars(select(ITSupplier)).all():
        if normalize_master_name(row.name) == norm:
            return row
    row = ITSupplier(
        id=uuid4(),
        name=name_clean,
        website=extra.get("website"),
        phone=extra.get("phone"),
        email=extra.get("email"),
        address=extra.get("address"),
        products=extra.get("products"),
        notes=extra.get("notes"),
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def supplier_to_dict(row: ITSupplier, *, usage: int = 0) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "website": row.website,
        "phone": row.phone,
        "email": row.email,
        "address": row.address,
        "products": row.products,
        "notes": row.notes,
        "is_active": row.is_active,
        "usage_count": usage,
    }


def asset_type_to_dict(row: AssetType, *, usage: int = 0) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "category": row.category,
        "numbering_prefix": row.numbering_prefix,
        "is_active": row.is_active,
        "usage_count": usage,
    }


# ---------------------------------------------------------------------------
# Activate / deactivate + merge (referenced rows keep their FK for history)
# ---------------------------------------------------------------------------

MASTER_MODELS = {
    "categories": AssetCategory,
    "types": AssetType,
    "makes": AssetMake,
    "models": AssetModel,
    "suppliers": ITSupplier,
}
MASTER_KIND_ALIASES = {
    "category": "categories",
    "type": "types",
    "asset_type": "types",
    "asset_types": "types",
    "make": "makes",
    "model": "models",
    "supplier": "suppliers",
}


def normalize_master_kind(kind: str) -> str:
    key = (kind or "").strip().lower()
    key = MASTER_KIND_ALIASES.get(key, key)
    if key not in MASTER_MODELS:
        raise ProTrackValidationError(
            f"Unknown master kind '{kind}'. Allowed: {', '.join(sorted(MASTER_MODELS))}"
        )
    return key


def set_master_active(db: Session, kind: str, master_id: UUID, is_active: bool):
    """
    Soft activate / deactivate a master record.

    Never a hard delete: assets that already reference the master keep their FK
    so history stays intact. Deactivating only hides it from new selections.
    """
    key = normalize_master_kind(kind)
    row = db.get(MASTER_MODELS[key], master_id)
    if row is None:
        raise ProTrackValidationError(f"{key[:-1].replace('_', ' ').capitalize()} not found.")
    row.is_active = bool(is_active)
    db.add(row)
    db.flush()
    return row


def master_to_dict(db: Session, kind: str, row) -> dict:
    key = normalize_master_kind(kind)
    counts = usage_counts(db)
    if key == "categories":
        return category_to_dict(row)
    if key == "types":
        return asset_type_to_dict(row, usage=counts["types"].get(str(row.id), 0))
    if key == "makes":
        return make_to_dict(row, usage=counts["makes"].get(str(row.id), 0))
    if key == "models":
        return model_to_dict(row, usage=counts["models"].get(str(row.id), 0))
    return supplier_to_dict(row, usage=counts["suppliers"].get(str(row.id), 0))


def merge_makes(db: Session, source_id: UUID, target_id: UUID) -> dict:
    """Move assets + models from source make onto target, then deactivate source."""
    if source_id == target_id:
        raise ProTrackValidationError("Source and target make must be different.")
    source = db.get(AssetMake, source_id)
    target = db.get(AssetMake, target_id)
    if source is None or target is None:
        raise ProTrackValidationError("Make not found.")

    models_moved = 0
    models_merged = 0
    for model in db.scalars(select(AssetModel).where(AssetModel.make_id == source.id)).all():
        twin = db.scalar(
            select(AssetModel).where(
                AssetModel.make_id == target.id,
                AssetModel.asset_type_id == model.asset_type_id,
                AssetModel.normalized_name == model.normalized_name,
            )
        )
        if twin is None:
            model.make_id = target.id
            db.add(model)
            models_moved += 1
            continue
        for asset in db.scalars(select(Asset).where(Asset.model_id == model.id)).all():
            asset.model_id = twin.id
            asset.model = twin.name
            db.add(asset)
        model.is_active = False
        db.add(model)
        models_merged += 1

    assets_moved = 0
    for asset in db.scalars(select(Asset).where(Asset.make_id == source.id)).all():
        asset.make_id = target.id
        asset.make = target.name
        db.add(asset)
        assets_moved += 1

    links_added = 0
    for link in db.scalars(
        select(AssetMakeTypeLink).where(AssetMakeTypeLink.make_id == source.id)
    ).all():
        existing = db.scalar(
            select(AssetMakeTypeLink).where(
                AssetMakeTypeLink.make_id == target.id,
                AssetMakeTypeLink.asset_type_id == link.asset_type_id,
            )
        )
        if existing is None:
            db.add(
                AssetMakeTypeLink(
                    id=uuid4(),
                    make_id=target.id,
                    asset_type_id=link.asset_type_id,
                )
            )
            links_added += 1

    source.is_active = False
    db.add(source)
    db.flush()
    return {
        "source_id": source.id,
        "source_name": source.name,
        "target_id": target.id,
        "target_name": target.name,
        "assets_moved": assets_moved,
        "models_moved": models_moved,
        "models_merged": models_merged,
        "type_links_added": links_added,
        "message": f"Merged '{source.name}' into '{target.name}'. Source make deactivated.",
    }


def merge_models(db: Session, source_id: UUID, target_id: UUID) -> dict:
    """Move assets from source model onto target, then deactivate source."""
    if source_id == target_id:
        raise ProTrackValidationError("Source and target model must be different.")
    source = db.get(AssetModel, source_id)
    target = db.get(AssetModel, target_id)
    if source is None or target is None:
        raise ProTrackValidationError("Model not found.")
    if source.asset_type_id != target.asset_type_id:
        raise ProTrackValidationError("Models must share the same asset type to merge.")

    target_make = db.get(AssetMake, target.make_id)
    assets_moved = 0
    for asset in db.scalars(select(Asset).where(Asset.model_id == source.id)).all():
        asset.model_id = target.id
        asset.model = target.name
        asset.make_id = target.make_id
        if target_make is not None:
            asset.make = target_make.name
        db.add(asset)
        assets_moved += 1

    source.is_active = False
    db.add(source)
    db.flush()
    return {
        "source_id": source.id,
        "source_name": source.name,
        "target_id": target.id,
        "target_name": target.name,
        "assets_moved": assets_moved,
        "message": f"Merged '{source.name}' into '{target.name}'. Source model deactivated.",
    }


# ---------------------------------------------------------------------------
# Resolve masters when saving an asset (learn forever)
# ---------------------------------------------------------------------------


def resolve_masters_for_asset(
    db: Session,
    *,
    asset_type_id: UUID,
    make: str | None = None,
    model: str | None = None,
    make_id: UUID | None = None,
    model_id: UUID | None = None,
    supplier_id: UUID | None = None,
    supplier_name: str | None = None,
) -> dict:
    """Validate cascade and ensure master records exist. Returns ids + display text."""
    asset_type = db.get(AssetType, asset_type_id)
    if asset_type is None or not asset_type.is_active:
        raise ProTrackValidationError("Asset type not found or inactive.")

    resolved_make_id = make_id
    resolved_model_id = model_id
    make_text = (make or "").strip() or None
    model_text = (model or "").strip() or None

    if resolved_make_id is not None:
        make_row = db.get(AssetMake, resolved_make_id)
        if make_row is None or not make_row.is_active:
            raise ProTrackValidationError("Make not found or inactive.")
        get_or_create_make(db, name=make_row.name, asset_type_id=asset_type_id)
        make_text = make_row.name
    elif make_text:
        make_row = get_or_create_make(db, name=make_text, asset_type_id=asset_type_id)
        resolved_make_id = make_row.id
        make_text = make_row.name

    if resolved_model_id is not None:
        model_row = db.get(AssetModel, resolved_model_id)
        if model_row is None or not model_row.is_active:
            raise ProTrackValidationError("Model not found or inactive.")
        if resolved_make_id and model_row.make_id != resolved_make_id:
            raise ProTrackValidationError("Model does not belong to the selected make.")
        if model_row.asset_type_id != asset_type_id:
            raise ProTrackValidationError("Model does not belong to the selected asset type.")
        model_text = model_row.name
        resolved_make_id = model_row.make_id
        make_text = db.get(AssetMake, model_row.make_id).name  # type: ignore[union-attr]
    elif model_text:
        if not resolved_make_id:
            raise ProTrackValidationError("Make is required when specifying a model.")
        model_row = get_or_create_model(
            db, name=model_text, make_id=resolved_make_id, asset_type_id=asset_type_id
        )
        resolved_model_id = model_row.id
        model_text = model_row.name

    resolved_supplier_id = supplier_id
    if resolved_supplier_id is None and supplier_name:
        resolved_supplier_id = get_or_create_supplier(db, name=supplier_name).id
    if resolved_supplier_id is not None and db.get(ITSupplier, resolved_supplier_id) is None:
        raise ProTrackValidationError("Supplier not found.")

    # Ensure category master exists for this type's category
    get_or_create_category(db, code=asset_type.category, name=asset_type.category.replace("_", " "))

    return {
        "make_id": resolved_make_id,
        "model_id": resolved_model_id,
        "make": make_text,
        "model": model_text,
        "supplier_id": resolved_supplier_id,
    }


def usage_counts(db: Session) -> dict:
    make_counts = {
        str(r[0]): int(r[1])
        for r in db.execute(
            select(Asset.make_id, func.count())
            .where(Asset.is_deleted.is_(False), Asset.make_id.is_not(None))
            .group_by(Asset.make_id)
        ).all()
    }
    model_counts = {
        str(r[0]): int(r[1])
        for r in db.execute(
            select(Asset.model_id, func.count())
            .where(Asset.is_deleted.is_(False), Asset.model_id.is_not(None))
            .group_by(Asset.model_id)
        ).all()
    }
    supplier_counts = {
        str(r[0]): int(r[1])
        for r in db.execute(
            select(Asset.supplier_id, func.count())
            .where(Asset.is_deleted.is_(False), Asset.supplier_id.is_not(None))
            .group_by(Asset.supplier_id)
        ).all()
    }
    type_counts = {
        str(r[0]): int(r[1])
        for r in db.execute(
            select(Asset.asset_type_id, func.count())
            .where(Asset.is_deleted.is_(False))
            .group_by(Asset.asset_type_id)
        ).all()
    }
    return {
        "makes": make_counts,
        "models": model_counts,
        "suppliers": supplier_counts,
        "types": type_counts,
    }
