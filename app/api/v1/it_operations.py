"""IT Operations API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth_deps import get_current_user, require_special
from app.api.deps import get_db
from app.core.access_control import (
    MODULE_IT_OPERATIONS,
    SPECIAL_ALLOCATE_IT_IPS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_GENERATE_IT_CREDENTIALS,
    SPECIAL_MANAGE_IT_ACCOUNTS,
    SPECIAL_MANAGE_IT_ASSETS,
    SPECIAL_MANAGE_IT_NETWORKS,
    SPECIAL_MANAGE_IT_SETTINGS,
    SPECIAL_VIEW_IT_OPERATIONS,
    SPECIAL_VIEW_IT_REPORTS,
    user_has_module,
    user_has_special,
)
from app.core.exceptions import ProTrackValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, pagination_query
from app.core.permissions import get_role_name, normalize_role_name
from app.models.it_operations import Asset, AssetAssignment, IPAddress, Network
from app.models.models import Ticket, User
from app.schemas.it_operations import (
    AssetAssignRequest,
    AssetAssignmentRead,
    AssetCreate,
    AssetRead,
    AssetRegisterRow,
    AssetReturnRequest,
    AssetTransferRequest,
    AssetTypeCreate,
    AssetTypeRead,
    AssetTypeUpdate,
    AssetUpdate,
    ComputerCreate,
    ComputerRead,
    ComputerUpdate,
    CredentialGenerateRequest,
    CredentialGenerateResponse,
    IPAllocateRequest,
    IPAllocationReportRow,
    IPAddressRead,
    IPReleaseRequest,
    ITDashboardSummary,
    ITProfileRead,
    ITSettingsRead,
    ITSettingsUpdate,
    ITUserAccountCreate,
    ITUserAccountRead,
    ITUserAccountUpdate,
    NetworkCreate,
    NetworkRead,
    NetworkUpdate,
    OpenITRequestRow,
    PendingITOnboardingTask,
)
from app.services import it_account_service, it_asset_service, it_dashboard_service, it_network_service
from app.services.ticketing_service import OPEN_STATUSES

router = APIRouter(
    prefix="/it",
    tags=["it-operations"],
    dependencies=[Depends(get_current_user)],
)

MODULE = MODULE_IT_OPERATIONS


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code or status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.detail)


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or None


def _role_name(db: Session, user: User) -> str:
    return normalize_role_name(get_role_name(db, user))


def _require_it_access(db: Session, user: User) -> None:
    role = _role_name(db, user)
    if user_has_module(user, role, MODULE_IT_OPERATIONS) or user_has_special(
        user, role, SPECIAL_VIEW_IT_OPERATIONS
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires IT Operations module or view_it_operations permission.",
    )


def _require_reports(db: Session, user: User) -> None:
    role = _role_name(db, user)
    if user_has_special(user, role, SPECIAL_VIEW_IT_REPORTS) or user_has_special(
        user, role, SPECIAL_VIEW_IT_OPERATIONS
    ):
        return
    if user_has_module(user, role, MODULE_IT_OPERATIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires view_it_reports permission.",
    )


def _asset_read(db: Session, asset: Asset) -> AssetRead:
    assignee_id, assignee_name = it_asset_service.assignee_name_for_asset(db, asset)
    at = asset.asset_type
    return AssetRead(
        id=asset.id,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        asset_number=asset.asset_number,
        asset_type_id=asset.asset_type_id,
        asset_type_name=at.name if at else None,
        asset_type_code=at.code if at else None,
        serial_number=asset.serial_number,
        make=asset.make,
        model=asset.model,
        status=asset.status,
        purchase_date=asset.purchase_date,
        purchase_cost=asset.purchase_cost,
        warranty_expiry=asset.warranty_expiry,
        location=asset.location,
        notes=asset.notes,
        is_deleted=asset.is_deleted,
        current_assignee_id=assignee_id,
        current_assignee_name=assignee_name,
    )


def _assignment_read(db: Session, row: AssetAssignment) -> AssetAssignmentRead:
    to_user = db.get(User, row.assigned_to_user_id)
    by_user = db.get(User, row.assigned_by_user_id)
    return AssetAssignmentRead(
        id=row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        asset_id=row.asset_id,
        assigned_to_user_id=row.assigned_to_user_id,
        assigned_to_user_name=_full_name(to_user),
        assigned_by_user_id=row.assigned_by_user_id,
        assigned_by_user_name=_full_name(by_user),
        assigned_date=row.assigned_date,
        returned_date=row.returned_date,
        return_condition=row.return_condition,
        notes=row.notes,
    )


def _computer_read(computer) -> ComputerRead:
    asset = computer.asset
    at = asset.asset_type if asset else None
    return ComputerRead(
        id=computer.id,
        created_at=computer.created_at,
        updated_at=computer.updated_at,
        asset_id=computer.asset_id,
        computer_name=computer.computer_name,
        os=computer.os,
        processor=computer.processor,
        ram_gb=computer.ram_gb,
        storage_type=computer.storage_type,
        storage_gb=computer.storage_gb,
        domain_joined=computer.domain_joined,
        mac_address=computer.mac_address,
        asset_number=asset.asset_number if asset else None,
        asset_type_id=asset.asset_type_id if asset else None,
        asset_type_code=at.code if at else None,
        asset_type_name=at.name if at else None,
        serial_number=asset.serial_number if asset else None,
        make=asset.make if asset else None,
        model=asset.model if asset else None,
        status=asset.status if asset else None,
        location=asset.location if asset else None,
    )


def _network_read(db: Session, network) -> NetworkRead:
    total, available, allocated = it_network_service.network_ip_counts(db, network.id)
    return NetworkRead(
        id=network.id,
        created_at=network.created_at,
        updated_at=network.updated_at,
        name=network.name,
        cidr=network.cidr,
        gateway=network.gateway,
        dns_primary=network.dns_primary,
        dns_secondary=network.dns_secondary,
        vlan_id=network.vlan_id,
        description=network.description,
        is_active=network.is_active,
        ip_total=total,
        ip_available=available,
        ip_allocated=allocated,
    )


def _ip_read(ip: IPAddress) -> IPAddressRead:
    hostname, user_id, asset_id = it_network_service.current_assignment_fields(ip)
    return IPAddressRead(
        id=ip.id,
        created_at=ip.created_at,
        updated_at=ip.updated_at,
        network_id=ip.network_id,
        address=ip.address,
        status=ip.status,
        allocation_type=ip.allocation_type,
        current_hostname=hostname,
        current_assignee_user_id=user_id,
        current_assignee_asset_id=asset_id,
    )


def _account_read(db: Session, account) -> ITUserAccountRead:
    user = db.get(User, account.user_id)
    return ITUserAccountRead(
        id=account.id,
        created_at=account.created_at,
        updated_at=account.updated_at,
        user_id=account.user_id,
        account_type=account.account_type,
        username=account.username,
        display_name=account.display_name,
        status=account.status,
        created_date=account.created_date,
        deactivated_date=account.deactivated_date,
        notes=account.notes,
        user_name=_full_name(user),
    )


def _settings_read(settings) -> ITSettingsRead:
    return ITSettingsRead(
        id=settings.id,
        created_at=settings.created_at,
        updated_at=settings.updated_at,
        asset_numbering_pattern=settings.asset_numbering_pattern,
        computer_naming_pattern=settings.computer_naming_pattern,
        default_domain=settings.default_domain,
        default_email_domain=settings.default_email_domain,
        ip_allocation_strategy=settings.ip_allocation_strategy,
        next_asset_seq=settings.next_asset_seq,
        next_computer_seq=settings.next_computer_seq,
        settings_json=settings.settings_json,
    )


def _profile_for_user(db: Session, user_id: UUID) -> ITProfileRead:
    assets = [_asset_read(db, a) for a in it_asset_service.list_assets_for_user(db, user_id)]
    accounts = [
        _account_read(db, a) for a in it_account_service.list_accounts(db, user_id=user_id)
    ]
    ips = [_ip_read(ip) for ip in it_network_service.list_ips_for_user(db, user_id)]
    return ITProfileRead(user_id=user_id, assets=assets, accounts=accounts, ips=ips)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=ITDashboardSummary)
def it_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return ITDashboardSummary(**it_dashboard_service.dashboard_summary(db))


@router.get("/dashboard/onboarding-tasks", response_model=list[PendingITOnboardingTask])
def it_onboarding_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return [
        PendingITOnboardingTask(**row)
        for row in it_dashboard_service.list_pending_it_onboarding_tasks(db)
    ]


# ---------------------------------------------------------------------------
# Asset types
# ---------------------------------------------------------------------------


@router.get("/asset-types", response_model=list[AssetTypeRead])
def list_asset_types(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return it_asset_service.list_asset_types(db, active_only=active_only)


@router.post(
    "/asset-types",
    response_model=AssetTypeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def create_asset_type(
    payload: AssetTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return it_asset_service.create_asset_type(
            db,
            code=payload.code,
            name=payload.name,
            category=payload.category,
            numbering_prefix=payload.numbering_prefix,
            is_active=payload.is_active,
            actor=current_user,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.patch(
    "/asset-types/{asset_type_id}",
    response_model=AssetTypeRead,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def update_asset_type(
    asset_type_id: UUID,
    payload: AssetTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.it_operations import AssetType

    row = db.get(AssetType, asset_type_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset type not found.")
    try:
        return it_asset_service.update_asset_type(
            db,
            row,
            actor=current_user,
            code=payload.code,
            name=payload.name,
            category=payload.category,
            numbering_prefix=payload.numbering_prefix,
            is_active=payload.is_active,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------


@router.get("/assets", response_model=PaginatedResponse[AssetRead])
def list_assets(
    status_filter: str | None = Query(None, alias="status"),
    asset_type_id: UUID | None = Query(None),
    search: str | None = Query(None),
    pagination: PaginationParams = Depends(pagination_query),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    rows, total = it_asset_service.list_assets(
        db,
        status=status_filter,
        asset_type_id=asset_type_id,
        search=search,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse.build(
        items=[_asset_read(db, r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/assets",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        asset = it_asset_service.create_asset(
            db,
            actor=current_user,
            asset_type_id=payload.asset_type_id,
            serial_number=payload.serial_number,
            make=payload.make,
            model=payload.model,
            purchase_date=payload.purchase_date,
            purchase_cost=payload.purchase_cost,
            warranty_expiry=payload.warranty_expiry,
            location=payload.location,
            notes=payload.notes,
        )
        asset = it_asset_service.get_asset(db, asset.id) or asset
        return _asset_read(db, asset)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.get("/assets/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return _asset_read(db, asset)


@router.patch(
    "/assets/{asset_id}",
    response_model=AssetRead,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def update_asset(
    asset_id: UUID,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    try:
        asset = it_asset_service.update_asset(
            db,
            asset,
            actor=current_user,
            asset_type_id=payload.asset_type_id,
            serial_number=payload.serial_number,
            make=payload.make,
            model=payload.model,
            status=payload.status,
            purchase_date=payload.purchase_date,
            purchase_cost=payload.purchase_cost,
            warranty_expiry=payload.warranty_expiry,
            location=payload.location,
            notes=payload.notes,
            fields_set=set(payload.model_fields_set),
        )
        asset = it_asset_service.get_asset(db, asset.id) or asset
        return _asset_read(db, asset)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.delete(
    "/assets/{asset_id}",
    response_model=AssetRead,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def delete_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    try:
        asset = it_asset_service.soft_delete_asset(db, asset, actor=current_user)
        return _asset_read(db, asset)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "/assets/{asset_id}/assign",
    response_model=AssetAssignmentRead,
    dependencies=[Depends(require_special(SPECIAL_ASSIGN_IT_ASSETS))],
)
def assign_asset(
    asset_id: UUID,
    payload: AssetAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    try:
        row = it_asset_service.assign_asset(
            db,
            asset,
            user_id=payload.user_id,
            by_user=current_user,
            assigned_date=payload.assigned_date,
            notes=payload.notes,
        )
        return _assignment_read(db, row)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "/assets/{asset_id}/return",
    response_model=AssetAssignmentRead,
    dependencies=[Depends(require_special(SPECIAL_ASSIGN_IT_ASSETS))],
)
def return_asset(
    asset_id: UUID,
    payload: AssetReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    try:
        row = it_asset_service.return_asset(
            db,
            asset,
            by_user=current_user,
            returned_date=payload.returned_date,
            return_condition=payload.return_condition,
            notes=payload.notes,
        )
        return _assignment_read(db, row)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "/assets/{asset_id}/transfer",
    response_model=AssetAssignmentRead,
    dependencies=[Depends(require_special(SPECIAL_ASSIGN_IT_ASSETS))],
)
def transfer_asset(
    asset_id: UUID,
    payload: AssetTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    try:
        row = it_asset_service.transfer_asset(
            db,
            asset,
            to_user_id=payload.to_user_id,
            by_user=current_user,
            assigned_date=payload.assigned_date,
            notes=payload.notes,
        )
        return _assignment_read(db, row)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.get("/assets/{asset_id}/assignments", response_model=list[AssetAssignmentRead])
def list_asset_assignments(
    asset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    asset = it_asset_service.get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return [
        _assignment_read(db, row)
        for row in it_asset_service.list_asset_assignments(db, asset_id)
    ]


# ---------------------------------------------------------------------------
# Computers
# ---------------------------------------------------------------------------


@router.get("/computers", response_model=PaginatedResponse[ComputerRead])
def list_computers(
    search: str | None = Query(None),
    pagination: PaginationParams = Depends(pagination_query),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    rows, total = it_asset_service.list_computers(
        db, search=search, skip=pagination.skip, limit=pagination.limit
    )
    return PaginatedResponse.build(
        items=[_computer_read(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/computers",
    response_model=ComputerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def create_computer(
    payload: ComputerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        computer = it_asset_service.create_computer(
            db,
            actor=current_user,
            asset_type_id=payload.asset_type_id,
            asset_id=payload.asset_id,
            os=payload.os,
            processor=payload.processor,
            ram_gb=payload.ram_gb,
            storage_type=payload.storage_type,
            storage_gb=payload.storage_gb,
            domain_joined=payload.domain_joined,
            mac_address=payload.mac_address,
            serial_number=payload.serial_number,
            make=payload.make,
            model=payload.model,
            purchase_date=payload.purchase_date,
            purchase_cost=payload.purchase_cost,
            warranty_expiry=payload.warranty_expiry,
            location=payload.location,
            notes=payload.notes,
        )
        computer = it_asset_service.get_computer(db, computer.id) or computer
        return _computer_read(computer)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.patch(
    "/computers/{computer_id}",
    response_model=ComputerRead,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ASSETS))],
)
def update_computer(
    computer_id: UUID,
    payload: ComputerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    computer = it_asset_service.get_computer(db, computer_id)
    if computer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Computer not found.")
    try:
        computer = it_asset_service.update_computer(
            db,
            computer,
            actor=current_user,
            os=payload.os,
            processor=payload.processor,
            ram_gb=payload.ram_gb,
            storage_type=payload.storage_type,
            storage_gb=payload.storage_gb,
            domain_joined=payload.domain_joined,
            mac_address=payload.mac_address,
            fields_set=set(payload.model_fields_set),
        )
        computer = it_asset_service.get_computer(db, computer.id) or computer
        return _computer_read(computer)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


# ---------------------------------------------------------------------------
# Networks / IPs
# ---------------------------------------------------------------------------


@router.get("/networks", response_model=list[NetworkRead])
def list_networks(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return [
        _network_read(db, n)
        for n in it_network_service.list_networks(db, active_only=active_only)
    ]


@router.post(
    "/networks",
    response_model=NetworkRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_NETWORKS))],
)
def create_network(
    payload: NetworkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        network = it_network_service.create_network(
            db,
            actor=current_user,
            name=payload.name,
            cidr=payload.cidr,
            gateway=payload.gateway,
            dns_primary=payload.dns_primary,
            dns_secondary=payload.dns_secondary,
            vlan_id=payload.vlan_id,
            description=payload.description,
            is_active=payload.is_active,
        )
        return _network_read(db, network)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.patch(
    "/networks/{network_id}",
    response_model=NetworkRead,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_NETWORKS))],
)
def update_network(
    network_id: UUID,
    payload: NetworkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    network = it_network_service.get_network(db, network_id)
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found.")
    try:
        network = it_network_service.update_network(
            db,
            network,
            actor=current_user,
            name=payload.name,
            gateway=payload.gateway,
            dns_primary=payload.dns_primary,
            dns_secondary=payload.dns_secondary,
            vlan_id=payload.vlan_id,
            description=payload.description,
            is_active=payload.is_active,
            fields_set=set(payload.model_fields_set),
        )
        return _network_read(db, network)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.get("/networks/{network_id}/ips", response_model=list[IPAddressRead])
def list_network_ips(
    network_id: UUID,
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    network = it_network_service.get_network(db, network_id)
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found.")
    return [
        _ip_read(ip)
        for ip in it_network_service.list_ips(db, network_id, status=status_filter)
    ]


@router.post(
    "/ips/allocate",
    response_model=IPAddressRead,
    dependencies=[Depends(require_special(SPECIAL_ALLOCATE_IT_IPS))],
)
def allocate_ip(
    payload: IPAllocateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ip = it_network_service.allocate_ip(
            db,
            actor=current_user,
            ip_address_id=payload.ip_address_id,
            network_id=payload.network_id,
            assigned_to_asset_id=payload.assigned_to_asset_id,
            assigned_to_user_id=payload.assigned_to_user_id,
            hostname=payload.hostname,
            notes=payload.notes,
            allocation_type=payload.allocation_type,
        )
        ip = it_network_service.get_ip(db, ip.id) or ip
        return _ip_read(ip)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "/ips/{ip_id}/release",
    response_model=IPAddressRead,
    dependencies=[Depends(require_special(SPECIAL_ALLOCATE_IT_IPS))],
)
def release_ip(
    ip_id: UUID,
    payload: IPReleaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = it_network_service.get_ip(db, ip_id)
    if ip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="IP address not found.")
    try:
        ip = it_network_service.release_ip(
            db, ip, actor=current_user, notes=payload.notes
        )
        ip = it_network_service.get_ip(db, ip.id) or ip
        return _ip_read(ip)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


@router.get("/accounts", response_model=list[ITUserAccountRead])
def list_accounts(
    user_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return [
        _account_read(db, a)
        for a in it_account_service.list_accounts(db, user_id=user_id, status=status_filter)
    ]


@router.post(
    "/accounts",
    response_model=ITUserAccountRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ACCOUNTS))],
)
def create_account(
    payload: ITUserAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        account = it_account_service.create_account(
            db,
            actor=current_user,
            user_id=payload.user_id,
            account_type=payload.account_type,
            username=payload.username,
            display_name=payload.display_name,
            status=payload.status,
            created_date=payload.created_date,
            notes=payload.notes,
        )
        return _account_read(db, account)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.patch(
    "/accounts/{account_id}",
    response_model=ITUserAccountRead,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_ACCOUNTS))],
)
def update_account(
    account_id: UUID,
    payload: ITUserAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = it_account_service.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    try:
        account = it_account_service.update_account(
            db,
            account,
            actor=current_user,
            username=payload.username,
            display_name=payload.display_name,
            status=payload.status,
            deactivated_date=payload.deactivated_date,
            notes=payload.notes,
            fields_set=set(payload.model_fields_set),
        )
        return _account_read(db, account)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post(
    "/accounts/generate-credential",
    response_model=CredentialGenerateResponse,
    dependencies=[Depends(require_special(SPECIAL_GENERATE_IT_CREDENTIALS))],
)
def generate_credential(
    payload: CredentialGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        account, otp = it_account_service.generate_credential(
            db,
            actor=current_user,
            user_id=payload.user_id,
            account_type=payload.account_type,
            username=payload.username,
        )
        return CredentialGenerateResponse(
            account=_account_read(db, account),
            one_time_password=otp,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get("/profile/me", response_model=ITProfileRead)
def my_it_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _profile_for_user(db, current_user.id)


@router.get("/profile/{user_id}", response_model=ITProfileRead)
def user_it_profile(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.id:
        _require_it_access(db, current_user)
    target = db.get(User, user_id)
    if target is None or target.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _profile_for_user(db, user_id)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=ITSettingsRead)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_it_access(db, current_user)
    return _settings_read(it_dashboard_service.get_settings(db))


@router.put(
    "/settings",
    response_model=ITSettingsRead,
    dependencies=[Depends(require_special(SPECIAL_MANAGE_IT_SETTINGS))],
)
def put_settings(
    payload: ITSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = it_dashboard_service.update_settings(
        db,
        actor=current_user,
        asset_numbering_pattern=payload.asset_numbering_pattern,
        computer_naming_pattern=payload.computer_naming_pattern,
        default_domain=payload.default_domain,
        default_email_domain=payload.default_email_domain,
        ip_allocation_strategy=payload.ip_allocation_strategy,
        settings_json=payload.settings_json,
        fields_set=set(payload.model_fields_set),
    )
    return _settings_read(settings)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/asset-register", response_model=list[AssetRegisterRow])
def report_asset_register(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_reports(db, current_user)
    rows, _ = it_asset_service.list_assets(db, skip=0, limit=500)
    out: list[AssetRegisterRow] = []
    for asset in rows:
        assignee_id, assignee_name = it_asset_service.assignee_name_for_asset(db, asset)
        at = asset.asset_type
        out.append(
            AssetRegisterRow(
                asset_number=asset.asset_number,
                asset_type_code=at.code if at else None,
                asset_type_name=at.name if at else None,
                make=asset.make,
                model=asset.model,
                serial_number=asset.serial_number,
                status=asset.status,
                location=asset.location,
                purchase_date=asset.purchase_date,
                purchase_cost=asset.purchase_cost,
                warranty_expiry=asset.warranty_expiry,
                current_assignee_name=assignee_name,
            )
        )
    return out


@router.get("/reports/ip-allocation", response_model=list[IPAllocationReportRow])
def report_ip_allocation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_reports(db, current_user)
    ips = list(
        db.scalars(
            select(IPAddress)
            .options(selectinload(IPAddress.assignment_history))
            .where(IPAddress.status == "allocated")
            .order_by(IPAddress.address)
        ).all()
    )
    out: list[IPAllocationReportRow] = []
    for ip in ips:
        network = db.get(Network, ip.network_id)
        hostname, user_id, asset_id = it_network_service.current_assignment_fields(ip)
        user_name = _full_name(db.get(User, user_id)) if user_id else None
        asset_number = None
        assigned_date = None
        for hist in ip.assignment_history or []:
            if hist.released_date is None:
                assigned_date = hist.assigned_date
                break
        if asset_id:
            asset = db.get(Asset, asset_id)
            asset_number = asset.asset_number if asset else None
        out.append(
            IPAllocationReportRow(
                network_name=network.name if network else "",
                address=ip.address,
                status=ip.status,
                hostname=hostname,
                assigned_to_user_name=user_name,
                assigned_to_asset_number=asset_number,
                assigned_date=assigned_date,
            )
        )
    return out


@router.get("/reports/open-requests", response_model=list[OpenITRequestRow])
def report_open_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_reports(db, current_user)
    tickets = list(
        db.scalars(
            select(Ticket)
            .options(selectinload(Ticket.requester), selectinload(Ticket.assignee))
            .where(Ticket.category == "it", Ticket.status.in_(OPEN_STATUSES))
            .order_by(Ticket.created_at.desc())
        ).all()
    )
    return [
        OpenITRequestRow(
            id=t.id,
            ticket_number=t.ticket_number,
            title=t.title,
            status=t.status,
            priority=t.priority,
            requester_name=_full_name(t.requester),
            assignee_name=_full_name(t.assignee),
            created_at=t.created_at,
        )
        for t in tickets
    ]
