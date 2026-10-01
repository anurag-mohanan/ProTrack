"""IT asset, computer, and assignment workflows."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import exists, func, not_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import MODULE_IT_OPERATIONS
from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetCustomerReturn,
    AssetLocationHistory,
    AssetNumberHistory,
    AssetOwnershipHistory,
    AssetStatusHistory,
    AssetType,
    Computer,
    ComputerNameHistory,
    ComputerNetworkInterface,
    ITSettings,
)
from app.models.models import Customer, User
from app.services.activity_service import log_activity

MODULE = MODULE_IT_OPERATIONS
ASSET_STATUSES = frozenset(
    {
        "available",
        "assigned",
        "reserved",
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
    {"available", "assigned", "reserved", "maintenance", "awaiting_return"}
)
PURCHASED_BY_CODES = frozenset(
    {"organization", "customer", "vendor", "leased", "other", "unknown"}
)
WARRANTY_STATUSES = frozenset({"none", "active", "expiring_soon", "expired"})
NIC_ROLES = frozenset({"lan", "wifi", "vpn", "other"})
# Days before expiry counted as "expiring soon"
WARRANTY_EXPIRING_SOON_DAYS = 30
# Selectable warranty alert windows (ITSettings.settings_json["warranty_alert_days"])
WARRANTY_ALERT_DAY_OPTIONS = (7, 30, 60, 90)
# Upper bound for the bulk "next numbers" preview
MAX_NUMBER_PREVIEW = 200


def warranty_alert_days(db: Session) -> int:
    """Configured warranty alert window; falls back to WARRANTY_EXPIRING_SOON_DAYS."""
    import json

    raw = db.scalar(select(ITSettings.settings_json).limit(1))
    if not raw:
        return WARRANTY_EXPIRING_SOON_DAYS
    try:
        value = int((json.loads(raw) or {}).get("warranty_alert_days"))
    except (TypeError, ValueError, AttributeError):
        return WARRANTY_EXPIRING_SOON_DAYS
    return value if value in WARRANTY_ALERT_DAY_OPTIONS else WARRANTY_EXPIRING_SOON_DAYS


def warranty_status_for(expiry: date | None, *, today: date | None = None) -> str:
    """Derive warranty status from warranty_expiry (warranty upto)."""
    if expiry is None:
        return "none"
    ref = today or date.today()
    if expiry < ref:
        return "expired"
    if expiry <= ref + timedelta(days=WARRANTY_EXPIRING_SOON_DAYS):
        return "expiring_soon"
    return "active"


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


def _clean_computer_type(value: str | None) -> str | None:
    from app.models.it_operations import COMPUTER_TYPES

    code = (value or "").strip().upper() or None
    if code is not None and code not in COMPUTER_TYPES:
        raise ProTrackValidationError(f"Invalid computer_type: {code}")
    return code


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


def _prefix_for_type(asset_type: AssetType) -> str:
    return (asset_type.numbering_prefix or asset_type.code or "ASSET").strip()


def _format_asset_number(pattern: str, *, prefix: str, seq: int, type_code: str) -> str:
    try:
        return pattern.format(prefix=prefix, seq=seq, type=type_code or "").strip()
    except (KeyError, ValueError) as exc:
        raise ProTrackValidationError(f"Invalid asset numbering pattern: {pattern}") from exc


def _seq_from_number(text: str, *, prefix_norm: str) -> int:
    import re

    raw = (text or "").strip()
    if not raw.upper().startswith(prefix_norm.upper()):
        return 0
    match = re.search(r"(\d+)\s*$", raw)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def _highest_seq_for_prefix(db: Session, *, prefix: str, pattern: str) -> int:
    """
    Highest numeric sequence among existing asset numbers for this prefix.

    Default policy: highest existing + 1 (do not fill gaps). Includes disposed,
    retired, deleted, and historical numbers so retired identities are never reused.
    """
    prefix_norm = prefix.strip()
    if not prefix_norm:
        return 0
    like = f"{prefix_norm}%"
    current_numbers = list(
        db.scalars(
            select(Asset.asset_number).where(Asset.asset_number.ilike(like))
        ).all()
    )
    history_numbers = list(
        db.scalars(
            select(AssetNumberHistory.asset_number).where(
                AssetNumberHistory.asset_number.ilike(like)
            )
        ).all()
    )
    highest = 0
    for num in (*current_numbers, *history_numbers):
        highest = max(highest, _seq_from_number(num or "", prefix_norm=prefix_norm))
    return highest


def asset_number_is_reserved(
    db: Session, number: str, *, exclude_asset_id: UUID | None = None
) -> bool:
    """True if the number is in use, historically used, or on a deleted asset."""
    cleaned = (number or "").strip()
    if not cleaned:
        return False
    current = select(Asset.id).where(Asset.asset_number == cleaned)
    if exclude_asset_id is not None:
        current = current.where(Asset.id != exclude_asset_id)
    if db.scalar(current.limit(1)) is not None:
        return True
    history = select(AssetNumberHistory.id).where(AssetNumberHistory.asset_number == cleaned)
    if exclude_asset_id is not None:
        # The open period for this asset is the current number, not a reservation.
        history = history.where(
            not_(
                (AssetNumberHistory.asset_id == exclude_asset_id)
                & AssetNumberHistory.effective_to.is_(None)
            )
        )
    return db.scalar(history.limit(1)) is not None


def preview_next_asset_number(db: Session, asset_type: AssetType) -> dict:
    """Suggest next number without consuming the sequence (read-side)."""
    settings = get_or_create_settings(db)
    prefix = _prefix_for_type(asset_type)
    pattern = settings.asset_numbering_pattern or "{prefix}-{seq:04d}"
    highest_db = _highest_seq_for_prefix(db, prefix=prefix, pattern=pattern)
    # Align with counter so imports that skipped the counter don't collide
    seq = max(highest_db, int(settings.next_asset_seq or 1) - 1) + 1
    number = _format_asset_number(
        pattern, prefix=prefix, seq=seq, type_code=asset_type.code or ""
    )
    # If collision (rare with custom patterns), walk forward — history is reserved too
    while asset_number_is_reserved(db, number):
        seq += 1
        number = _format_asset_number(
            pattern, prefix=prefix, seq=seq, type_code=asset_type.code or ""
        )
    return {
        "asset_number": number,
        "prefix": prefix,
        "sequence": seq,
        "pattern": pattern,
        "highest_existing_sequence": highest_db,
        "message": "Suggested next available asset number (highest existing + 1).",
    }


def preview_next_asset_numbers(
    db: Session, asset_type_id: UUID, count: int = 1
) -> list[str]:
    """Suggest the next N numbers for a type without allocating any of them."""
    asset_type = db.get(AssetType, asset_type_id)
    if asset_type is None:
        raise ProTrackValidationError("Asset type not found.")
    wanted = max(1, min(int(count or 1), MAX_NUMBER_PREVIEW))
    first = preview_next_asset_number(db, asset_type)
    prefix = first["prefix"]
    pattern = first["pattern"]
    numbers = [str(first["asset_number"])]
    seq = int(first["sequence"])
    attempts = 0
    while len(numbers) < wanted:
        seq += 1
        attempts += 1
        if attempts > wanted * 50:
            raise ProTrackValidationError(
                f"Numbering pattern '{pattern}' cannot produce {wanted} distinct numbers."
            )
        number = _format_asset_number(
            pattern, prefix=prefix, seq=seq, type_code=asset_type.code or ""
        )
        if number in numbers:
            continue
        if asset_number_is_reserved(db, number):
            continue
        numbers.append(number)
    return numbers


def next_asset_number(db: Session, asset_type: AssetType) -> str:
    """
    Allocate next asset number under lock.

    Uses max(highest existing for prefix, settings counter) + 1.
    Does not recycle gaps or historical disposed numbers.
    """
    settings = _locked_settings(db)
    prefix = _prefix_for_type(asset_type)
    pattern = settings.asset_numbering_pattern or "{prefix}-{seq:04d}"
    highest_db = _highest_seq_for_prefix(db, prefix=prefix, pattern=pattern)
    seq = max(highest_db, int(settings.next_asset_seq or 1) - 1) + 1
    number = _format_asset_number(
        pattern, prefix=prefix, seq=seq, type_code=asset_type.code or ""
    )
    while asset_number_is_reserved(db, number):
        seq += 1
        number = _format_asset_number(
            pattern, prefix=prefix, seq=seq, type_code=asset_type.code or ""
        )
    settings.next_asset_seq = seq + 1
    db.add(settings)
    db.flush()
    return number


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
    """Primary open assignment (most recent). For shared desks prefer list_open_assignments."""
    return db.scalar(
        select(AssetAssignment)
        .where(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.returned_date.is_(None),
        )
        .order_by(AssetAssignment.assigned_date.desc())
        .limit(1)
    )


def list_open_assignments(db: Session, asset_id: UUID) -> list[AssetAssignment]:
    return list(
        db.scalars(
            select(AssetAssignment)
            .where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.returned_date.is_(None),
            )
            .order_by(AssetAssignment.assigned_date.desc())
        ).all()
    )


def get_open_assignment_for_shift(
    db: Session, asset_id: UUID, shift_id: UUID
) -> AssetAssignment | None:
    return db.scalar(
        select(AssetAssignment)
        .where(
            AssetAssignment.asset_id == asset_id,
            AssetAssignment.returned_date.is_(None),
            AssetAssignment.shift_id == shift_id,
        )
        .limit(1)
    )


def _open_number_period(
    db: Session,
    asset: Asset,
    *,
    actor: User,
    on_date: date,
    reason: str | None = None,
    notes: str | None = None,
) -> None:
    db.add(
        AssetNumberHistory(
            id=uuid4(),
            asset_id=asset.id,
            asset_number=asset.asset_number,
            effective_from=on_date,
            changed_by_user_id=actor.id,
            reason=reason,
            notes=notes,
        )
    )


def _current_number_period(db: Session, asset_id: UUID) -> AssetNumberHistory | None:
    return db.scalar(
        select(AssetNumberHistory)
        .where(
            AssetNumberHistory.asset_id == asset_id,
            AssetNumberHistory.effective_to.is_(None),
        )
        .order_by(AssetNumberHistory.effective_from.desc())
        .limit(1)
    )


def _open_computer_name_period(
    db: Session,
    computer: Computer,
    *,
    actor: User,
    on_date: date,
    reason: str | None = None,
    notes: str | None = None,
) -> None:
    db.add(
        ComputerNameHistory(
            id=uuid4(),
            computer_id=computer.id,
            computer_name=computer.computer_name,
            effective_from=on_date,
            changed_by_user_id=actor.id,
            reason=reason,
            notes=notes,
        )
    )


def _current_computer_name_period(db: Session, computer_id: UUID) -> ComputerNameHistory | None:
    return db.scalar(
        select(ComputerNameHistory)
        .where(
            ComputerNameHistory.computer_id == computer_id,
            ComputerNameHistory.effective_to.is_(None),
        )
        .order_by(ComputerNameHistory.effective_from.desc())
        .limit(1)
    )


def apply_computer_name_change(
    db: Session,
    computer: Computer,
    new_name: str,
    *,
    actor: User,
    reason: str | None = None,
    notes: str | None = None,
    on_date: date | None = None,
) -> None:
    from app.services import it_computer_suggest_service as suggest

    cleaned = (new_name or "").strip()
    if not cleaned:
        raise ProTrackValidationError("Computer name is required.")
    if cleaned == computer.computer_name:
        return
    if suggest.computer_name_is_taken(db, cleaned, exclude_computer_id=computer.id):
        raise ProTrackValidationError(
            f"Computer name '{cleaned}' is already in use or was used historically."
        )
    today = on_date or date.today()
    current = _current_computer_name_period(db, computer.id)
    if current is not None and current.effective_to is None:
        current.effective_to = today
        db.add(current)
    computer.computer_name = cleaned
    db.add(computer)
    db.flush()
    _open_computer_name_period(
        db, computer, actor=actor, on_date=today, reason=reason or "manual_update", notes=notes
    )


def _serial_conflict(db: Session, serial: str, *, exclude_asset_id: UUID | None = None) -> Asset | None:
    cleaned = (serial or "").strip()
    if not cleaned:
        return None
    stmt = select(Asset).where(
        Asset.is_deleted.is_(False),
        func.lower(Asset.serial_number) == cleaned.lower(),
    )
    if exclude_asset_id is not None:
        stmt = stmt.where(Asset.id != exclude_asset_id)
    return db.scalar(stmt.limit(1))


def apply_asset_number_change(
    db: Session,
    asset: Asset,
    new_number: str,
    *,
    actor: User,
    reason: str | None = None,
    on_date: date | None = None,
) -> str:
    """Move an asset to a new number, closing the previous history period.

    Previous numbers stay reserved forever (including deleted assets).
    """
    cleaned = (new_number or "").strip()
    if not cleaned:
        raise ProTrackValidationError("Asset number is required.")
    if cleaned == asset.asset_number:
        return cleaned
    if asset_number_is_reserved(db, cleaned, exclude_asset_id=asset.id):
        raise ProTrackValidationError(
            f"Asset number '{cleaned}' is already used or historically reserved."
        )
    today = on_date or date.today()
    prev = _current_number_period(db, asset.id)
    if prev is None:
        _open_number_period(db, asset, actor=actor, on_date=today, reason="open_before_change")
        prev = _current_number_period(db, asset.id)
    _end_open_period(prev, on_date=today)
    if prev is not None:
        db.add(prev)
    old_number = asset.asset_number
    if not asset.legacy_asset_number:
        asset.legacy_asset_number = old_number
    asset.asset_number = cleaned
    db.add(asset)
    db.flush()
    _open_number_period(
        db, asset, actor=actor, on_date=today, reason=reason or "renumber"
    )
    return old_number


def _open_ownership_period(
    db: Session,
    asset: Asset,
    *,
    actor: User,
    on_date: date,
    notes: str | None = None,
) -> None:
    db.add(
        AssetOwnershipHistory(
            id=uuid4(),
            asset_id=asset.id,
            purchased_by=asset.purchased_by,
            owner_customer_id=asset.owner_customer_id,
            effective_from=on_date,
            changed_by_user_id=actor.id,
            notes=notes,
        )
    )


def _open_location_period(
    db: Session,
    asset: Asset,
    *,
    actor: User,
    on_date: date,
    notes: str | None = None,
) -> None:
    db.add(
        AssetLocationHistory(
            id=uuid4(),
            asset_id=asset.id,
            location=asset.location,
            effective_from=on_date,
            changed_by_user_id=actor.id,
            notes=notes,
        )
    )


def _open_status_period(
    db: Session,
    asset: Asset,
    *,
    actor: User,
    on_date: date,
    reason: str | None = None,
    notes: str | None = None,
) -> None:
    db.add(
        AssetStatusHistory(
            id=uuid4(),
            asset_id=asset.id,
            status=asset.status,
            effective_from=on_date,
            changed_by_user_id=actor.id,
            reason=reason,
            notes=notes,
        )
    )


def _end_open_period(row, *, on_date: date) -> None:
    if row is not None and row.effective_to is None:
        # Period ends the day before the new one starts when same-day change.
        row.effective_to = on_date if on_date >= row.effective_from else row.effective_from


def _current_ownership_period(db: Session, asset_id: UUID) -> AssetOwnershipHistory | None:
    return db.scalar(
        select(AssetOwnershipHistory)
        .where(
            AssetOwnershipHistory.asset_id == asset_id,
            AssetOwnershipHistory.effective_to.is_(None),
        )
        .order_by(AssetOwnershipHistory.effective_from.desc())
        .limit(1)
    )


def _current_location_period(db: Session, asset_id: UUID) -> AssetLocationHistory | None:
    return db.scalar(
        select(AssetLocationHistory)
        .where(
            AssetLocationHistory.asset_id == asset_id,
            AssetLocationHistory.effective_to.is_(None),
        )
        .order_by(AssetLocationHistory.effective_from.desc())
        .limit(1)
    )


def _current_status_period(db: Session, asset_id: UUID) -> AssetStatusHistory | None:
    return db.scalar(
        select(AssetStatusHistory)
        .where(
            AssetStatusHistory.asset_id == asset_id,
            AssetStatusHistory.effective_to.is_(None),
        )
        .order_by(AssetStatusHistory.effective_from.desc())
        .limit(1)
    )


def list_asset_lifecycle_history(db: Session, asset_id: UUID) -> dict:
    # Open periods (effective_to IS NULL) first, then newest effective_from.
    ownership = list(
        db.scalars(
            select(AssetOwnershipHistory)
            .where(AssetOwnershipHistory.asset_id == asset_id)
            .order_by(
                AssetOwnershipHistory.effective_to.is_(None).desc(),
                AssetOwnershipHistory.effective_from.desc(),
            )
        ).all()
    )
    locations = list(
        db.scalars(
            select(AssetLocationHistory)
            .where(AssetLocationHistory.asset_id == asset_id)
            .order_by(
                AssetLocationHistory.effective_to.is_(None).desc(),
                AssetLocationHistory.effective_from.desc(),
            )
        ).all()
    )
    statuses = list(
        db.scalars(
            select(AssetStatusHistory)
            .where(AssetStatusHistory.asset_id == asset_id)
            .order_by(
                AssetStatusHistory.effective_to.is_(None).desc(),
                AssetStatusHistory.effective_from.desc(),
            )
        ).all()
    )
    numbers = list(
        db.scalars(
            select(AssetNumberHistory)
            .where(AssetNumberHistory.asset_id == asset_id)
            .order_by(
                AssetNumberHistory.effective_to.is_(None).desc(),
                AssetNumberHistory.effective_from.desc(),
            )
        ).all()
    )
    return {
        "ownership": [
            {
                "id": str(row.id),
                "purchased_by": row.purchased_by,
                "owner_customer_id": str(row.owner_customer_id) if row.owner_customer_id else None,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat() if row.effective_to else None,
                "changed_by_user_id": str(row.changed_by_user_id),
                "notes": row.notes,
            }
            for row in ownership
        ],
        "locations": [
            {
                "id": str(row.id),
                "location": row.location,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat() if row.effective_to else None,
                "changed_by_user_id": str(row.changed_by_user_id),
                "notes": row.notes,
            }
            for row in locations
        ],
        "statuses": [
            {
                "id": str(row.id),
                "status": row.status,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat() if row.effective_to else None,
                "changed_by_user_id": str(row.changed_by_user_id),
                "reason": row.reason,
                "notes": row.notes,
            }
            for row in statuses
        ],
        "asset_numbers": [
            {
                "id": str(row.id),
                "asset_number": row.asset_number,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat() if row.effective_to else None,
                "changed_by_user_id": str(row.changed_by_user_id),
                "reason": row.reason,
                "notes": row.notes,
            }
            for row in numbers
        ],
        "computer_names": [
            {
                "id": str(row.id),
                "computer_name": row.computer_name,
                "effective_from": row.effective_from.isoformat(),
                "effective_to": row.effective_to.isoformat() if row.effective_to else None,
                "changed_by_user_id": str(row.changed_by_user_id),
                "reason": row.reason,
                "notes": row.notes,
            }
            for row in (
                db.scalars(
                    select(ComputerNameHistory)
                    .join(Computer, Computer.id == ComputerNameHistory.computer_id)
                    .where(Computer.asset_id == asset_id)
                    .order_by(
                        ComputerNameHistory.effective_to.is_(None).desc(),
                        ComputerNameHistory.effective_from.desc(),
                    )
                ).all()
            )
        ],
    }


def list_assets(
    db: Session,
    *,
    status: str | None = None,
    asset_type_id: UUID | None = None,
    category: str | None = None,
    make_id: UUID | None = None,
    model_id: UUID | None = None,
    search: str | None = None,
    inventory_scope: str = "current",
    purchased_by: str | None = None,
    owner_customer_id: UUID | None = None,
    customer_used_for_id: UUID | None = None,
    warranty_status: str | None = None,
    warranty_within_days: int | None = None,
    skip: int = 0,
    limit: int = 25,
) -> tuple[list[Asset], int]:
    stmt = (
        select(Asset)
        .options(selectinload(Asset.asset_type), selectinload(Asset.assignments), selectinload(Asset.computer))
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
    category_key = (category or "").strip().lower() or None
    if category_key:
        category_clause = Asset.asset_type_id.in_(
            select(AssetType.id).where(AssetType.category == category_key)
        )
        stmt = stmt.where(category_clause)
        count_filters.append(category_clause)
    if make_id:
        stmt = stmt.where(Asset.make_id == make_id)
        count_filters.append(Asset.make_id == make_id)
    if model_id:
        stmt = stmt.where(Asset.model_id == model_id)
        count_filters.append(Asset.model_id == model_id)
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
        history_match = exists().where(
            AssetNumberHistory.asset_id == Asset.id,
            AssetNumberHistory.asset_number.ilike(q),
        )
        computer_match = exists().where(
            Computer.asset_id == Asset.id,
            Computer.computer_name.ilike(q),
        )
        computer_history_match = exists().where(
            ComputerNameHistory.computer_id == Computer.id,
            Computer.asset_id == Asset.id,
            ComputerNameHistory.computer_name.ilike(q),
        )
        search_clause = or_(
            Asset.asset_number.ilike(q),
            Asset.legacy_asset_number.ilike(q),
            Asset.serial_number.ilike(q),
            Asset.service_tag.ilike(q),
            Asset.make.ilike(q),
            Asset.model.ilike(q),
            Asset.location.ilike(q),
            Asset.description.ilike(q),
            history_match,
            computer_match,
            computer_history_match,
        )
        stmt = stmt.where(search_clause)
        count_filters.append(search_clause)

    warranty_key = (warranty_status or "").strip().lower() or None
    if warranty_key:
        if warranty_key not in WARRANTY_STATUSES:
            raise ProTrackValidationError(
                f"Invalid warranty_status '{warranty_status}'. "
                f"Allowed: {', '.join(sorted(WARRANTY_STATUSES))}"
            )
        today = date.today()
        window = (
            warranty_within_days
            if warranty_within_days and warranty_within_days > 0
            else WARRANTY_EXPIRING_SOON_DAYS
        )
        soon = today + timedelta(days=window)
        if warranty_key == "none":
            w_clause = Asset.warranty_expiry.is_(None)
        elif warranty_key == "expired":
            w_clause = Asset.warranty_expiry.is_not(None) & (Asset.warranty_expiry < today)
        elif warranty_key == "expiring_soon":
            w_clause = (
                Asset.warranty_expiry.is_not(None)
                & (Asset.warranty_expiry >= today)
                & (Asset.warranty_expiry <= soon)
            )
        else:  # active
            w_clause = Asset.warranty_expiry.is_not(None) & (Asset.warranty_expiry > soon)
        stmt = stmt.where(w_clause)
        count_filters.append(w_clause)

    total = int(
        db.scalar(select(func.count()).select_from(Asset).where(*count_filters)) or 0
    )
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
    make_id: UUID | None = None,
    model_id: UUID | None = None,
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
    supplier_name: str | None = None,
    invoice_number: str | None = None,
    condition: str | None = None,
    computer_name: str | None = None,
    mac_address: str | None = None,
    ip_address_id: UUID | None = None,
    provision_computer: bool | None = None,
    computer_type: str | None = None,
    commit: bool = True,
) -> Asset:
    from app.services.it_master_data_service import resolve_masters_for_asset

    asset_type = db.get(AssetType, asset_type_id)
    if asset_type is None or not asset_type.is_active:
        raise ProTrackValidationError("Asset type not found or inactive.")
    computer_type = _clean_computer_type(computer_type)
    _validate_ownership(purchased_by=purchased_by, owner_customer_id=owner_customer_id)
    if owner_customer_id is not None and db.get(Customer, owner_customer_id) is None:
        raise ProTrackValidationError("Owner customer not found.")
    if customer_used_for_id is not None and db.get(Customer, customer_used_for_id) is None:
        raise ProTrackValidationError("Customer used for not found.")

    masters = resolve_masters_for_asset(
        db,
        asset_type_id=asset_type_id,
        make=make,
        model=model,
        make_id=make_id,
        model_id=model_id,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
    )

    preferred = (asset_number or "").strip() or None
    if preferred:
        if asset_number_is_reserved(db, preferred):
            suggested = preview_next_asset_number(db, asset_type)["asset_number"]
            raise ProTrackValidationError(
                f"Asset number '{preferred}' already exists or was used historically. "
                f"Suggested next: {suggested}"
            )
        number = preferred
    else:
        number = next_asset_number(db, asset_type)

    serial = (serial_number or "").strip() or None
    if serial:
        conflict = _serial_conflict(db, serial)
        if conflict is not None:
            raise ProTrackValidationError(
                f"Serial number '{serial}' is already assigned to {conflict.asset_number}."
            )

    tag = (service_tag or "").strip()
    if tag:
        tag_conflict = db.scalar(
            select(Asset)
            .where(
                Asset.is_deleted.is_(False),
                func.lower(Asset.service_tag) == tag.lower(),
            )
            .limit(1)
        )
        if tag_conflict is not None:
            raise ProTrackValidationError(
                f"Service tag '{tag}' is already assigned to {tag_conflict.asset_number}."
            )

    from app.services import it_computer_suggest_service as suggest

    mac = suggest.normalize_mac(mac_address)
    if mac:
        mac_owner = suggest.mac_is_taken(db, mac)
        if mac_owner is not None:
            raise ProTrackValidationError(
                f"MAC address {mac} is already assigned to {mac_owner.computer_name}."
            )
    asset = Asset(
        id=uuid4(),
        asset_number=number,
        legacy_asset_number=(legacy_asset_number or "").strip() or None,
        asset_type_id=asset_type.id,
        description=(description or "").strip() or None,
        serial_number=(serial_number or "").strip() or None,
        service_tag=(service_tag or "").strip() or None,
        make=masters["make"],
        model=masters["model"],
        make_id=masters["make_id"],
        model_id=masters["model_id"],
        status="available",
        purchased_by=purchased_by,
        owner_customer_id=owner_customer_id,
        customer_used_for_id=customer_used_for_id,
        supplier_id=masters["supplier_id"],
        invoice_number=(invoice_number or "").strip() or None,
        condition=(condition or "").strip() or None,
        purchase_date=purchase_date,
        purchase_cost=purchase_cost,
        warranty_expiry=warranty_expiry,
        location=(location or "").strip() or None,
        computer_type=computer_type,
        notes=(notes or "").strip() or None,
        is_deleted=False,
    )
    db.add(asset)
    db.flush()
    today = date.today()
    _open_number_period(db, asset, actor=actor, on_date=today, reason="created")
    _open_ownership_period(db, asset, actor=actor, on_date=today)
    _open_location_period(db, asset, actor=actor, on_date=today)
    _open_status_period(db, asset, actor=actor, on_date=today)
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
    wants_computer = provision_computer
    if wants_computer is None:
        wants_computer = False
    if (computer_name or "").strip() or mac or ip_address_id:
        wants_computer = True
    if wants_computer:
        create_computer(
            db,
            actor=actor,
            asset_id=asset.id,
            computer_name=(computer_name or "").strip() or None,
            mac_address=mac,
            ip_address_id=ip_address_id,
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
    asset_number: str | None = None,
    computer_name: str | None = None,
    computer_name_reason: str | None = None,
    computer_type: str | None = None,
    fields_set: set[str] | None = None,
    commit: bool = True,
) -> Asset:
    if asset.is_deleted:
        raise ProTrackValidationError("Cannot update a deleted asset.")
    if "computer_type" in (fields_set or set()) or (fields_set is None and computer_type is not None):
        asset.computer_type = _clean_computer_type(computer_type)
    old = {
        "status": asset.status,
        "location": asset.location,
        "purchased_by": asset.purchased_by,
        "owner_customer_id": str(asset.owner_customer_id) if asset.owner_customer_id else None,
        "asset_number": asset.asset_number,
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

    if "asset_number" in touched or (fields_set is None and asset_number is not None):
        next_number = (asset_number or "").strip()
        if next_number and next_number != asset.asset_number:
            apply_asset_number_change(
                db, asset, next_number, actor=actor, reason="manual_update"
            )

    if "computer_name" in touched or (fields_set is None and computer_name is not None):
        computer = getattr(asset, "computer", None) or db.scalar(
            select(Computer).where(Computer.asset_id == asset.id)
        )
        if computer is not None and computer_name:
            apply_computer_name_change(
                db,
                computer,
                computer_name,
                actor=actor,
                reason=computer_name_reason or "manual_update",
            )

    db.add(asset)
    db.flush()
    ownership_changed = old["purchased_by"] != asset.purchased_by or old[
        "owner_customer_id"
    ] != (str(asset.owner_customer_id) if asset.owner_customer_id else None)
    location_changed = old["location"] != asset.location
    status_changed = old["status"] != asset.status
    today = date.today()
    if ownership_changed:
        prev = _current_ownership_period(db, asset.id)
        _end_open_period(prev, on_date=today)
        if prev is not None:
            db.add(prev)
        _open_ownership_period(db, asset, actor=actor, on_date=today)
    if location_changed:
        prev = _current_location_period(db, asset.id)
        _end_open_period(prev, on_date=today)
        if prev is not None:
            db.add(prev)
        _open_location_period(db, asset, actor=actor, on_date=today)
    if status_changed:
        prev = _current_status_period(db, asset.id)
        _end_open_period(prev, on_date=today)
        if prev is not None:
            db.add(prev)
        reason = "maintenance" if asset.status == "maintenance" else None
        _open_status_period(db, asset, actor=actor, on_date=today, reason=reason)
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
    if commit:
        db.commit()
        db.refresh(asset)
    return asset


def soft_delete_asset(
    db: Session, asset: Asset, *, actor: User, commit: bool = True
) -> Asset:
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
    if commit:
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
    shift_id: UUID | None = None,
    assignment_type: str | None = None,
    force_override: bool = False,
    override_reason: str | None = None,
    planned_end_date: date | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    purpose: str | None = None,
    reservation_id: UUID | None = None,
    commit: bool = True,
) -> AssetAssignment:
    """Create a time-bound assignment after the allocation engine approves it.

    The asset row is locked first so two simultaneous requests for the same slot
    serialise; the second re-reads committed assignments and is rejected.
    """
    from app.models.it_operations import (
        ASSIGNMENT_TYPE_PRIMARY,
        ASSIGNMENT_TYPE_SHIFT_SHARED,
        ASSET_ASSIGNMENT_TYPES,
        ResourceReservation,
    )
    from app.services import resource_allocation_engine as engine

    if asset.is_deleted:
        raise ProTrackValidationError("Cannot assign a deleted asset.")
    if asset.status in {"returned_to_customer", "disposed", "retired"}:
        raise ProTrackValidationError(
            f"Cannot assign an asset with status '{asset.status}'."
        )
    if asset.status not in engine.ASSIGNABLE_ASSET_STATUSES:
        raise ProTrackValidationError(
            f"Asset must be available or assigned to add an occupant "
            f"(current status: {asset.status})."
        )

    resolved_type = (assignment_type or "").strip().upper() or None
    if resolved_type and resolved_type not in ASSET_ASSIGNMENT_TYPES:
        raise ProTrackValidationError(f"Invalid assignment_type: {resolved_type}")

    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("Assignee user not found.")

    engine.lock_resource(db, asset)
    when = assigned_date or date.today()
    request = engine.build_request(
        db,
        start_date=when,
        end_date=planned_end_date,
        shift_id=shift_id,
        start_time=start_time,
        end_time=end_time,
        user_id=user_id,
        reservation_id=reservation_id,
    )
    result = engine.evaluate_asset(db, asset, request)
    if result["reason_code"] == engine.REASON_ALREADY_HOLDS:
        raise ProTrackValidationError(result["reason"], status_code=409)
    engine.raise_if_blocked(result, override=force_override, override_reason=override_reason)
    overridden = not result["available"]

    window = request.window
    if shift_id is not None or not window.all_day:
        resolved_type = resolved_type or ASSIGNMENT_TYPE_SHIFT_SHARED
    resolved_type = resolved_type or ASSIGNMENT_TYPE_PRIMARY
    assignment = AssetAssignment(
        id=uuid4(),
        asset_id=asset.id,
        assigned_to_user_id=user_id,
        assigned_by_user_id=by_user.id,
        shift_id=shift_id,
        # Explicit window: custom times, or "all hours" when no shift was chosen so
        # new rows are never mistaken for legacy assignments needing review.
        start_time=(start_time or None) if (start_time or shift_id) else "00:00",
        end_time=(end_time or None) if (end_time or shift_id) else "24:00",
        planned_end_date=planned_end_date,
        purpose=(purpose or "").strip() or None,
        assignment_type=resolved_type,
        override_reason=(override_reason or "").strip() or None if overridden else None,
        assigned_date=when,
        notes=(notes or "").strip() or None,
    )
    prev_status = asset.status
    if when <= date.today():
        asset.status = "assigned"
    db.add(assignment)
    db.add(asset)
    db.flush()
    if prev_status != asset.status:
        prev = _current_status_period(db, asset.id)
        _end_open_period(prev, on_date=when)
        if prev is not None:
            db.add(prev)
        _open_status_period(db, asset, actor=by_user, on_date=when)

    fulfilled = []
    for res in db.scalars(
        select(ResourceReservation).where(
            ResourceReservation.asset_id == asset.id,
            ResourceReservation.status == "ACTIVE",
            or_(ResourceReservation.id == reservation_id, ResourceReservation.user_id == user_id),
        )
    ).all():
        res.status = "FULFILLED"
        res.released_by_user_id = by_user.id
        res.released_at = datetime.now(timezone.utc).replace(tzinfo=None)
        res.release_reason = "Fulfilled by assignment"
        db.add(res)
        fulfilled.append(str(res.id))

    from app.services import virtual_seat_service

    virtual_seat_service.sync_seats(db, actor=by_user, user_ids={user_id})
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
            "planned_end_date": str(planned_end_date) if planned_end_date else None,
            "shift_id": str(shift_id) if shift_id else None,
            "window": window.label,
            "assignment_type": assignment.assignment_type,
            "purpose": assignment.purpose,
            "override_reason": assignment.override_reason,
            "overridden_conflict": result["reason"] if overridden else None,
            "fulfilled_reservations": fulfilled,
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
    assignment_id: UUID | None = None,
    shift_id: UUID | None = None,
    commit: bool = True,
) -> AssetAssignment:
    open_rows = list_open_assignments(db, asset.id)
    if not open_rows:
        raise ProTrackValidationError("Asset is not currently assigned.")

    assignment: AssetAssignment | None = None
    if assignment_id is not None:
        assignment = next((row for row in open_rows if row.id == assignment_id), None)
        if assignment is None:
            raise ProTrackValidationError("Open assignment not found for this asset.")
    elif shift_id is not None:
        assignment = next((row for row in open_rows if row.shift_id == shift_id), None)
        if assignment is None:
            raise ProTrackValidationError("No open assignment for that shift.")
    else:
        if len(open_rows) > 1:
            raise ProTrackValidationError(
                "Shared desk has multiple open occupants. "
                "Specify assignment_id or shift_id to return one."
            )
        assignment = open_rows[0]

    when = returned_date or date.today()
    assignment.returned_date = when
    assignment.released_by_user_id = by_user.id
    assignment.released_at = datetime.now(timezone.utc).replace(tzinfo=None)
    assignment.return_condition = (return_condition or "").strip() or None
    if notes:
        assignment.notes = (
            f"{assignment.notes}\n{notes}".strip() if assignment.notes else notes.strip()
        )
    remaining = [row for row in open_rows if row.id != assignment.id]
    prev_status = asset.status
    if not remaining:
        asset.status = "available"
    db.add(assignment)
    db.add(asset)
    db.flush()
    if prev_status != asset.status:
        prev = _current_status_period(db, asset.id)
        _end_open_period(prev, on_date=when)
        if prev is not None:
            db.add(prev)
        _open_status_period(db, asset, actor=by_user, on_date=when)
    from app.services import virtual_seat_service

    virtual_seat_service.sync_seats(
        db, actor=by_user, user_ids={assignment.assigned_to_user_id}
    )
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
            "assignment_id": str(assignment.id),
            "shift_id": str(assignment.shift_id) if assignment.shift_id else None,
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
    if original_assignee is not None:
        from app.services import virtual_seat_service

        virtual_seat_service.sync_seats(db, actor=by_user, user_ids={original_assignee})
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


def list_child_assets(db: Session, asset_id: UUID) -> list[Asset]:
    return list(
        db.scalars(
            select(Asset)
            .where(
                Asset.parent_asset_id == asset_id,
                Asset.is_deleted.is_(False),
            )
            .order_by(Asset.asset_number.asc())
        ).all()
    )


def transfer_asset(
    db: Session,
    asset: Asset,
    *,
    to_user_id: UUID,
    by_user: User,
    assigned_date: date | None = None,
    notes: str | None = None,
    include_children: bool = False,
    commit: bool = True,
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
    child_numbers: list[str] = []
    if include_children:
        for child in list_child_assets(db, asset.id):
            transfer_asset(
                db,
                child,
                to_user_id=to_user_id,
                by_user=by_user,
                assigned_date=when,
                notes=notes or f"Cascaded from parent {asset.asset_number}",
                include_children=True,
                commit=False,
            )
            child_numbers.append(child.asset_number)
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
            "include_children": include_children,
            "child_assets": child_numbers,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    if commit:
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
    availability: str | None = None,
    skip: int = 0,
    limit: int = 25,
) -> tuple[list[Computer], int]:
    """availability: all|open|assigned|available|reserved|maintenance|retired|disposed"""
    stmt = (
        select(Computer)
        .options(
            selectinload(Computer.asset).selectinload(Asset.asset_type),
            selectinload(Computer.interfaces),
        )
        .join(Asset, Computer.asset_id == Asset.id)
        .where(Asset.is_deleted.is_(False))
    )
    avail = (availability or "all").strip().lower()
    if avail == "open" or avail == "available":
        stmt = stmt.where(Asset.status == "available")
    elif avail == "assigned":
        stmt = stmt.where(Asset.status == "assigned")
    elif avail == "reserved":
        stmt = stmt.where(Asset.status == "reserved")
    elif avail == "awaiting_return":
        stmt = stmt.where(Asset.status == "awaiting_return")
    elif avail == "maintenance":
        stmt = stmt.where(Asset.status == "maintenance")
    elif avail == "retired":
        stmt = stmt.where(Asset.status == "retired")
    elif avail == "disposed":
        stmt = stmt.where(Asset.status == "disposed")
    if search:
        q = f"%{search.strip()}%"
        nic_mac_match = exists().where(
            ComputerNetworkInterface.computer_id == Computer.id,
            ComputerNetworkInterface.mac_address.ilike(q),
        )
        stmt = stmt.where(
            or_(
                Computer.computer_name.ilike(q),
                Asset.asset_number.ilike(q),
                Computer.mac_address.ilike(q),
                nic_mac_match,
                Asset.make.ilike(q),
                Asset.model.ilike(q),
            )
        )
    rows_all = list(db.scalars(stmt.order_by(Computer.computer_name)).all())
    total = len(rows_all)
    return rows_all[skip : skip + limit], total


def effective_mac_address(computer: Computer) -> str | None:
    """Primary NIC MAC is SoT; computer.mac_address is a denormalized copy."""
    interfaces = list(getattr(computer, "interfaces", None) or [])
    primary = next((row for row in interfaces if row.is_primary and row.is_active), None)
    if primary is None:
        primary = next((row for row in interfaces if row.is_primary), None)
    if primary is not None and primary.mac_address:
        return primary.mac_address
    active = next((row for row in interfaces if row.is_active and row.mac_address), None)
    if active is not None:
        return active.mac_address
    return computer.mac_address


def _sync_primary_mac(
    db: Session, computer: Computer, mac_address: str | None
) -> None:
    """Write MAC to the primary NIC (SoT) and keep computer.mac_address in sync."""
    mac = (mac_address or "").strip() or None
    computer.mac_address = mac
    db.add(computer)
    existing = list_computer_interfaces(db, computer.id)
    if not existing:
        if mac:
            create_computer_interface(
                db,
                computer,
                name="LAN",
                role="lan",
                mac_address=mac,
                is_primary=True,
                commit=False,
            )
        return
    primary = next((row for row in existing if row.is_primary), existing[0])
    primary.mac_address = mac
    if not primary.is_primary:
        for row in existing:
            row.is_primary = row.id == primary.id
            db.add(row)
    db.add(primary)


def get_computer_current_assignee(
    db: Session, asset_id: UUID
) -> tuple[AssetAssignment | None, User | None]:
    assignment = get_current_assignment(db, asset_id)
    if assignment is None:
        return None, None
    user = db.get(User, assignment.assigned_to_user_id)
    return assignment, user


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
    computer_name: str | None = None,
    ip_address_id: UUID | None = None,
    commit: bool = True,
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
            provision_computer=False,
            commit=False,
        )

    type_code = (asset_type.code if asset_type else "PC")[:6]
    from app.services import it_computer_suggest_service as suggest

    preferred_name = (computer_name or "").strip() or None
    if preferred_name:
        if suggest.computer_name_is_taken(db, preferred_name):
            next_name = suggest.suggest_computer_name(db, type_code=type_code)["computer_name"]
            raise ProTrackValidationError(
                f"Computer name '{preferred_name}' is already in use. Suggested: {next_name}"
            )
        allocated_name = preferred_name
    else:
        allocated_name = suggest.suggest_computer_name(db, type_code=type_code)["computer_name"]

    mac = suggest.normalize_mac(mac_address)
    if mac:
        mac_owner = suggest.mac_is_taken(db, mac)
        if mac_owner is not None:
            raise ProTrackValidationError(
                f"MAC address {mac} is already assigned to {mac_owner.computer_name}."
            )

    computer = Computer(
        id=uuid4(),
        asset_id=asset.id,
        computer_name=allocated_name,
        os=(os or "").strip() or None,
        processor=(processor or "").strip() or None,
        ram_gb=ram_gb,
        storage_type=(storage_type or "").strip() or None,
        storage_gb=storage_gb,
        domain_joined=bool(domain_joined),
        mac_address=mac,
    )
    db.add(computer)
    db.flush()
    _open_computer_name_period(
        db, computer, actor=actor, on_date=date.today(), reason="created"
    )
    if mac:
        _ensure_primary_interface(db, computer, mac_address=mac, name="LAN")
    if ip_address_id is not None:
        from app.services import it_network_service

        it_network_service.allocate_ip(
            db,
            actor=actor,
            ip_address_id=ip_address_id,
            assigned_to_asset_id=asset.id,
            hostname=computer.computer_name,
            commit=False,
        )
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
    if commit:
        db.commit()
        db.refresh(computer)
    return computer


def _ensure_primary_interface(
    db: Session,
    computer: Computer,
    *,
    mac_address: str | None,
    name: str = "LAN",
) -> ComputerNetworkInterface:
    existing = list_computer_interfaces(db, computer.id)
    if existing:
        primary = next((row for row in existing if row.is_primary), existing[0])
        if mac_address and not primary.mac_address:
            primary.mac_address = mac_address
            db.add(primary)
        return primary
    return create_computer_interface(
        db,
        computer,
        name=name,
        role="lan",
        mac_address=mac_address,
        is_primary=True,
        commit=False,
    )


def list_computer_interfaces(db: Session, computer_id: UUID) -> list[ComputerNetworkInterface]:
    return list(
        db.scalars(
            select(ComputerNetworkInterface)
            .where(ComputerNetworkInterface.computer_id == computer_id)
            .order_by(
                ComputerNetworkInterface.is_primary.desc(),
                ComputerNetworkInterface.name.asc(),
            )
        ).all()
    )


def get_computer_interface(
    db: Session, interface_id: UUID
) -> ComputerNetworkInterface | None:
    return db.get(ComputerNetworkInterface, interface_id)


def create_computer_interface(
    db: Session,
    computer: Computer,
    *,
    name: str,
    role: str = "lan",
    mac_address: str | None = None,
    is_primary: bool = False,
    is_active: bool = True,
    notes: str | None = None,
    commit: bool = True,
) -> ComputerNetworkInterface:
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ProTrackValidationError("Interface name is required.")
    role_norm = (role or "lan").strip().lower()
    if role_norm not in NIC_ROLES:
        raise ProTrackValidationError(f"Invalid NIC role '{role}'.")
    clash = db.scalar(
        select(ComputerNetworkInterface).where(
            ComputerNetworkInterface.computer_id == computer.id,
            ComputerNetworkInterface.name == cleaned_name,
        )
    )
    if clash is not None:
        raise ProTrackValidationError(f"Interface '{cleaned_name}' already exists on this computer.")
    existing = list_computer_interfaces(db, computer.id)
    make_primary = bool(is_primary) or len(existing) == 0
    if make_primary:
        for row in existing:
            if row.is_primary:
                row.is_primary = False
                db.add(row)
    interface = ComputerNetworkInterface(
        id=uuid4(),
        computer_id=computer.id,
        name=cleaned_name,
        role=role_norm,
        mac_address=(mac_address or "").strip() or None,
        is_primary=make_primary,
        is_active=bool(is_active),
        notes=(notes or "").strip() or None,
    )
    db.add(interface)
    if make_primary and interface.mac_address:
        computer.mac_address = interface.mac_address
        db.add(computer)
    db.flush()
    if commit:
        db.commit()
        db.refresh(interface)
    return interface


def update_computer_interface(
    db: Session,
    interface: ComputerNetworkInterface,
    *,
    name: str | None = None,
    role: str | None = None,
    mac_address: str | None = None,
    is_primary: bool | None = None,
    is_active: bool | None = None,
    notes: str | None = None,
    fields_set: set[str] | None = None,
    commit: bool = True,
) -> ComputerNetworkInterface:
    touched = fields_set or set()
    if name is not None and ("name" in touched or fields_set is None):
        cleaned = name.strip()
        if not cleaned:
            raise ProTrackValidationError("Interface name is required.")
        clash = db.scalar(
            select(ComputerNetworkInterface).where(
                ComputerNetworkInterface.computer_id == interface.computer_id,
                ComputerNetworkInterface.name == cleaned,
                ComputerNetworkInterface.id != interface.id,
            )
        )
        if clash is not None:
            raise ProTrackValidationError(f"Interface '{cleaned}' already exists on this computer.")
        interface.name = cleaned
    if role is not None and ("role" in touched or fields_set is None):
        role_norm = role.strip().lower()
        if role_norm not in NIC_ROLES:
            raise ProTrackValidationError(f"Invalid NIC role '{role}'.")
        interface.role = role_norm
    if "mac_address" in touched or (fields_set is None and mac_address is not None):
        interface.mac_address = (mac_address or "").strip() or None
    if is_active is not None and ("is_active" in touched or fields_set is None):
        interface.is_active = bool(is_active)
    if "notes" in touched or (fields_set is None and notes is not None):
        interface.notes = (notes or "").strip() or None
    if is_primary is True:
        siblings = list_computer_interfaces(db, interface.computer_id)
        for row in siblings:
            if row.id != interface.id and row.is_primary:
                row.is_primary = False
                db.add(row)
        interface.is_primary = True
    elif is_primary is False and ("is_primary" in touched or fields_set is None):
        interface.is_primary = False
    db.add(interface)
    computer = db.get(Computer, interface.computer_id)
    if computer is not None and interface.is_primary and interface.mac_address:
        computer.mac_address = interface.mac_address
        db.add(computer)
    db.flush()
    if commit:
        db.commit()
        db.refresh(interface)
    return interface


def delete_computer_interface(
    db: Session,
    interface: ComputerNetworkInterface,
    *,
    commit: bool = True,
) -> None:
    was_primary = interface.is_primary
    computer_id = interface.computer_id
    db.delete(interface)
    db.flush()
    if was_primary:
        remaining = list_computer_interfaces(db, computer_id)
        if remaining:
            remaining[0].is_primary = True
            db.add(remaining[0])
            computer = db.get(Computer, computer_id)
            if computer is not None:
                computer.mac_address = remaining[0].mac_address
                db.add(computer)
    if commit:
        db.commit()


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
    computer_name: str | None = None,
    computer_name_reason: str | None = None,
    fields_set: set[str] | None = None,
) -> Computer:
    touched = fields_set or set()
    if "computer_name" in touched or (fields_set is None and computer_name is not None):
        apply_computer_name_change(
            db,
            computer,
            computer_name or "",
            actor=actor,
            reason=(computer_name_reason or "").strip() or "manual_update",
        )
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
        from app.services import it_computer_suggest_service as suggest

        mac = suggest.normalize_mac(mac_address)
        if mac:
            mac_owner = suggest.mac_is_taken(db, mac, exclude_computer_id=computer.id)
            if mac_owner is not None:
                raise ProTrackValidationError(
                    f"MAC address {mac} is already assigned to {mac_owner.computer_name}."
                )
        _sync_primary_mac(db, computer, mac)
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
        .options(
            selectinload(Computer.asset).selectinload(Asset.asset_type),
            selectinload(Computer.interfaces),
        )
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


def return_assets_for_user(
    db: Session,
    *,
    user_id: UUID,
    by_user: User,
    returned_date: date | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> list[AssetAssignment]:
    """Return every open assignment held by ``user_id`` (exit / offboard reclaim)."""
    when = returned_date or date.today()
    note = notes or "Returned on employee exit"
    from app.models.it_operations import WorkstationPackageAssignment
    from app.services import workstation_package_service

    seat_rows = db.scalars(
        select(WorkstationPackageAssignment).where(
            WorkstationPackageAssignment.user_id == user_id,
            WorkstationPackageAssignment.status == "ACTIVE",
            or_(
                WorkstationPackageAssignment.effective_to.is_(None),
                WorkstationPackageAssignment.effective_to >= when,
            ),
        )
    ).all()
    for seat_assignment in seat_rows:
        workstation_package_service.return_package_assignment(
            db, seat_assignment, actor=by_user, returned_date=when, notes=note, commit=False
        )
    db.flush()
    open_rows = list(
        db.scalars(
            select(AssetAssignment).where(
                AssetAssignment.assigned_to_user_id == user_id,
                AssetAssignment.returned_date.is_(None),
            )
        ).all()
    )
    returned: list[AssetAssignment] = []
    for assignment in open_rows:
        asset = db.get(Asset, assignment.asset_id)
        if asset is None or asset.is_deleted:
            continue
        returned.append(
            return_asset(
                db,
                asset,
                by_user=by_user,
                returned_date=when,
                notes=note,
                assignment_id=assignment.id,
                commit=False,
            )
        )
    if commit:
        db.commit()
        for row in returned:
            db.refresh(row)
    return returned

