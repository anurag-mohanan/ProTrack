"""Resource package templates and transactional assignment into IT SoT tables."""

from __future__ import annotations

from collections import Counter
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import MODULE_RESOURCE_PLANNING
from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    SOFTWARE_REQUIREMENT_LEVELS,
    Asset,
    AssetAssignment,
    AssetType,
    Computer,
    IPAddress,
    ResourcePackage,
    ResourcePackageHardwareLine,
    ResourcePackageSoftwareLine,
    SoftwareCatalog,
)
from app.models.models import User
from app.services import it_asset_service, it_network_service, it_software_service
from app.services.activity_service import log_activity
from app.services.resource_shift_service import (
    ShiftConflictError,
    ShiftValidationError,
    assign_shift,
    get_employee_shift,
)

UNAVAILABLE_ASSET_STATUSES = frozenset(
    {
        "retired",
        "disposed",
        "returned_to_customer",
        "lost",
        "decommissioned",
        "maintenance",
        "broken",
        "awaiting_return",
    }
)
CANDIDATE_LIMIT = 20


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _code(value: str) -> str:
    cleaned = (value or "").strip().upper().replace(" ", "-")
    if not cleaned:
        raise ProTrackValidationError("Package code is required.")
    return cleaned[:40]


def get_package(db: Session, package_id: UUID) -> ResourcePackage | None:
    return db.scalar(
        select(ResourcePackage)
        .options(
            selectinload(ResourcePackage.hardware_lines).selectinload(
                ResourcePackageHardwareLine.asset_type
            ),
            selectinload(ResourcePackage.software_lines).selectinload(
                ResourcePackageSoftwareLine.software
            ),
        )
        .where(ResourcePackage.id == package_id)
    )


def list_packages(db: Session, *, active_only: bool = False) -> list[ResourcePackage]:
    stmt = (
        select(ResourcePackage)
        .options(
            selectinload(ResourcePackage.hardware_lines).selectinload(
                ResourcePackageHardwareLine.asset_type
            ),
            selectinload(ResourcePackage.software_lines).selectinload(
                ResourcePackageSoftwareLine.software
            ),
        )
        .order_by(ResourcePackage.name)
    )
    if active_only:
        stmt = stmt.where(ResourcePackage.is_active.is_(True))
    return list(db.scalars(stmt).all())


def _replace_lines(
    db: Session,
    package: ResourcePackage,
    *,
    hardware_lines: list[dict] | None,
    software_lines: list[dict] | None,
) -> None:
    if hardware_lines is not None:
        package.hardware_lines.clear()
        db.flush()
        seen_types: set[UUID] = set()
        for line in hardware_lines:
            asset_type_id = line["asset_type_id"]
            if asset_type_id in seen_types:
                raise ProTrackValidationError("Duplicate asset type on package hardware lines.")
            seen_types.add(asset_type_id)
            asset_type = db.get(AssetType, asset_type_id)
            if asset_type is None or not asset_type.is_active:
                raise ProTrackValidationError("Asset type not found or inactive.")
            qty = int(line.get("quantity") or 1)
            if qty < 1:
                raise ProTrackValidationError("Hardware quantity must be at least 1.")
            package.hardware_lines.append(
                ResourcePackageHardwareLine(
                    id=uuid4(),
                    asset_type_id=asset_type_id,
                    quantity=qty,
                    is_required=bool(line.get("is_required", True)),
                )
            )
    if software_lines is not None:
        package.software_lines.clear()
        db.flush()
        seen_sw: set[UUID] = set()
        for line in software_lines:
            software_id = line["software_id"]
            if software_id in seen_sw:
                raise ProTrackValidationError("Duplicate software on package software lines.")
            seen_sw.add(software_id)
            software = db.get(SoftwareCatalog, software_id)
            if software is None:
                raise ProTrackValidationError("Software catalog entry not found.")
            level = str(line.get("requirement_level") or "required").strip().lower()
            if level not in SOFTWARE_REQUIREMENT_LEVELS:
                raise ProTrackValidationError(
                    f"Invalid requirement_level. Allowed: {sorted(SOFTWARE_REQUIREMENT_LEVELS)}"
                )
            seats = int(line.get("seats") or 1)
            if seats < 1:
                raise ProTrackValidationError("Software seats must be at least 1.")
            package.software_lines.append(
                ResourcePackageSoftwareLine(
                    id=uuid4(),
                    software_id=software_id,
                    requirement_level=level,
                    seats=seats,
                )
            )


def create_package(
    db: Session,
    *,
    code: str,
    name: str,
    description: str | None = None,
    requires_ip: bool = False,
    is_active: bool = True,
    hardware_lines: list[dict] | None = None,
    software_lines: list[dict] | None = None,
) -> ResourcePackage:
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ProTrackValidationError("Package name is required.")
    code_val = _code(code)
    existing = db.scalar(
        select(ResourcePackage).where(func.lower(ResourcePackage.code) == code_val.lower())
    )
    if existing is not None:
        raise ProTrackValidationError("A package with this code already exists.")
    package = ResourcePackage(
        id=uuid4(),
        code=code_val,
        name=cleaned_name,
        description=_optional_str(description),
        requires_ip=bool(requires_ip),
        is_active=bool(is_active),
    )
    db.add(package)
    db.flush()
    _replace_lines(db, package, hardware_lines=hardware_lines or [], software_lines=software_lines or [])
    db.commit()
    return get_package(db, package.id) or package


def update_package(
    db: Session,
    package: ResourcePackage,
    *,
    code: str | None = None,
    name: str | None = None,
    description: str | None = None,
    requires_ip: bool | None = None,
    is_active: bool | None = None,
    hardware_lines: list[dict] | None = None,
    software_lines: list[dict] | None = None,
    fields_set: set[str] | None = None,
) -> ResourcePackage:
    touched = fields_set or set()
    if "code" in touched or (fields_set is None and code is not None):
        code_val = _code(code or package.code)
        clash = db.scalar(
            select(ResourcePackage).where(
                func.lower(ResourcePackage.code) == code_val.lower(),
                ResourcePackage.id != package.id,
            )
        )
        if clash is not None:
            raise ProTrackValidationError("A package with this code already exists.")
        package.code = code_val
    if "name" in touched or (fields_set is None and name is not None):
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise ProTrackValidationError("Package name is required.")
        package.name = cleaned_name
    if "description" in touched or (fields_set is None and description is not None):
        package.description = _optional_str(description)
    if "requires_ip" in touched or (fields_set is None and requires_ip is not None):
        package.requires_ip = bool(requires_ip)
    if "is_active" in touched or (fields_set is None and is_active is not None):
        package.is_active = bool(is_active)
    if hardware_lines is not None or software_lines is not None:
        _replace_lines(
            db,
            package,
            hardware_lines=hardware_lines if hardware_lines is not None else None,
            software_lines=software_lines if software_lines is not None else None,
        )
    db.add(package)
    db.commit()
    return get_package(db, package.id) or package


def deactivate_package(db: Session, package: ResourcePackage) -> ResourcePackage:
    package.is_active = False
    db.add(package)
    db.commit()
    db.refresh(package)
    return package


def _open_assignment_asset_ids(db: Session, on_date: date) -> set[UUID]:
    return set(
        db.scalars(
            select(AssetAssignment.asset_id).where(
                AssetAssignment.assigned_date <= on_date,
                or_(
                    AssetAssignment.returned_date.is_(None),
                    AssetAssignment.returned_date > on_date,
                ),
            )
        ).all()
    )


def _available_assets_of_type(
    db: Session,
    asset_type_id: UUID,
    on_date: date,
) -> list[Asset]:
    occupied = _open_assignment_asset_ids(db, on_date)
    stmt = select(Asset).where(
        Asset.asset_type_id == asset_type_id,
        Asset.is_deleted.is_(False),
        Asset.status == "available",
    )
    assets = [row for row in db.scalars(stmt).all() if row.id not in occupied]
    return assets


def _shift_payload(shift) -> dict | None:
    if shift is None:
        return None
    return {
        "id": str(shift.id),
        "name": shift.name,
        "code": shift.code,
        "start_time": str(shift.start_time) if getattr(shift, "start_time", None) else None,
        "end_time": str(shift.end_time) if getattr(shift, "end_time", None) else None,
    }


def preview_package_assignment(
    db: Session,
    *,
    user_id: UUID,
    package_id: UUID,
    on_date: date | None = None,
) -> dict:
    on_date = on_date or date.today()
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("User not found.")
    package = get_package(db, package_id)
    if package is None:
        raise ProTrackValidationError("Resource package not found.")
    if not package.is_active:
        raise ProTrackValidationError("Resource package is inactive.")

    hardware: list[dict] = []
    shortages: list[str] = []
    for line in package.hardware_lines:
        candidates = _available_assets_of_type(db, line.asset_type_id, on_date)
        available = len(candidates)
        type_name = line.asset_type.name if line.asset_type else str(line.asset_type_id)
        if line.is_required and available < line.quantity:
            shortages.append(
                f"{type_name}: need {line.quantity}, available {available}"
            )
        hardware.append(
            {
                "asset_type_id": str(line.asset_type_id),
                "asset_type_name": type_name,
                "quantity": line.quantity,
                "is_required": line.is_required,
                "available_count": available,
                "candidates": [
                    {
                        "id": str(asset.id),
                        "asset_number": asset.asset_number,
                        "status": asset.status,
                        "make": asset.make,
                        "model": asset.model,
                    }
                    for asset in candidates[:CANDIDATE_LIMIT]
                ],
            }
        )

    software: list[dict] = []
    for line in package.software_lines:
        pools = it_software_service.list_license_pools(
            db, software_id=line.software_id, include_expired=False
        )
        pool_rows = []
        total_seats = 0
        for pool in pools:
            seats = it_software_service.available_seats(db, pool)
            total_seats += seats
            pool_rows.append(
                {
                    "id": str(pool.id),
                    "seat_count": pool.seat_count,
                    "available_seats": seats,
                    "license_type": pool.license_type,
                    "status": getattr(pool, "status", None) or "active",
                }
            )
        sw_name = line.software.name if line.software else str(line.software_id)
        if line.requirement_level == "required" and total_seats < line.seats:
            shortages.append(f"{sw_name}: need {line.seats} seat(s), available {total_seats}")
        software.append(
            {
                "software_id": str(line.software_id),
                "software_name": sw_name,
                "requirement_level": line.requirement_level,
                "seats": line.seats,
                "available_seats": total_seats,
                "pools": pool_rows,
            }
        )

    ip_available = int(
        db.scalar(select(func.count()).select_from(IPAddress).where(IPAddress.status == "available"))
        or 0
    )
    ip_candidates = [
        {"id": str(ip.id), "address": ip.address, "network_id": str(ip.network_id)}
        for ip in db.scalars(
            select(IPAddress)
            .where(IPAddress.status == "available")
            .order_by(IPAddress.address)
            .limit(CANDIDATE_LIMIT)
        ).all()
    ]
    if package.requires_ip and ip_available < 1:
        shortages.append("IP: none available")

    shift = get_employee_shift(db, user_id, on_date)
    return {
        "user_id": str(user_id),
        "user_name": f"{user.first_name} {user.last_name}".strip(),
        "package_id": str(package.id),
        "package_code": package.code,
        "package_name": package.name,
        "requires_ip": package.requires_ip,
        "on_date": on_date.isoformat(),
        "shift": _shift_payload(shift),
        "hardware": hardware,
        "software": software,
        "ip": {
            "required": package.requires_ip,
            "available_count": ip_available,
            "candidates": ip_candidates,
        },
        "shortages": shortages,
        "can_assign_without_override": not shortages,
    }


def _validate_assign_selection(
    db: Session,
    package: ResourcePackage,
    *,
    asset_ids: list[UUID],
    license_pool_ids: list[UUID],
    ip_address_id: UUID | None,
    network_id: UUID | None,
    on_date: date,
) -> list[Asset]:
    assets: list[Asset] = []
    for asset_id in asset_ids:
        asset = db.get(Asset, asset_id)
        if asset is None or asset.is_deleted:
            raise ProTrackValidationError("Selected asset not found.")
        assets.append(asset)

    by_type = Counter(asset.asset_type_id for asset in assets)
    selected_types = set(by_type)
    allowed_types = {line.asset_type_id for line in package.hardware_lines}
    extra = selected_types - allowed_types
    if extra:
        raise ProTrackValidationError("Selected assets include types not in this package.")
    for line in package.hardware_lines:
        count = by_type.get(line.asset_type_id, 0)
        type_name = line.asset_type.name if line.asset_type else str(line.asset_type_id)
        if line.is_required and count < line.quantity:
            raise ProTrackValidationError(
                f"Select {line.quantity} {type_name} asset(s) (got {count})."
            )
        if count > line.quantity:
            raise ProTrackValidationError(
                f"Too many {type_name} assets selected ({count}; package allows {line.quantity})."
            )

    required_software = {
        line.software_id: line.seats
        for line in package.software_lines
        if line.requirement_level == "required"
    }
    covered: Counter[UUID] = Counter()
    for pool_id in license_pool_ids:
        pool = it_software_service.get_license_pool(db, pool_id)
        if pool is None:
            raise ProTrackValidationError("License pool not found.")
        covered[pool.software_id] += 1
    for software_id, seats in required_software.items():
        if covered.get(software_id, 0) < seats:
            software = db.get(SoftwareCatalog, software_id)
            name = software.name if software else str(software_id)
            raise ProTrackValidationError(f"Select a license pool for {name}.")

    if package.requires_ip and ip_address_id is None and network_id is None:
        raise ProTrackValidationError("This package requires an IP assignment.")
    if ip_address_id is not None and network_id is not None:
        raise ProTrackValidationError("Provide only one of ip_address_id or network_id.")

    occupied = _open_assignment_asset_ids(db, on_date)
    for asset in assets:
        if asset.id in occupied:
            raise ProTrackValidationError(
                f"Asset {asset.asset_number} is already assigned."
            )
        if asset.status in UNAVAILABLE_ASSET_STATUSES:
            raise ProTrackValidationError(
                f"Asset {asset.asset_number} is not available (status={asset.status})."
            )
    return assets


def assign_package(
    db: Session,
    *,
    actor: User,
    user_id: UUID,
    package_id: UUID,
    asset_ids: list[UUID] | None = None,
    license_pool_ids: list[UUID] | None = None,
    shift_id: UUID | None = None,
    ip_address_id: UUID | None = None,
    network_id: UUID | None = None,
    notes: str | None = None,
    assigned_date: date | None = None,
) -> dict:
    on_date = assigned_date or date.today()
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise ProTrackValidationError("User not found.")
    package = get_package(db, package_id)
    if package is None:
        raise ProTrackValidationError("Resource package not found.")
    if not package.is_active:
        raise ProTrackValidationError("Resource package is inactive.")

    asset_ids = list(asset_ids or [])
    license_pool_ids = list(license_pool_ids or [])
    assets = _validate_assign_selection(
        db,
        package,
        asset_ids=asset_ids,
        license_pool_ids=license_pool_ids,
        ip_address_id=ip_address_id,
        network_id=network_id,
        on_date=on_date,
    )

    created_asset_ids: list[str] = []
    created_assignment_ids: list[str] = []
    allocated_ip_id: str | None = None
    shift_assignment_id: str | None = None

    try:
        if shift_id is not None:
            shift_row = assign_shift(
                db,
                {
                    "user_id": user_id,
                    "shift_id": shift_id,
                    "effective_from": on_date,
                    "assignment_type": "permanent",
                    "end_date_existing": True,
                    "notes": notes,
                },
                commit=False,
            )
            shift_assignment_id = str(shift_row.id)

        for asset in assets:
            assignment = it_asset_service.assign_asset(
                db,
                asset,
                user_id=user_id,
                by_user=actor,
                assigned_date=on_date,
                notes=notes,
                shift_id=shift_id,
                commit=False,
            )
            created_asset_ids.append(str(asset.id))
            created_assignment_ids.append(str(assignment.id))

        computer_id = None
        for asset in assets:
            computer = db.scalar(select(Computer).where(Computer.asset_id == asset.id))
            if computer is not None:
                computer_id = computer.id
                break

        for pool_id in license_pool_ids:
            it_software_service.assign_license(
                db,
                license_pool_id=pool_id,
                user_id=user_id,
                computer_id=computer_id,
                assigned_date=on_date,
                notes=notes,
                commit=False,
            )

        if ip_address_id is not None or network_id is not None:
            computer_asset_id = assets[0].id if assets else None
            ip = it_network_service.allocate_ip(
                db,
                actor=actor,
                ip_address_id=ip_address_id,
                network_id=network_id,
                assigned_to_asset_id=computer_asset_id,
                assigned_to_user_id=user_id,
                notes=notes,
                commit=False,
            )
            allocated_ip_id = str(ip.id)

        existing_req = {
            row.software_id
            for row in it_software_service.list_requirements(
                db, user_id=user_id, active_on=on_date
            )
        }
        for line in package.software_lines:
            if line.software_id in existing_req:
                continue
            it_software_service.create_requirement(
                db,
                user_id=user_id,
                software_id=line.software_id,
                requirement_level=line.requirement_level,
                reason=f"Package {package.code}",
                notes=notes,
                commit=False,
            )

        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_resource_package,
            entity_id=package.id,
            action=ActivityAction.it_resource_package_assigned,
            new_value={
                "user_id": str(user_id),
                "package_id": str(package.id),
                "package_code": package.code,
                "asset_ids": created_asset_ids,
                "license_pool_ids": [str(x) for x in license_pool_ids],
                "shift_id": str(shift_id) if shift_id else None,
                "ip_address_id": allocated_ip_id,
            },
            outcome="success",
            module=MODULE_RESOURCE_PLANNING,
            commit=False,
        )
        db.commit()
    except (ProTrackValidationError, ShiftValidationError, ShiftConflictError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return {
        "package_id": str(package.id),
        "user_id": str(user_id),
        "asset_ids": created_asset_ids,
        "assignment_ids": created_assignment_ids,
        "license_pool_ids": [str(x) for x in license_pool_ids],
        "shift_assignment_id": shift_assignment_id,
        "ip_address_id": allocated_ip_id,
    }
