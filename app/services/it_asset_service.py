"""IT asset, computer, and assignment workflows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import MODULE_IT_OPERATIONS
from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetCustomerReturn,
    AssetType,
    Computer,
    ITSettings,
)
from app.models.models import Customer, User
from app.services.activity_service import log_activity

MODULE = MODULE_IT_OPERATIONS
ASSET_STATUSES = frozenset(
    {
        "available",
        "assigned",
        "maintenance",
        "awaiting_return",
        "returned_to_customer",
        "lost",
        "damaged",
        "retired",
        "disposed",
    }
)
CURRENT_INVENTORY_STATUSES = frozenset(
    {"available", "assigned", "maintenance", "awaiting_return"}
)
PURCHASED_BY_CODES = frozenset(
    {"organization", "customer", "vendor", "leased", "other", "unknown"}
)


def _validate_ownership(
    *,
    purchased_by: str,
    owner_customer_id: UUID | None,
) -> None:
    if purchased_by not in PURCHASED_BY_CODES:
        raise ProTrackValidationError(
            f"Invalid purchased_by '{purchased_by}'. "
            f"Allowed: {', '.join(sorted(PURCHASED_BY_CODES))}"
        )
    if purchased_by == "customer" and owner_customer_id is None:
        raise ProTrackValidationError(
            "owner_customer_id is required when purchased_by is 'customer'."
        )
    if purchased_by != "customer" and owner_customer_id is not None:
        raise ProTrackValidationError(
            "owner_customer_id is only allowed when purchased_by is 'customer'."
        )


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def get_or_create_settings(db: Session) -> ITSettings:
    settings = db.scalar(select(ITSettings).limit(1))
    if settings is not None:
        return settings
    settings = ITSettings(
        id=uuid4(),
        asset_numbering_pattern="{prefix}-{seq:04d}",
        computer_naming_pattern="PRO-{type}{seq:03d}",
        ip_allocation_strategy="sequential",
        next_asset_seq=1,
        next_computer_seq=1,
    )
    db.add(settings)
    db.flush()
    return settings


def _locked_settings(db: Session) -> ITSettings:
    settings = db.scalar(select(ITSettings).with_for_update().limit(1))
    if settings is None:
        get_or_create_settings(db)
        settings = db.scalar(select(ITSettings).with_for_update().limit(1))
    if settings is None:
        raise ProTrackValidationError("IT settings could not be initialized.")
    return settings


def next_asset_number(db: Session, asset_type: AssetType) -> str:
    settings = _locked_settings(db)
    seq = settings.next_asset_seq or 1
    prefix = (asset_type.numbering_prefix or asset_type.code or "ASSET").strip()
    pattern = settings.asset_numbering_pattern or "{prefix}-{seq:04d}"
    try:
        number = pattern.format(prefix=prefix, seq=seq, type=asset_type.code or "")
    except (KeyError, ValueError) as exc:
        raise ProTrackValidationError(
            f"Invalid asset numbering pattern: {pattern}"
        ) from exc
    settings.next_asset_seq = seq + 1
    db.add(settings)
    db.flush()
    return number.strip()


def next_computer_name(db: Session, type_code: str) -> str:
    settings = _locked_settings(db)
    seq = settings.next_computer_seq or 1
    code = (type_code or "PC").strip().upper()[:6]
    pattern = settings.computer_naming_pattern or "PRO-{type}{seq:03d}"
    try:
        name = pattern.format(type=code, seq=seq, org="PRO", prefix="PRO")
    except (KeyError, ValueError) as exc:
        raise ProTrackValidationError(
            f"Invalid computer naming pattern: {pattern}"
        ) from exc
    settings.next_computer_seq = seq + 1
    db.add(settings)
    db.flush()
    return name.strip()


def list_asset_types(db: Session, *, active_only: bool = False) -> list[AssetType]:
    stmt = select(AssetType).order_by(AssetType.name)
    if active_only:
        stmt = stmt.where(AssetType.is_active.is_(True))
    return list(db.scalars(stmt).all())


def create_asset_type(
    db: Session,
    *,
    code: str,
    name: str,
    category: str = "other",
    numbering_prefix: str | None = None,
    is_active: bool = True,
    actor: User,
) -> AssetType:
    code_norm = code.strip().upper().replace(" ", "_")
    if not code_norm:
        raise ProTrackValidationError("Asset type code is required.")
    existing = db.scalar(select(AssetType).where(AssetType.code == code_norm))
    if existing is not None:
        raise ProTrackValidationError(f"Asset type code '{code_norm}' already exists.")
    row = AssetType(
        id=uuid4(),
        code=code_norm,
        name=name.strip(),
        category=(category or "other").strip().lower(),
        numbering_prefix=(numbering_prefix or "").strip() or None,
        is_active=bool(is_active),
    )
    db.add(row)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset_type,
        entity_id=row.id,
        action=ActivityAction.it_asset_created,
        new_value={"code": row.code, "name": row.name},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


def update_asset_type(
    db: Session,
    asset_type: AssetType,
    *,
    actor: User,
    code: str | None = None,
    name: str | None = None,
    category: str | None = None,
    numbering_prefix: str | None = None,
    is_active: bool | None = None,
) -> AssetType:
    old = {"code": asset_type.code, "name": asset_type.name, "is_active": asset_type.is_active}
    if code is not None:
        code_norm = code.strip().upper().replace(" ", "_")
        if not code_norm:
            raise ProTrackValidationError("Asset type code is required.")
        clash = db.scalar(
            select(AssetType).where(AssetType.code == code_norm, AssetType.id != asset_type.id)
        )
        if clash is not None:
            raise ProTrackValidationError(f"Asset type code '{code_norm}' already exists.")
        asset_type.code = code_norm
    if name is not None:
        asset_type.name = name.strip()
    if category is not None:
        asset_type.category = category.strip().lower()
    if numbering_prefix is not None:
        asset_type.numbering_prefix = numbering_prefix.strip() or None
    if is_active is not None:
        asset_type.is_active = bool(is_active)
    db.add(asset_type)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset_type,
        entity_id=asset_type.id,
        action=ActivityAction.it_asset_updated,
        old_value=old,
        new_value={"code": asset_type.code, "name": asset_type.name, "is_active": asset_type.is_active},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(asset_type)
    return asset_type


def get_current_assignment(db: Session, asset_id: UUID) -> AssetAssignment | None:
    return db.scalar(
        select(AssetAssignment)
        .where(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.returned_date.is_(None),
        )
        .order_by(AssetAssignment.assigned_date.desc())
        .limit(1)
    )


def list_assets(
    db: Session,
    *,
    status: str | None = None,
    asset_type_id: UUID | None = None,
    search: str | None = None,
    inventory_scope: str = "current",
    purchased_by: str | None = None,
    owner_customer_id: UUID | None = None,
    customer_used_for_id: UUID | None = None,
    skip: int = 0,
    limit: int = 25,
) -> tuple[list[Asset], int]:
    stmt = (
        select(Asset)
        .options(selectinload(Asset.asset_type), selectinload(Asset.assignments))
        .where(Asset.is_deleted.is_(False))
    )
    count_filters = [Asset.is_deleted.is_(False)]

    scope = (inventory_scope or "current").strip().lower()
    if status:
        stmt = stmt.where(Asset.status == status)
        count_filters.append(Asset.status == status)
    elif scope == "current":
        stmt = stmt.where(Asset.status.in_(CURRENT_INVENTORY_STATUSES))
        count_filters.append(Asset.status.in_(CURRENT_INVENTORY_STATUSES))
    elif scope == "returned":
        stmt = stmt.where(Asset.status == "returned_to_customer")
        count_filters.append(Asset.status == "returned_to_customer")
    elif scope == "historical":
        stmt = stmt.where(
            Asset.status.in_(
                ("returned_to_customer", "retired", "disposed", "lost")
            )
        )
        count_filters.append(
            Asset.status.in_(
                ("returned_to_customer", "retired", "disposed", "lost")
            )
        )
    # scope == "all": no extra status filter

    if asset_type_id:
        stmt = stmt.where(Asset.asset_type_id == asset_type_id)
        count_filters.append(Asset.asset_type_id == asset_type_id)
    if purchased_by:
        stmt = stmt.where(Asset.purchased_by == purchased_by)
        count_filters.append(Asset.purchased_by == purchased_by)
    if owner_customer_id:
        stmt = stmt.where(Asset.owner_customer_id == owner_customer_id)
        count_filters.append(Asset.owner_customer_id == owner_customer_id)
    if customer_used_for_id:
        stmt = stmt.where(Asset.customer_used_for_id == customer_used_for_id)
        count_filters.append(Asset.customer_used_for_id == customer_used_for_id)
    if search:
        q = f"%{search.strip()}%"
        search_clause = or_(
            Asset.asset_number.ilike(q),
            Asset.legacy_asset_number.ilike(q),
            Asset.serial_number.ilike(q),
            Asset.service_tag.ilike(q),
            Asset.make.ilike(q),
            Asset.model.ilike(q),
            Asset.location.ilike(q),
            Asset.description.ilike(q),
        )
        stmt = stmt.where(search_clause)
        count_filters.append(search_clause)

    count_stmt = select(Asset.id).where(*count_filters)
    total = len(list(db.scalars(count_stmt).all()))
    rows = list(
        db.scalars(stmt.order_by(Asset.asset_number).offset(skip).limit(limit)).all()
    )
    return rows, total


def get_asset(db: Session, asset_id: UUID, *, include_deleted: bool = False) -> Asset | None:
    stmt = (
        select(Asset)
        .options(
            selectinload(Asset.asset_type),
            selectinload(Asset.computer),
            selectinload(Asset.assignments),
        )
        .where(Asset.id == asset_id)
    )
    asset = db.scalar(stmt)
    if asset is None:
        return None
    if asset.is_deleted and not include_deleted:
        return None
    return asset


def create_asset(
    db: Session,
    *,
    actor: User,
    asset_type_id: UUID,
    serial_number: str | None = None,
    make: str | None = None,
    model: str | None = None,
    purchase_date: date | None = None,
    purchase_cost: Decimal | None = None,
    warranty_expiry: date | None = None,
    location: str | None = None,
    notes: str | None = None,
    legacy_asset_number: str | None = None,
    asset_number: str | None = None,
    description: str | None = None,
    service_tag: str | None = None,
    purchased_by: str = "organization",
    owner_customer_id: UUID | None = None,
    customer_used_for_id: UUID | None = None,
    supplier_id: UUID | None = None,
    invoice_number: str | None = None,
    condition: str | None = None,
    commit: bool = True,
) -> Asset:
    asset_type = db.get(AssetType, asset_type_id)
    if asset_type is None or not asset_type.is_active:
        raise ProTrackValidationError("Asset type not found or inactive.")
    _validate_ownership(purchased_by=purchased_by, owner_customer_id=owner_customer_id)
    if owner_customer_id is not None and db.get(Customer, owner_customer_id) is None:
        raise ProTrackValidationError("Owner customer not found.")
    if customer_used_for_id is not None and db.get(Customer, customer_used_for_id) is None:
        raise ProTrackValidationError("Customer used for not found.")
    preferred = (asset_number or legacy_asset_number or "").strip() or None
    if preferred:
        clash = db.scalar(
            select(Asset).where(
                Asset.is_deleted.is_(False),
                Asset.asset_number == preferred,
            )
        )
        if clash is not None:
            raise ProTrackValidationError(
                f"Asset number '{preferred}' already exists."
            )
        number = preferred
    else:
        number = next_asset_number(db, asset_type)
    asset = Asset(
        id=uuid4(),
        asset_number=number,
        legacy_asset_number=(legacy_asset_number or preferred or "").strip() or None,
        asset_type_id=asset_type.id,
        description=(description or "").strip() or None,
        serial_number=(serial_number or "").strip() or None,
        service_tag=(service_tag or "").strip() or None,
        make=(make or "").strip() or None,
        model=(model or "").strip() or None,
        status="available",
        purchased_by=purchased_by,
        owner_customer_id=owner_customer_id,
        customer_used_for_id=customer_used_for_id,
        supplier_id=supplier_id,
        invoice_number=(invoice_number or "").strip() or None,
        condition=(condition or "").strip() or None,
        purchase_date=purchase_date,
        purchase_cost=purchase_cost,
        warranty_expiry=warranty_expiry,
        location=(location or "").strip() or None,
        notes=(notes or "").strip() or None,
        is_deleted=False,
    )
    db.add(asset)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=ActivityAction.it_asset_created,
        new_value={
            "asset_number": asset.asset_number,
            "asset_type_id": str(asset_type.id),
            "purchased_by": asset.purchased_by,
            "owner_customer_id": str(owner_customer_id) if owner_customer_id else None,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(asset)
    return asset


def update_asset(
    db: Session,
    asset: Asset,
    *,
    actor: User,
    asset_type_id: UUID | None = None,
    serial_number: str | None = None,
    make: str | None = None,
    model: str | None = None,
    status: str | None = None,
    purchase_date: date | None = None,
    purchase_cost: Decimal | None = None,
    warranty_expiry: date | None = None,
    location: str | None = None,
    notes: str | None = None,
    legacy_asset_number: str | None = None,
    description: str | None = None,
    service_tag: str | None = None,
    purchased_by: str | None = None,
    owner_customer_id: UUID | None = None,
    customer_used_for_id: UUID | None = None,
    supplier_id: UUID | None = None,
    invoice_number: str | None = None,
    condition: str | None = None,
    fields_set: set[str] | None = None,
) -> Asset:
    if asset.is_deleted:
        raise ProTrackValidationError("Cannot update a deleted asset.")
    old = {
        "status": asset.status,
        "location": asset.location,
        "purchased_by": asset.purchased_by,
        "owner_customer_id": str(asset.owner_customer_id) if asset.owner_customer_id else None,
    }
    touched = fields_set or set()

    if asset_type_id is not None and ("asset_type_id" in touched or fields_set is None):
        at = db.get(AssetType, asset_type_id)
        if at is None:
            raise ProTrackValidationError("Asset type not found.")
        asset.asset_type_id = asset_type_id
    if "serial_number" in touched or (fields_set is None and serial_number is not None):
        asset.serial_number = (serial_number or "").strip() or None
    if "make" in touched or (fields_set is None and make is not None):
        asset.make = (make or "").strip() or None
    if "model" in touched or (fields_set is None and model is not None):
        asset.model = (model or "").strip() or None
    if status is not None and ("status" in touched or fields_set is None):
        if status not in ASSET_STATUSES:
            raise ProTrackValidationError(f"Invalid asset status '{status}'.")
        asset.status = status
    if "purchase_date" in touched or (fields_set is None and purchase_date is not None):
        asset.purchase_date = purchase_date
    if "purchase_cost" in touched or (fields_set is None and purchase_cost is not None):
        asset.purchase_cost = purchase_cost
    if "warranty_expiry" in touched or (fields_set is None and warranty_expiry is not None):
        asset.warranty_expiry = warranty_expiry
    if "location" in touched or (fields_set is None and location is not None):
        asset.location = (location or "").strip() or None
    if "notes" in touched or (fields_set is None and notes is not None):
        asset.notes = (notes or "").strip() or None
    if "legacy_asset_number" in touched or (
        fields_set is None and legacy_asset_number is not None
    ):
        asset.legacy_asset_number = (legacy_asset_number or "").strip() or None
    if "description" in touched or (fields_set is None and description is not None):
        asset.description = (description or "").strip() or None
    if "service_tag" in touched or (fields_set is None and service_tag is not None):
        asset.service_tag = (service_tag or "").strip() or None
    if "invoice_number" in touched or (fields_set is None and invoice_number is not None):
        asset.invoice_number = (invoice_number or "").strip() or None
    if "condition" in touched or (fields_set is None and condition is not None):
        asset.condition = (condition or "").strip() or None
    if "supplier_id" in touched or (fields_set is None and supplier_id is not None):
        asset.supplier_id = supplier_id

    next_purchased_by = asset.purchased_by
    next_owner = asset.owner_customer_id
    if purchased_by is not None and ("purchased_by" in touched or fields_set is None):
        next_purchased_by = purchased_by
    if "owner_customer_id" in touched or (
        fields_set is None and owner_customer_id is not None
    ):
        next_owner = owner_customer_id
    if (
        ("purchased_by" in touched or "owner_customer_id" in touched)
        or (
            fields_set is None
            and (purchased_by is not None or owner_customer_id is not None)
        )
    ):
        _validate_ownership(purchased_by=next_purchased_by, owner_customer_id=next_owner)
        if next_owner is not None and db.get(Customer, next_owner) is None:
            raise ProTrackValidationError("Owner customer not found.")
        asset.purchased_by = next_purchased_by
        asset.owner_customer_id = next_owner

    if "customer_used_for_id" in touched or (
        fields_set is None and customer_used_for_id is not None
    ):
        if customer_used_for_id is not None and db.get(Customer, customer_used_for_id) is None:
            raise ProTrackValidationError("Customer used for not found.")
        asset.customer_used_for_id = customer_used_for_id

    db.add(asset)
    db.flush()
    ownership_changed = old["purchased_by"] != asset.purchased_by or old[
        "owner_customer_id"
    ] != (str(asset.owner_customer_id) if asset.owner_customer_id else None)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=(
            ActivityAction.it_asset_ownership_changed
            if ownership_changed
            else ActivityAction.it_asset_updated
        ),
        old_value=old,
        new_value={
            "status": asset.status,
            "location": asset.location,
            "purchased_by": asset.purchased_by,
            "owner_customer_id": str(asset.owner_customer_id)
            if asset.owner_customer_id
            else None,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(asset)
    return asset


def soft_delete_asset(db: Session, asset: Asset, *, actor: User) -> Asset:
    if asset.is_deleted:
        return asset
    if asset.status == "returned_to_customer":
        raise ProTrackValidationError(
            "Returned customer assets must be retained in history and cannot be deleted."
        )
    open_asg = get_current_assignment(db, asset.id)
    if open_asg is not None:
        raise ProTrackValidationError("Return the asset before deleting it.")
    asset.is_deleted = True
    if asset.status == "available":
        asset.status = "retired"
    db.add(asset)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=ActivityAction.it_asset_deleted,
        new_value={"asset_number": asset.asset_number},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(asset)
    return asset


def assign_asset(
    db: Session,
    asset: Asset,
    *,
    user_id: UUID,
    by_user: User,
    assigned_date: date | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> AssetAssignment:
    if asset.is_deleted:
        raise ProTrackValidationError("Cannot assign a deleted asset.")
    if asset.status == "returned_to_customer":
        raise ProTrackValidationError(
            "Cannot assign an asset that was returned to the customer."
        )
    if asset.status != "available":
        raise ProTrackValidationError(
            f"Asset must be available to assign (current status: {asset.status})."
        )
    if get_current_assignment(db, asset.id) is not None:
        raise ProTrackValidationError("Asset already has an open assignment.")
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("Assignee user not found.")
    when = assigned_date or date.today()
    assignment = AssetAssignment(
        id=uuid4(),
        asset_id=asset.id,
        assigned_to_user_id=user_id,
        assigned_by_user_id=by_user.id,
        assigned_date=when,
        notes=(notes or "").strip() or None,
    )
    asset.status = "assigned"
    db.add(assignment)
    db.add(asset)
    db.flush()
    log_activity(
        db,
        user=by_user,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=ActivityAction.it_asset_assigned,
        new_value={
            "asset_number": asset.asset_number,
            "assigned_to_user_id": str(user_id),
            "assigned_date": str(when),
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(assignment)
    return assignment


def return_asset(
    db: Session,
    asset: Asset,
    *,
    by_user: User,
    returned_date: date | None = None,
    return_condition: str | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> AssetAssignment:
    assignment = get_current_assignment(db, asset.id)
    if assignment is None:
        raise ProTrackValidationError("Asset is not currently assigned.")
    when = returned_date or date.today()
    assignment.returned_date = when
    assignment.return_condition = (return_condition or "").strip() or None
    if notes:
        assignment.notes = (
            f"{assignment.notes}\n{notes}".strip() if assignment.notes else notes.strip()
        )
    asset.status = "available"
    db.add(assignment)
    db.add(asset)
    db.flush()
    log_activity(
        db,
        user=by_user,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=ActivityAction.it_asset_returned,
        new_value={
            "asset_number": asset.asset_number,
            "returned_date": str(when),
            "return_condition": assignment.return_condition,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(assignment)
    return assignment


def return_asset_to_customer(
    db: Session,
    asset: Asset,
    *,
    by_user: User,
    return_date: date | None = None,
    owner_customer_id: UUID | None = None,
    received_by_name: str | None = None,
    condition_at_return: str | None = None,
    return_reason: str | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> AssetCustomerReturn:
    """Mark customer-owned asset as returned — keep history, remove from current inventory."""
    if asset.is_deleted:
        raise ProTrackValidationError("Cannot return a deleted asset.")
    if asset.status == "returned_to_customer":
        raise ProTrackValidationError("Asset is already returned to customer.")
    if asset.purchased_by != "customer":
        raise ProTrackValidationError(
            "Only customer-owned assets can be returned to a customer."
        )
    customer_id = owner_customer_id or asset.owner_customer_id
    if customer_id is None:
        raise ProTrackValidationError("Customer owner is required for return.")
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ProTrackValidationError("Owner customer not found.")

    when = return_date or date.today()
    assignment = get_current_assignment(db, asset.id)
    original_assignee = assignment.assigned_to_user_id if assignment else None
    if assignment is not None:
        assignment.returned_date = when
        assignment.return_condition = (condition_at_return or "").strip() or None
        db.add(assignment)

    event = AssetCustomerReturn(
        id=uuid4(),
        asset_id=asset.id,
        owner_customer_id=customer_id,
        return_date=when,
        returned_by_user_id=by_user.id,
        received_by_name=(received_by_name or "").strip() or None,
        condition_at_return=(condition_at_return or "").strip() or None,
        return_reason=(return_reason or "").strip() or None,
        notes=(notes or "").strip() or None,
        original_assignee_user_id=original_assignee,
    )
    asset.status = "returned_to_customer"
    asset.owner_customer_id = customer_id
    db.add(event)
    db.add(asset)
    db.flush()
    log_activity(
        db,
        user=by_user,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=ActivityAction.it_asset_returned_to_customer,
        new_value={
            "asset_number": asset.asset_number,
            "owner_customer_id": str(customer_id),
            "return_date": str(when),
            "condition_at_return": event.condition_at_return,
            "received_by_name": event.received_by_name,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(event)
    return event


def list_customer_returns(
    db: Session,
    *,
    owner_customer_id: UUID | None = None,
    limit: int = 500,
) -> list[AssetCustomerReturn]:
    stmt = (
        select(AssetCustomerReturn)
        .options(selectinload(AssetCustomerReturn.asset).selectinload(Asset.asset_type))
        .order_by(AssetCustomerReturn.return_date.desc())
        .limit(limit)
    )
    if owner_customer_id is not None:
        stmt = stmt.where(AssetCustomerReturn.owner_customer_id == owner_customer_id)
    return list(db.scalars(stmt).all())


def transfer_asset(
    db: Session,
    asset: Asset,
    *,
    to_user_id: UUID,
    by_user: User,
    assigned_date: date | None = None,
    notes: str | None = None,
) -> AssetAssignment:
    when = assigned_date or date.today()
    if get_current_assignment(db, asset.id) is not None:
        return_asset(
            db,
            asset,
            by_user=by_user,
            returned_date=when,
            notes="Transferred",
            commit=False,
        )
    elif asset.status != "available":
        asset.status = "available"
        db.add(asset)
        db.flush()
    assignment = assign_asset(
        db,
        asset,
        user_id=to_user_id,
        by_user=by_user,
        assigned_date=when,
        notes=notes,
        commit=False,
    )
    log_activity(
        db,
        user=by_user,
        entity_type=EntityType.it_asset,
        entity_id=asset.id,
        action=ActivityAction.it_asset_transferred,
        new_value={
            "asset_number": asset.asset_number,
            "to_user_id": str(to_user_id),
            "assigned_date": str(when),
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def list_asset_assignments(db: Session, asset_id: UUID) -> list[AssetAssignment]:
    return list(
        db.scalars(
            select(AssetAssignment)
            .where(AssetAssignment.asset_id == asset_id)
            .order_by(AssetAssignment.assigned_date.desc(), AssetAssignment.created_at.desc())
        ).all()
    )


def list_computers(
    db: Session,
    *,
    search: str | None = None,
    skip: int = 0,
    limit: int = 25,
) -> tuple[list[Computer], int]:
    stmt = (
        select(Computer)
        .options(
            selectinload(Computer.asset).selectinload(Asset.asset_type),
        )
        .join(Asset, Computer.asset_id == Asset.id)
        .where(Asset.is_deleted.is_(False))
    )
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Computer.computer_name.ilike(q),
                Asset.asset_number.ilike(q),
                Computer.mac_address.ilike(q),
            )
        )
    rows_all = list(db.scalars(stmt.order_by(Computer.computer_name)).all())
    total = len(rows_all)
    return rows_all[skip : skip + limit], total


def create_computer(
    db: Session,
    *,
    actor: User,
    asset_type_id: UUID | None = None,
    asset_id: UUID | None = None,
    os: str | None = None,
    processor: str | None = None,
    ram_gb: int | None = None,
    storage_type: str | None = None,
    storage_gb: int | None = None,
    domain_joined: bool = False,
    mac_address: str | None = None,
    serial_number: str | None = None,
    make: str | None = None,
    model: str | None = None,
    purchase_date: date | None = None,
    purchase_cost: Decimal | None = None,
    warranty_expiry: date | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> Computer:
    if asset_id is None and asset_type_id is None:
        raise ProTrackValidationError("Provide asset_id or asset_type_id.")
    if asset_id is not None and asset_type_id is not None:
        raise ProTrackValidationError("Provide only one of asset_id or asset_type_id.")

    if asset_id is not None:
        asset = get_asset(db, asset_id)
        if asset is None:
            raise ProTrackValidationError("Asset not found.")
        if asset.computer is not None:
            raise ProTrackValidationError("Asset already has a computer record.")
        asset_type = asset.asset_type or db.get(AssetType, asset.asset_type_id)
    else:
        asset_type = db.get(AssetType, asset_type_id)
        if asset_type is None or not asset_type.is_active:
            raise ProTrackValidationError("Asset type not found or inactive.")
        if asset_type.category not in {"computer", "network_equipment"}:
            # Still allow, but prefer computer-category types.
            pass
        asset = create_asset(
            db,
            actor=actor,
            asset_type_id=asset_type.id,
            serial_number=serial_number,
            make=make,
            model=model,
            purchase_date=purchase_date,
            purchase_cost=purchase_cost,
            warranty_expiry=warranty_expiry,
            location=location,
            notes=notes,
            commit=False,
        )

    type_code = (asset_type.code if asset_type else "PC")[:6]
    computer_name = next_computer_name(db, type_code)
    computer = Computer(
        id=uuid4(),
        asset_id=asset.id,
        computer_name=computer_name,
        os=(os or "").strip() or None,
        processor=(processor or "").strip() or None,
        ram_gb=ram_gb,
        storage_type=(storage_type or "").strip() or None,
        storage_gb=storage_gb,
        domain_joined=bool(domain_joined),
        mac_address=(mac_address or "").strip() or None,
    )
    db.add(computer)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_computer,
        entity_id=computer.id,
        action=ActivityAction.it_computer_created,
        new_value={
            "computer_name": computer.computer_name,
            "asset_number": asset.asset_number,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(computer)
    return computer


def update_computer(
    db: Session,
    computer: Computer,
    *,
    actor: User,
    os: str | None = None,
    processor: str | None = None,
    ram_gb: int | None = None,
    storage_type: str | None = None,
    storage_gb: int | None = None,
    domain_joined: bool | None = None,
    mac_address: str | None = None,
    fields_set: set[str] | None = None,
) -> Computer:
    touched = fields_set or set()
    if "os" in touched or (fields_set is None and os is not None):
        computer.os = (os or "").strip() or None
    if "processor" in touched or (fields_set is None and processor is not None):
        computer.processor = (processor or "").strip() or None
    if "ram_gb" in touched or (fields_set is None and ram_gb is not None):
        computer.ram_gb = ram_gb
    if "storage_type" in touched or (fields_set is None and storage_type is not None):
        computer.storage_type = (storage_type or "").strip() or None
    if "storage_gb" in touched or (fields_set is None and storage_gb is not None):
        computer.storage_gb = storage_gb
    if "domain_joined" in touched or (fields_set is None and domain_joined is not None):
        computer.domain_joined = bool(domain_joined)
    if "mac_address" in touched or (fields_set is None and mac_address is not None):
        computer.mac_address = (mac_address or "").strip() or None
    db.add(computer)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_computer,
        entity_id=computer.id,
        action=ActivityAction.it_computer_updated,
        new_value={"computer_name": computer.computer_name},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(computer)
    return computer


def get_computer(db: Session, computer_id: UUID) -> Computer | None:
    return db.scalar(
        select(Computer)
        .options(selectinload(Computer.asset).selectinload(Asset.asset_type))
        .where(Computer.id == computer_id)
    )


def assignee_name_for_asset(db: Session, asset: Asset) -> tuple[UUID | None, str | None]:
    asg = get_current_assignment(db, asset.id)
    if asg is None:
        return None, None
    user = db.get(User, asg.assigned_to_user_id)
    return asg.assigned_to_user_id, _full_name(user)


def list_assets_for_user(db: Session, user_id: UUID) -> list[Asset]:
    open_ids = select(AssetAssignment.asset_id).where(
        AssetAssignment.assigned_to_user_id == user_id,
        AssetAssignment.returned_date.is_(None),
    )
    return list(
        db.scalars(
            select(Asset)
            .options(selectinload(Asset.asset_type))
            .where(Asset.is_deleted.is_(False), Asset.id.in_(open_ids))
            .order_by(Asset.asset_number)
        ).all()
    )
