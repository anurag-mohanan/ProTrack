"""Helpers for IT Hardware Workbook import (combined asset+computer+IP+parent rows).

Used by ``it_data_import_service`` for import_type ``hardware_workbook``.
Reusable aliases live in FIELD_ALIASES — this module owns row defaults and
combined commit logic only.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.it_operations import Asset, Computer, IPAddress, IPAssignmentHistory
from app.models.models import Customer, User
# it_asset_service not imported here to avoid circular imports at module load


PLACEHOLDER_ASSIGNEES = frozenset(
    {
        "open",
        "all",
        "n/a",
        "na",
        "none",
        "unassigned",
        "available",
        "servprosohm",
        "conference room",
        "planning board",
        "eng planning board",
        "prosohm eng team",
    }
)

_3D_MOUSE_RE = re.compile(r"3\s*d\s*mouse|spacemouse|3dconnexion", re.I)


def is_placeholder_assignee(label: str) -> bool:
    key = " ".join((label or "").strip().lower().split())
    return key in PLACEHOLDER_ASSIGNEES


def is_3d_mouse_type(type_label: str) -> bool:
    return bool(_3D_MOUSE_RE.search(type_label or ""))


def apply_hardware_row_defaults(fields: dict[str, str]) -> dict[str, str]:
    """Mutate/copy defaults: 3D Mouse make/model; Open → available."""
    out = dict(fields)
    type_label = out.get("asset_type") or ""
    if is_3d_mouse_type(type_label):
        if not (out.get("make") or "").strip():
            out["make"] = "3Dconnexion"
        if not (out.get("model_number") or out.get("model") or "").strip():
            out["model_number"] = "SpaceMouse Compact"

    assignee = (out.get("assigned_to") or "").strip()
    if assignee and is_placeholder_assignee(assignee):
        out["_assignee_placeholder"] = "1"
        out["assigned_to"] = ""
        if not (out.get("current_status") or "").strip():
            out["current_status"] = "Available"

    # Serial / Service Tag combined column: prefer service_tag when looks like Dell tag
    serialish = (out.get("serial_number") or "").strip()
    service = (out.get("service_tag") or "").strip()
    if serialish and not service:
        out["service_tag"] = serialish
    return out


def normalize_mac(value: str) -> str | None:
    raw = re.sub(r"[^0-9A-Fa-f]", "", value or "")
    if len(raw) != 12:
        return None
    parts = [raw[i : i + 2].upper() for i in range(0, 12, 2)]
    return "-".join(parts)


def validate_ipv4(value: str) -> bool:
    try:
        ipaddress.IPv4Address((value or "").strip())
        return True
    except ValueError:
        return False


def needs_computer_record(fields: dict[str, str], type_label: str) -> bool:
    code = re.sub(r"[^A-Za-z0-9]+", " ", (type_label or "").lower())
    if any(k in code for k in ("workstation", "desktop", "laptop", "server", "computer")):
        return True
    return bool(
        (fields.get("computer_name") or "").strip()
        or (fields.get("mac_address") or "").strip()
        or (fields.get("ip_address") or "").strip()
    )


def _norm_id(value: str) -> str:
    """Align with it_data_import_service: casefold spaces only — keep hyphens."""
    return re.sub(r"\s+", "", (value or "").upper())


def analyze_hardware_issues(
    fields: dict[str, str],
    *,
    existing: dict[str, set[str]],
    existing_ips: set[str],
    existing_macs: set[str],
    users: dict[str, User],
    customers: dict[str, Customer],
    resolve_ownership,
    match_user,
    match_customer,
    preview_next_asset_number,
    resolve_or_create_asset_type,
    db: Session,
) -> tuple[str, list[dict[str, str]], dict[str, Any]]:
    """Return action, issues, preview extras for one hardware workbook row."""
    issues: list[dict[str, str]] = []
    action = "import"
    extras: dict[str, Any] = {}

    fields = apply_hardware_row_defaults(fields)
    anum = (fields.get("asset_number") or "").strip()
    generated = False
    if not anum:
        at = resolve_or_create_asset_type(db, fields.get("asset_type") or "OTHER")
        suggested = preview_next_asset_number(db, at)["asset_number"]
        fields["asset_number"] = suggested
        fields["_generated_asset_number"] = "1"
        generated = True
        extras["generated_asset_number"] = suggested
        issues.append(
            {
                "code": "ASSET_NUMBER_GENERATED",
                "severity": "warning",
                "detail": f"Blank Asset Number → suggested {suggested} (confirm on commit).",
            }
        )
        anum = suggested

    # Preserve exact number — never normalize hyphenation for storage
    norm = _norm_id(anum)
    st = (fields.get("service_tag") or "").strip()
    sn = (fields.get("serial_number") or "").strip()
    strong = None
    if st and _norm_id(st) in existing["service_tag"]:
        strong = "service_tag"
    elif sn and _norm_id(sn) in existing["serial"]:
        strong = "serial_number"
    elif norm in existing["asset_number"] or norm in existing["legacy"]:
        strong = "asset_number"
    if strong:
        action = "skip_duplicate"
        issues.append(
            {
                "code": "DUPLICATE",
                "severity": "warning",
                "detail": f"Asset Number '{anum}' already exists (matched on {strong}).",
            }
        )

    purchased_by, _oid, own_issues = resolve_ownership(
        fields.get("ownership_type") or "",
        fields.get("owner_customer") or "",
        customers,
    )
    fields["_purchased_by"] = purchased_by
    if not (fields.get("ownership_type") or "").strip() and not (
        fields.get("owner_customer") or ""
    ).strip():
        issues.append(
            {
                "code": "OWNERSHIP_REQUIRED",
                "severity": "review",
                "detail": "Hardware ownership blank — import with Ownership Required (unknown).",
            }
        )
        fields["_purchased_by"] = "unknown"
    else:
        issues.extend(own_issues)

    assignee = (fields.get("assigned_to") or "").strip()
    if fields.get("_assignee_placeholder") == "1":
        pass  # intentionally unassigned
    elif assignee and match_user(users, assignee) is None:
        issues.append(
            {
                "code": "USER_UNKNOWN",
                "severity": "warning",
                "detail": f"Assigned User '{assignee}' could not be matched.",
            }
        )

    ip = (fields.get("ip_address") or "").strip()
    if ip:
        if not validate_ipv4(ip):
            issues.append(
                {
                    "code": "INVALID_IP",
                    "severity": "error",
                    "detail": f"Invalid IPv4 address '{ip}'.",
                }
            )
            action = "error"
        elif ip in existing_ips:
            issues.append(
                {
                    "code": "IP_CONFLICT",
                    "severity": "warning",
                    "detail": f"IP '{ip}' already exists — review before overwrite.",
                }
            )

    mac_raw = (fields.get("mac_address") or "").strip()
    if mac_raw:
        mac = normalize_mac(mac_raw)
        if mac is None:
            issues.append(
                {
                    "code": "INVALID_MAC",
                    "severity": "warning",
                    "detail": f"MAC '{mac_raw}' is not a valid 12-hex address.",
                }
            )
        else:
            fields["mac_address"] = mac
            if mac in existing_macs:
                issues.append(
                    {
                        "code": "MAC_CONFLICT",
                        "severity": "warning",
                        "detail": f"MAC '{mac}' already exists on another computer.",
                    }
                )

    parent = (fields.get("parent_asset_number") or "").strip()
    if parent:
        extras["parent_asset_number"] = parent
        # Presence checked at commit (order-independent)

    preview = {
        "asset_number": anum,
        "asset_type": fields.get("asset_type") or "",
        "category": fields.get("category") or "",
        "make": fields.get("make") or "",
        "model": fields.get("model_number") or fields.get("model") or "",
        "assigned_to": assignee or ("Open" if fields.get("_assignee_placeholder") else ""),
        "ownership_type": fields.get("ownership_type") or "",
        "owner_customer": fields.get("owner_customer") or "",
        "parent_asset_number": parent,
        "computer_name": fields.get("computer_name") or "",
        "ip_address": ip,
        "generated_asset_number": generated,
        "import_action": action,
    }
    extras["fields"] = fields
    extras["preview"] = preview
    return action, issues, extras


def link_parent_assets(db: Session, created: list[tuple[Asset, str | None]]) -> list[str]:
    """Second-pass parent links. Returns warning strings for unresolved parents."""
    warnings: list[str] = []
    for asset, parent_number in created:
        if not parent_number:
            continue
        parent = db.scalar(
            select(Asset).where(
                Asset.is_deleted.is_(False),
                Asset.asset_number == parent_number,
            )
        )
        if parent is None:
            # try casefold match
            for a in db.scalars(select(Asset).where(Asset.is_deleted.is_(False))).all():
                if (a.asset_number or "").strip().casefold() == parent_number.casefold():
                    parent = a
                    break
        if parent is None:
            warnings.append(
                f"Parent Asset '{parent_number}' not found for {asset.asset_number}."
            )
            continue
        if parent.id == asset.id:
            continue
        asset.parent_asset_id = parent.id
        db.add(asset)
    return warnings


def ensure_computer_and_ip(
    db: Session,
    *,
    asset: Asset,
    fields: dict[str, str],
    batch_id: UUID,
    source_system: str,
    actor: User,
    ensure_slash24_network,
) -> None:
    from datetime import date

    type_label = fields.get("asset_type") or ""
    if needs_computer_record(fields, type_label):
        existing_c = db.scalar(select(Computer).where(Computer.asset_id == asset.id))
        cname = (
            (fields.get("computer_name") or "").strip()
            or asset.asset_number
            or "UNKNOWN"
        )[:40]
        if existing_c is None:
            clash = db.scalar(select(Computer).where(Computer.computer_name == cname))
            if clash is not None:
                cname = f"{cname[:36]}-{str(uuid4())[:3]}"
            db.add(
                Computer(
                    id=uuid4(),
                    asset_id=asset.id,
                    computer_name=cname,
                    mac_address=(fields.get("mac_address") or "").strip() or None,
                    import_batch_id=batch_id,
                    source_system=source_system,
                )
            )

    ip = (fields.get("ip_address") or "").strip()
    if not ip or not validate_ipv4(ip):
        return
    existing_ip = db.scalar(select(IPAddress).where(IPAddress.address == ip))
    if existing_ip is not None:
        return
    network = ensure_slash24_network(db, ip)
    ip_row = IPAddress(
        id=uuid4(),
        network_id=network.id,
        address=ip,
        status="allocated",
        allocation_type="static",
        import_batch_id=batch_id,
    )
    db.add(ip_row)
    db.flush()
    db.add(
        IPAssignmentHistory(
            id=uuid4(),
            ip_address_id=ip_row.id,
            assigned_to_asset_id=asset.id,
            assigned_by_user_id=actor.id,
            hostname=(fields.get("computer_name") or "").strip() or None,
            assigned_date=date.today(),
            notes="IT Hardware Workbook import",
        )
    )
