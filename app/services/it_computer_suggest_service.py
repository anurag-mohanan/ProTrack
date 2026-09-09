"""Deterministic computer-name and IP suggestions from live inventory."""

from __future__ import annotations

import ipaddress
import re
from collections import Counter, defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.it_operations import (
    Computer,
    ComputerNameHistory,
    ComputerNetworkInterface,
    IPAddress,
    IPAssignmentHistory,
    Network,
)

_NAME_RE = re.compile(r"^(.*?)(\d+)$")
_MAC_RE = re.compile(r"[^0-9A-Fa-f]")


def parse_trailing_number(value: str) -> tuple[str, int, int] | None:
    text = (value or "").strip()
    match = _NAME_RE.match(text)
    if not match:
        return None
    prefix, digits = match.group(1), match.group(2)
    return prefix, int(digits), len(digits)


def normalize_mac(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    hex_only = _MAC_RE.sub("", raw).upper()
    if len(hex_only) != 12:
        return raw.upper()
    return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2))


def computer_name_is_taken(
    db: Session, name: str, *, exclude_computer_id: UUID | None = None
) -> bool:
    cleaned = (name or "").strip()
    if not cleaned:
        return False
    stmt = select(Computer.id).where(func.lower(Computer.computer_name) == cleaned.lower())
    if exclude_computer_id is not None:
        stmt = stmt.where(Computer.id != exclude_computer_id)
    if db.scalar(stmt.limit(1)) is not None:
        return True
    history = select(ComputerNameHistory.id).where(
        func.lower(ComputerNameHistory.computer_name) == cleaned.lower()
    )
    if exclude_computer_id is not None:
        history = history.where(
            ~(
                (ComputerNameHistory.computer_id == exclude_computer_id)
                & ComputerNameHistory.effective_to.is_(None)
            )
        )
    return db.scalar(history.limit(1)) is not None


def mac_is_taken(
    db: Session, mac: str, *, exclude_computer_id: UUID | None = None
) -> Computer | None:
    normalized = normalize_mac(mac)
    if not normalized:
        return None
    compact = _MAC_RE.sub("", normalized).upper()
    computers = list(
        db.scalars(select(Computer).options(selectinload(Computer.interfaces))).all()
    )
    for computer in computers:
        if exclude_computer_id is not None and computer.id == exclude_computer_id:
            continue
        candidates = [computer.mac_address, *[iface.mac_address for iface in computer.interfaces]]
        for candidate in candidates:
            if not candidate:
                continue
            if _MAC_RE.sub("", candidate).upper() == compact:
                return computer
    return None


def suggest_computer_name(db: Session, *, type_code: str | None = None) -> dict:
    names = [
        (row.computer_name or "").strip()
        for row in db.scalars(select(Computer).order_by(Computer.computer_name)).all()
        if (row.computer_name or "").strip()
    ]
    grouped: dict[tuple[str, int], list[int]] = defaultdict(list)
    for name in names:
        parsed = parse_trailing_number(name)
        if parsed is None:
            continue
        prefix, number, width = parsed
        grouped[(prefix, width)].append(number)

    if grouped:
        (prefix, width), numbers = max(grouped.items(), key=lambda item: len(item[1]))
        used = set(numbers)
        seq = max(used) + 1
        candidate = f"{prefix}{seq:0{width}d}"
        while computer_name_is_taken(db, candidate):
            seq += 1
            candidate = f"{prefix}{seq:0{width}d}"
        samples = sorted(
            [f"{prefix}{n:0{width}d}" for n in numbers],
            key=lambda value: parse_trailing_number(value)[1] if parse_trailing_number(value) else 0,
        )[-5:]
        return {
            "computer_name": candidate,
            "prefix": prefix,
            "sequence": seq,
            "width": width,
            "source": "existing_names",
            "highest_existing_sequence": max(used),
            "sample_names": samples,
            "message": (
                f"Suggested from existing computer naming pattern "
                f"({samples[0]} … {samples[-1]} → {candidate})."
                if samples
                else f"Suggested unique computer name {candidate}."
            ),
        }

    settings = None
    from app.services import it_asset_service as asset_svc

    settings = asset_svc.get_or_create_settings(db)
    code = (type_code or "PC").strip().upper()[:6]
    pattern = settings.computer_naming_pattern or "PRO-{type}{seq:03d}"
    seq = int(settings.next_computer_seq or 1)
    try:
        candidate = pattern.format(type=code, seq=seq, org="PRO", prefix="PRO").strip()
    except (KeyError, ValueError):
        candidate = f"PRO{code}{seq:03d}"
    while computer_name_is_taken(db, candidate):
        seq += 1
        try:
            candidate = pattern.format(type=code, seq=seq, org="PRO", prefix="PRO").strip()
        except (KeyError, ValueError):
            candidate = f"PRO{code}{seq:03d}"
    return {
        "computer_name": candidate,
        "prefix": code,
        "sequence": seq,
        "width": 3,
        "source": "settings_pattern",
        "highest_existing_sequence": seq - 1,
        "sample_names": [],
        "message": (
            f"No existing computer names found. Suggested from the configured "
            f"naming pattern ({pattern})."
        ),
    }


def _last_octet(address: str) -> int | None:
    try:
        packed = ipaddress.IPv4Address(address.strip())
    except ValueError:
        return None
    return int(packed) & 0xFF


def _open_ip_history_map(db: Session) -> dict[UUID, IPAssignmentHistory]:
    rows = list(
        db.scalars(
            select(IPAssignmentHistory).where(IPAssignmentHistory.released_date.is_(None))
        ).all()
    )
    return {row.ip_address_id: row for row in rows}


def current_ip_for_asset(db: Session, asset_id: UUID) -> dict | None:
    history = db.scalar(
        select(IPAssignmentHistory)
        .where(
            IPAssignmentHistory.assigned_to_asset_id == asset_id,
            IPAssignmentHistory.released_date.is_(None),
        )
        .order_by(IPAssignmentHistory.assigned_date.desc(), IPAssignmentHistory.created_at.desc())
        .limit(1)
    )
    if history is None:
        return None
    ip = db.get(IPAddress, history.ip_address_id)
    if ip is None:
        return None
    network = db.get(Network, ip.network_id) if ip.network_id else None
    return {
        "ip_address_id": ip.id,
        "address": ip.address,
        "status": ip.status,
        "allocation_type": ip.allocation_type,
        "network_id": ip.network_id,
        "network_name": network.name if network else None,
        "network_cidr": network.cidr if network else None,
        "hostname": history.hostname,
    }


def current_ips_for_assets(db: Session, asset_ids: list[UUID]) -> dict[UUID, dict]:
    if not asset_ids:
        return {}
    rows = list(
        db.scalars(
            select(IPAssignmentHistory).where(
                IPAssignmentHistory.assigned_to_asset_id.in_(asset_ids),
                IPAssignmentHistory.released_date.is_(None),
            )
        ).all()
    )
    by_asset: dict[UUID, IPAssignmentHistory] = {}
    for row in rows:
        if row.assigned_to_asset_id is None:
            continue
        current = by_asset.get(row.assigned_to_asset_id)
        if current is None or row.assigned_date > current.assigned_date:
            by_asset[row.assigned_to_asset_id] = row
    ip_ids = [row.ip_address_id for row in by_asset.values()]
    ips = {
        ip.id: ip
        for ip in db.scalars(select(IPAddress).where(IPAddress.id.in_(ip_ids))).all()
    } if ip_ids else {}
    network_ids = {ip.network_id for ip in ips.values()}
    networks = {
        net.id: net
        for net in db.scalars(select(Network).where(Network.id.in_(network_ids))).all()
    } if network_ids else {}
    result: dict[UUID, dict] = {}
    for asset_id, history in by_asset.items():
        ip = ips.get(history.ip_address_id)
        if ip is None:
            continue
        network = networks.get(ip.network_id)
        result[asset_id] = {
            "ip_address_id": ip.id,
            "address": ip.address,
            "status": ip.status,
            "allocation_type": ip.allocation_type,
            "network_id": ip.network_id,
            "network_name": network.name if network else None,
            "network_cidr": network.cidr if network else None,
            "hostname": history.hostname,
        }
    return result


def suggest_computer_ip(
    db: Session,
    *,
    computer_name: str | None = None,
    network_id: UUID | None = None,
) -> dict:
    networks = list(
        db.scalars(
            select(Network).where(Network.is_active.is_(True)).order_by(Network.name)
        ).all()
    )
    if network_id is not None:
        networks = [net for net in networks if net.id == network_id]
    if not networks:
        return {
            "address": None,
            "ip_address_id": None,
            "network_id": None,
            "network_name": None,
            "network_cidr": None,
            "allocation_type": "static",
            "available": False,
            "message": "No active IP pool exists. Add a network CIDR under Administration → IP Pools.",
        }

    open_hist = _open_ip_history_map(db)
    computers = {
        (row.computer_name or "").strip().lower(): row
        for row in db.scalars(select(Computer)).all()
        if (row.computer_name or "").strip()
    }
    ips = list(db.scalars(select(IPAddress)).all())
    ips_by_network: dict[UUID, list[IPAddress]] = defaultdict(list)
    for ip in ips:
        ips_by_network[ip.network_id].append(ip)

    scored_networks: list[tuple[int, Network]] = []
    for net in networks:
        allocated = sum(1 for ip in ips_by_network.get(net.id, []) if ip.status == "allocated")
        scored_networks.append((allocated, net))
    scored_networks.sort(key=lambda item: item[0], reverse=True)
    preferred = scored_networks[0][1]

    name_num = None
    parsed_name = parse_trailing_number(computer_name or "")
    if parsed_name:
        name_num = parsed_name[1]

    correlated: list[tuple[int, str]] = []
    if name_num is not None:
        for ip in ips:
            hist = open_hist.get(ip.id)
            hostname = (hist.hostname if hist else None) or ""
            computer = computers.get(hostname.lower()) if hostname else None
            host_parsed = parse_trailing_number(
                computer.computer_name if computer else hostname
            )
            octet = _last_octet(ip.address)
            if host_parsed is None or octet is None:
                continue
            correlated.append((octet - host_parsed[1], ip.address))

    candidate_address = None
    reason = None
    if correlated and name_num is not None:
        offset, _count = Counter(item[0] for item in correlated).most_common(1)[0]
        if _count / len(correlated) >= 0.6:
            wanted_octet = name_num + offset
            if 1 <= wanted_octet <= 254:
                prefix = ".".join(preferred.cidr.split("/")[0].split(".")[:3])
                candidate_address = f"{prefix}.{wanted_octet}"
                reason = (
                    f"Existing computer/IP pairs most often use last-octet = name sequence "
                    f"{offset:+d} ({_count}/{len(correlated)}). "
                    f"Suggested {candidate_address} for this name."
                )

    pool = ips_by_network.get(preferred.id, [])
    available = [
        ip
        for ip in pool
        if ip.status == "available" and ip.id not in open_hist
    ]
    available.sort(key=lambda ip: tuple(int(part) for part in ip.address.split(".")))

    chosen: IPAddress | None = None
    if candidate_address:
        chosen = next((ip for ip in available if ip.address == candidate_address), None)
        if chosen is None:
            reason = (
                (reason or "")
                + f" {candidate_address} is not available in the pool; using the next free address."
            ).strip()
            candidate_address = None

    if chosen is None and available:
        chosen = available[0]
        if reason is None:
            reason = (
                f"Suggested next available address in {preferred.name} ({preferred.cidr})."
            )

    if chosen is None:
        return {
            "address": None,
            "ip_address_id": None,
            "network_id": preferred.id,
            "network_name": preferred.name,
            "network_cidr": preferred.cidr,
            "allocation_type": "static",
            "available": False,
            "message": (
                f"No available IP in {preferred.name} ({preferred.cidr}). "
                "Release an address or expand the pool."
            ),
        }

    return {
        "address": chosen.address,
        "ip_address_id": chosen.id,
        "network_id": preferred.id,
        "network_name": preferred.name,
        "network_cidr": preferred.cidr,
        "allocation_type": "static",
        "available": True,
        "message": reason
        or f"Suggested next available address in {preferred.name} ({preferred.cidr}).",
    }
