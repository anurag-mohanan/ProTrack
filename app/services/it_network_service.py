"""IT network and IP allocation workflows."""

from __future__ import annotations

import ipaddress
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import MODULE_IT_OPERATIONS
from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import IPAddress, IPAssignmentHistory, Network
from app.models.models import User
from app.services.activity_service import log_activity

MODULE = MODULE_IT_OPERATIONS
AUTO_GENERATE_MIN_PREFIX = 24  # /24 and smaller (more specific) only
MAX_AUTO_IPS = 1024


def _parse_network(cidr: str) -> ipaddress.IPv4Network:
    try:
        return ipaddress.IPv4Network(cidr.strip(), strict=False)
    except ValueError as exc:
        raise ProTrackValidationError(f"Invalid CIDR: {cidr}") from exc


def network_ip_counts(db: Session, network_id: UUID) -> tuple[int, int, int]:
    rows = db.execute(
        select(IPAddress.status, func.count())
        .where(IPAddress.network_id == network_id)
        .group_by(IPAddress.status)
    ).all()
    by_status = {status: int(count) for status, count in rows}
    total = sum(by_status.values())
    available = by_status.get("available", 0)
    allocated = by_status.get("allocated", 0)
    return total, available, allocated


def get_network(db: Session, network_id: UUID) -> Network | None:
    return db.scalar(
        select(Network)
        .options(selectinload(Network.ip_addresses))
        .where(Network.id == network_id)
    )


def list_networks(db: Session, *, active_only: bool = False) -> list[Network]:
    stmt = select(Network).order_by(Network.name)
    if active_only:
        stmt = stmt.where(Network.is_active.is_(True))
    return list(db.scalars(stmt).all())


def create_network(
    db: Session,
    *,
    actor: User,
    name: str,
    cidr: str,
    gateway: str | None = None,
    dns_primary: str | None = None,
    dns_secondary: str | None = None,
    vlan_id: int | None = None,
    description: str | None = None,
    is_active: bool = True,
) -> Network:
    net = _parse_network(cidr)
    network = Network(
        id=uuid4(),
        name=name.strip(),
        cidr=str(net),
        gateway=(gateway or "").strip() or None,
        dns_primary=(dns_primary or "").strip() or None,
        dns_secondary=(dns_secondary or "").strip() or None,
        vlan_id=vlan_id,
        description=(description or "").strip() or None,
        is_active=bool(is_active),
    )
    db.add(network)
    db.flush()

    # Auto-generate usable hosts only for /24 and smaller.
    if net.prefixlen >= AUTO_GENERATE_MIN_PREFIX:
        hosts = list(net.hosts())
        if len(hosts) > MAX_AUTO_IPS:
            raise ProTrackValidationError(
                f"CIDR {net} has {len(hosts)} usable hosts; max auto-generation is {MAX_AUTO_IPS}."
            )
        for host in hosts:
            db.add(
                IPAddress(
                    id=uuid4(),
                    network_id=network.id,
                    address=str(host),
                    status="available",
                )
            )
        db.flush()
    else:
        # Larger ranges: optionally reserve gateway if provided.
        if gateway:
            try:
                gw = ipaddress.IPv4Address(gateway.strip())
                if gw in net:
                    db.add(
                        IPAddress(
                            id=uuid4(),
                            network_id=network.id,
                            address=str(gw),
                            status="reserved",
                            allocation_type="gateway",
                        )
                    )
                    db.flush()
            except ValueError:
                pass

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_network,
        entity_id=network.id,
        action=ActivityAction.it_network_created,
        new_value={"name": network.name, "cidr": network.cidr},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(network)
    return network


def update_network(
    db: Session,
    network: Network,
    *,
    actor: User,
    name: str | None = None,
    gateway: str | None = None,
    dns_primary: str | None = None,
    dns_secondary: str | None = None,
    vlan_id: int | None = None,
    description: str | None = None,
    is_active: bool | None = None,
    fields_set: set[str] | None = None,
) -> Network:
    touched = fields_set or set()
    if "name" in touched or (fields_set is None and name is not None):
        network.name = (name or "").strip() or network.name
    if "gateway" in touched or (fields_set is None and gateway is not None):
        network.gateway = (gateway or "").strip() or None
    if "dns_primary" in touched or (fields_set is None and dns_primary is not None):
        network.dns_primary = (dns_primary or "").strip() or None
    if "dns_secondary" in touched or (fields_set is None and dns_secondary is not None):
        network.dns_secondary = (dns_secondary or "").strip() or None
    if "vlan_id" in touched or (fields_set is None and vlan_id is not None):
        network.vlan_id = vlan_id
    if "description" in touched or (fields_set is None and description is not None):
        network.description = (description or "").strip() or None
    if "is_active" in touched or (fields_set is None and is_active is not None):
        network.is_active = bool(is_active)
    db.add(network)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_network,
        entity_id=network.id,
        action=ActivityAction.it_network_updated,
        new_value={"name": network.name, "is_active": network.is_active},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(network)
    return network


def add_manual_ip(
    db: Session,
    network: Network,
    *,
    address: str,
    status: str = "available",
    allocation_type: str | None = None,
) -> IPAddress:
    net = _parse_network(network.cidr)
    try:
        ip = ipaddress.IPv4Address(address.strip())
    except ValueError as exc:
        raise ProTrackValidationError(f"Invalid IP address: {address}") from exc
    if ip not in net:
        raise ProTrackValidationError(f"{address} is not within {network.cidr}.")
    existing = db.scalar(select(IPAddress).where(IPAddress.address == str(ip)))
    if existing is not None:
        raise ProTrackValidationError(f"IP {ip} already exists.")
    row = IPAddress(
        id=uuid4(),
        network_id=network.id,
        address=str(ip),
        status=status,
        allocation_type=allocation_type,
    )
    db.add(row)
    db.flush()
    return row


def list_ips(
    db: Session,
    network_id: UUID,
    *,
    status: str | None = None,
) -> list[IPAddress]:
    stmt = (
        select(IPAddress)
        .options(selectinload(IPAddress.assignment_history))
        .where(IPAddress.network_id == network_id)
        .order_by(IPAddress.address)
    )
    if status:
        stmt = stmt.where(IPAddress.status == status)
    return list(db.scalars(stmt).all())


def _current_ip_history(db: Session, ip_id: UUID) -> IPAssignmentHistory | None:
    return db.scalar(
        select(IPAssignmentHistory)
        .where(
            IPAssignmentHistory.ip_address_id == ip_id,
            IPAssignmentHistory.released_date.is_(None),
        )
        .order_by(IPAssignmentHistory.assigned_date.desc())
        .limit(1)
    )


def allocate_ip(
    db: Session,
    *,
    actor: User,
    ip_address_id: UUID | None = None,
    network_id: UUID | None = None,
    assigned_to_asset_id: UUID | None = None,
    assigned_to_user_id: UUID | None = None,
    hostname: str | None = None,
    notes: str | None = None,
    allocation_type: str | None = "static",
) -> IPAddress:
    if ip_address_id is None and network_id is None:
        raise ProTrackValidationError("Provide ip_address_id or network_id.")
    if ip_address_id is not None and network_id is not None:
        raise ProTrackValidationError("Provide only one of ip_address_id or network_id.")

    if ip_address_id is not None:
        ip = db.scalar(
            select(IPAddress).where(IPAddress.id == ip_address_id).with_for_update()
        )
        if ip is None:
            raise ProTrackValidationError("IP address not found.")
    else:
        ip = db.scalar(
            select(IPAddress)
            .where(
                IPAddress.network_id == network_id,
                IPAddress.status == "available",
            )
            .order_by(IPAddress.address)
            .with_for_update()
            .limit(1)
        )
        if ip is None:
            raise ProTrackValidationError(
                "No available IP in this network. Add IPs manually for large CIDRs, "
                "or choose a /24-or-smaller network with auto-generated pools."
            )

    if ip.status != "available":
        raise ProTrackValidationError(f"IP {ip.address} is not available (status={ip.status}).")
    if _current_ip_history(db, ip.id) is not None:
        raise ProTrackValidationError(f"IP {ip.address} already has an open assignment.")

    ip.status = "allocated"
    ip.allocation_type = (allocation_type or "static").strip() or "static"
    history = IPAssignmentHistory(
        id=uuid4(),
        ip_address_id=ip.id,
        assigned_to_asset_id=assigned_to_asset_id,
        assigned_to_user_id=assigned_to_user_id,
        assigned_by_user_id=actor.id,
        hostname=(hostname or "").strip() or None,
        assigned_date=date.today(),
        notes=(notes or "").strip() or None,
    )
    db.add(ip)
    db.add(history)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_ip_address,
        entity_id=ip.id,
        action=ActivityAction.it_ip_allocated,
        new_value={
            "address": ip.address,
            "assigned_to_user_id": str(assigned_to_user_id) if assigned_to_user_id else None,
            "assigned_to_asset_id": str(assigned_to_asset_id) if assigned_to_asset_id else None,
            "hostname": history.hostname,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(ip)
    return ip


def release_ip(
    db: Session,
    ip: IPAddress,
    *,
    actor: User,
    notes: str | None = None,
) -> IPAddress:
    history = _current_ip_history(db, ip.id)
    if history is None and ip.status != "allocated":
        raise ProTrackValidationError(f"IP {ip.address} is not currently allocated.")
    if history is not None:
        history.released_date = date.today()
        if notes:
            history.notes = (
                f"{history.notes}\n{notes}".strip() if history.notes else notes.strip()
            )
        db.add(history)
    ip.status = "available"
    db.add(ip)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_ip_address,
        entity_id=ip.id,
        action=ActivityAction.it_ip_released,
        new_value={"address": ip.address},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(ip)
    return ip


def get_ip(db: Session, ip_id: UUID) -> IPAddress | None:
    return db.scalar(
        select(IPAddress)
        .options(selectinload(IPAddress.assignment_history))
        .where(IPAddress.id == ip_id)
    )


def list_ips_for_user(db: Session, user_id: UUID) -> list[IPAddress]:
    open_ids = select(IPAssignmentHistory.ip_address_id).where(
        IPAssignmentHistory.assigned_to_user_id == user_id,
        IPAssignmentHistory.released_date.is_(None),
    )
    return list(
        db.scalars(
            select(IPAddress)
            .options(selectinload(IPAddress.assignment_history))
            .where(IPAddress.id.in_(open_ids))
            .order_by(IPAddress.address)
        ).all()
    )


def current_assignment_fields(ip: IPAddress) -> tuple[str | None, UUID | None, UUID | None]:
    for hist in ip.assignment_history or []:
        if hist.released_date is None:
            return hist.hostname, hist.assigned_to_user_id, hist.assigned_to_asset_id
    return None, None, None
