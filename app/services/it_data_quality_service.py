"""Unified IT / Resource Planning data-quality report.

Aggregates existing computer reconciliation + resource IT gaps, and adds
network / ownership / lifecycle detectors. Flags missing links for review —
never invents employee, owner, IP, or license relationships.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.it_operations import (
    CURRENT_INVENTORY_STATUSES,
    Asset,
    AssetAssignment,
    Computer,
    IPAddress,
    IPAssignmentHistory,
    WorkstationPackage,
    WorkstationPackageAssignment,
)
from app.models.models import User
from app.services import it_computer_reconciliation_service as recon
from app.services import resource_it_gap_service


_INACTIVE_ASSET_STATUSES = frozenset({"retired", "disposed", "returned_to_customer", "lost"})
_SAMPLE_LIMIT = 50


def _issue(
    *,
    code: str,
    severity: str,
    domain: str,
    title: str,
    count: int,
    samples: list[dict] | None = None,
    repair_code: str | None = None,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "domain": domain,
        "title": title,
        "count": count,
        "samples": (samples or [])[:_SAMPLE_LIMIT],
        "repair_code": repair_code,
    }


def _open_ip_histories(db: Session) -> list[IPAssignmentHistory]:
    return list(
        db.scalars(
            select(IPAssignmentHistory)
            .options(selectinload(IPAssignmentHistory.ip_address))
            .where(IPAssignmentHistory.released_date.is_(None))
        ).all()
    )


def _network_issues(db: Session) -> list[dict]:
    open_histories = _open_ip_histories(db)
    asset_to_ips: dict[UUID, list[IPAssignmentHistory]] = defaultdict(list)
    open_by_ip: dict[UUID, IPAssignmentHistory] = {}
    for hist in open_histories:
        open_by_ip[hist.ip_address_id] = hist
        if hist.assigned_to_asset_id is not None:
            asset_to_ips[hist.assigned_to_asset_id].append(hist)

    computers = list(
        db.scalars(
            select(Computer).options(selectinload(Computer.asset)).order_by(Computer.computer_name)
        ).all()
    )

    computers_without_ip: list[dict] = []
    for computer in computers:
        asset = computer.asset
        if asset is None or getattr(asset, "is_deleted", False):
            continue
        status = (asset.status or "").lower()
        if status not in CURRENT_INVENTORY_STATUSES:
            continue
        if asset.id not in asset_to_ips:
            computers_without_ip.append(
                {
                    "computer_id": str(computer.id),
                    "computer_name": computer.computer_name,
                    "asset_number": asset.asset_number,
                    "status": status,
                }
            )

    allocated_ips = list(
        db.scalars(select(IPAddress).where(IPAddress.status == "allocated")).all()
    )
    ip_without_computer: list[dict] = []
    for ip in allocated_ips:
        hist = open_by_ip.get(ip.id)
        asset_id = hist.assigned_to_asset_id if hist is not None else None
        linked_computer = None
        if asset_id is not None:
            linked_computer = db.scalar(select(Computer).where(Computer.asset_id == asset_id))
        if linked_computer is None:
            ip_without_computer.append(
                {
                    "ip_id": str(ip.id),
                    "address": ip.address,
                    "hostname": hist.hostname if hist else None,
                    "assigned_to_asset_id": str(asset_id) if asset_id else None,
                    "detail": (
                        "Allocated with no open history"
                        if hist is None
                        else (
                            "Open history has no asset"
                            if asset_id is None
                            else "Linked asset has no computer record"
                        )
                    ),
                }
            )

    conflicting_multi_ip: list[dict] = []
    intentional_multi_ip: list[dict] = []
    for asset_id, histories in asset_to_ips.items():
        if len(histories) < 2:
            continue
        asset = db.get(Asset, asset_id)
        interface_ids = {
            getattr(h, "interface_id", None)
            for h in histories
            if getattr(h, "interface_id", None) is not None
        }
        intentional = len(interface_ids) >= 2 and len(interface_ids) == len(histories)
        sample = {
            "asset_id": str(asset_id),
            "asset_number": asset.asset_number if asset else None,
            "ip_count": len(histories),
            "addresses": [
                h.ip_address.address if h.ip_address is not None else str(h.ip_address_id)
                for h in histories
            ],
            "interface_bound": len(interface_ids),
        }
        if intentional:
            intentional_multi_ip.append(sample)
        else:
            conflicting_multi_ip.append(sample)

    retired_with_ip: list[dict] = []
    for asset_id, histories in asset_to_ips.items():
        asset = db.get(Asset, asset_id)
        if asset is None or getattr(asset, "is_deleted", False):
            continue
        status = (asset.status or "").lower()
        if status not in _INACTIVE_ASSET_STATUSES:
            continue
        for hist in histories:
            retired_with_ip.append(
                {
                    "asset_id": str(asset.id),
                    "asset_number": asset.asset_number,
                    "status": status,
                    "ip_id": str(hist.ip_address_id),
                    "address": hist.ip_address.address if hist.ip_address else None,
                }
            )

    return [
        _issue(
            code="computers_without_ip",
            severity="warning",
            domain="network",
            title="Active computers with no IP assignment",
            count=len(computers_without_ip),
            samples=computers_without_ip,
        ),
        _issue(
            code="ip_without_computer",
            severity="warning",
            domain="network",
            title="Allocated IPs not linked to a computer",
            count=len(ip_without_computer),
            samples=ip_without_computer,
        ),
        _issue(
            code="asset_multiple_active_ips",
            severity="error",
            domain="network",
            title="Assets with multiple active IPs (no NIC binding)",
            count=len(conflicting_multi_ip),
            samples=conflicting_multi_ip,
        ),
        _issue(
            code="asset_multi_homed_ips",
            severity="info",
            domain="network",
            title="Multi-homed assets (IPs bound to distinct NICs)",
            count=len(intentional_multi_ip),
            samples=intentional_multi_ip,
        ),
        _issue(
            code="inactive_asset_with_active_ip",
            severity="error",
            domain="network",
            title="Retired/disposed/returned assets with active IP",
            count=len(retired_with_ip),
            samples=retired_with_ip,
        ),
    ]


def _lifecycle_issues(db: Session) -> list[dict]:
    open_assignments = list(
        db.scalars(
            select(AssetAssignment).where(AssetAssignment.returned_date.is_(None))
        ).all()
    )
    disposed_with_assignment: list[dict] = []
    for assignment in open_assignments:
        asset = db.get(Asset, assignment.asset_id)
        if asset is None or getattr(asset, "is_deleted", False):
            continue
        status = (asset.status or "").lower()
        if status not in _INACTIVE_ASSET_STATUSES:
            continue
        disposed_with_assignment.append(
            {
                "asset_id": str(asset.id),
                "asset_number": asset.asset_number,
                "status": status,
                "assigned_to_user_id": str(assignment.assigned_to_user_id),
                "assigned_date": assignment.assigned_date.isoformat(),
            }
        )

    missing_owner: list[dict] = []
    assets = db.scalars(
        select(Asset).where(
            Asset.is_deleted.is_(False),
            Asset.purchased_by == "customer",
            Asset.owner_customer_id.is_(None),
        )
    ).all()
    for asset in assets:
        status = (asset.status or "").lower()
        if status in _INACTIVE_ASSET_STATUSES:
            continue
        missing_owner.append(
            {
                "asset_id": str(asset.id),
                "asset_number": asset.asset_number,
                "status": status,
                "purchased_by": asset.purchased_by,
            }
        )

    inactive_assignee: list[dict] = []
    for assignment in open_assignments:
        user = db.get(User, assignment.assigned_to_user_id)
        if user is None:
            continue
        if user.is_active and not getattr(user, "is_deleted", False):
            continue
        asset = db.get(Asset, assignment.asset_id)
        if asset is None or getattr(asset, "is_deleted", False):
            continue
        inactive_assignee.append(
            {
                "asset_id": str(asset.id),
                "asset_number": asset.asset_number,
                "user_id": str(user.id),
                "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
                "status": asset.status,
            }
        )

    return [
        _issue(
            code="inactive_asset_with_open_assignment",
            severity="error",
            domain="assets",
            title="Retired/disposed/returned assets still assigned",
            count=len(disposed_with_assignment),
            samples=disposed_with_assignment,
        ),
        _issue(
            code="customer_owned_without_owner",
            severity="warning",
            domain="assets",
            title="Customer-owned assets missing owner customer",
            count=len(missing_owner),
            samples=missing_owner,
        ),
        _issue(
            code="assigned_to_inactive_employee",
            severity="error",
            domain="people",
            title="Assets assigned to inactive or deleted employees",
            count=len(inactive_assignee),
            samples=inactive_assignee,
        ),
    ]


def _computer_domain_issues(computer_report: dict) -> list[dict]:
    samples = computer_report.get("samples") or {}
    return [
        _issue(
            code="assigned_without_employee",
            severity="error",
            domain="computers",
            title="Status assigned with no employee",
            count=int(computer_report.get("assigned_without_employee") or 0),
            samples=list(samples.get("assigned_without_employee") or []),
            repair_code="repair_orphan_assigned",
        ),
        _issue(
            code="available_with_open_assignment",
            severity="warning",
            domain="computers",
            title="Status available but open assignment exists",
            count=int(computer_report.get("available_with_open_assignment") or 0),
            samples=list(samples.get("available_with_open_assignment") or []),
        ),
        _issue(
            code="assigned_without_team",
            severity="warning",
            domain="computers",
            title="Assigned computers with no resolvable team",
            count=int(computer_report.get("assigned_without_team") or 0),
            samples=list(samples.get("assigned_without_team") or []),
        ),
        _issue(
            code="computers_without_location",
            severity="info",
            domain="computers",
            title="Computers missing location",
            count=int(computer_report.get("computers_without_location") or 0),
            samples=[],
        ),
    ]


def _people_domain_issues(computer_report: dict, gaps: dict) -> list[dict]:
    samples = computer_report.get("samples") or {}
    users_without_computer = list(gaps.get("users_without_computer") or [])
    return [
        _issue(
            code="employees_without_computer",
            severity="error",
            domain="people",
            title="Active employees without a computer",
            count=int(computer_report.get("employees_without_computer") or 0),
            samples=list(samples.get("employees_without_computer") or [])
            or [
                {
                    "user_id": str(row.get("user_id")),
                    "user_name": row.get("full_name"),
                }
                for row in users_without_computer[:_SAMPLE_LIMIT]
            ],
        ),
        _issue(
            code="employees_without_shift_today",
            severity="warning",
            domain="people",
            title="Active employees with no shift today",
            count=int(computer_report.get("employees_without_shift_today") or 0),
            samples=list(samples.get("employees_without_shift_today") or []),
        ),
        _issue(
            code="users_missing_licenses",
            severity="error",
            domain="licenses",
            title="People missing required software licenses",
            count=len(gaps.get("users_missing_licenses") or []),
            samples=[
                {
                    "user_id": str(row.get("user_id")),
                    "user_name": row.get("full_name"),
                    "missing_count": len(row.get("missing") or []),
                }
                for row in (gaps.get("users_missing_licenses") or [])[:_SAMPLE_LIMIT]
            ],
        ),
    ]


def _license_domain_issues(gaps: dict) -> list[dict]:
    oversubscribed = list(gaps.get("oversubscribed_software") or [])
    no_pool = list(gaps.get("software_without_pool") or [])
    expired = list(gaps.get("expired_pools") or [])
    expiring = list(gaps.get("expiring_pools") or [])
    return [
        _issue(
            code="license_shortage",
            severity="error",
            domain="licenses",
            title="License seat shortages vs required headcount",
            count=len(oversubscribed),
            samples=[
                {
                    "software_id": str(row.get("software_id")),
                    "software_name": row.get("software_name"),
                    "required_headcount": row.get("required_headcount"),
                    "seat_count": row.get("seat_count"),
                    "seat_shortfall": row.get("seat_shortfall"),
                }
                for row in oversubscribed[:_SAMPLE_LIMIT]
            ],
        ),
        _issue(
            code="required_software_without_pool",
            severity="error",
            domain="licenses",
            title="Required software with no license pool",
            count=len(no_pool),
            samples=[
                {
                    "software_id": str(row.get("software_id")),
                    "software_name": row.get("software_name"),
                    "required_headcount": row.get("required_headcount"),
                }
                for row in no_pool[:_SAMPLE_LIMIT]
            ],
        ),
        _issue(
            code="expired_license_pools",
            severity="warning",
            domain="licenses",
            title="Expired license pools still in inventory",
            count=len(expired),
            samples=[
                {
                    "software_name": row.get("software_name"),
                    "pool_id": str(row.get("id")) if row.get("id") else None,
                }
                for row in expired[:_SAMPLE_LIMIT]
            ],
        ),
        _issue(
            code="expiring_license_pools",
            severity="info",
            domain="licenses",
            title="License pools expiring soon",
            count=len(expiring),
            samples=[
                {
                    "software_name": row.get("software_name"),
                    "pool_id": str(row.get("id")) if row.get("id") else None,
                }
                for row in expiring[:_SAMPLE_LIMIT]
            ],
        ),
    ]


def _identity_issues(db: Session) -> list[dict]:
    computers = list(
        db.scalars(
            select(Computer)
            .options(selectinload(Computer.asset), selectinload(Computer.interfaces))
            .order_by(Computer.computer_name)
        ).all()
    )
    mac_mismatch: list[dict] = []
    computers_without_mac: list[dict] = []
    for computer in computers:
        primary = next((row for row in (computer.interfaces or []) if row.is_primary), None)
        nic_mac = (primary.mac_address if primary is not None else None) or None
        denorm = computer.mac_address
        asset = computer.asset
        if not (nic_mac or denorm):
            if asset is not None and not getattr(asset, "is_deleted", False):
                status = (asset.status or "").lower()
                if status in CURRENT_INVENTORY_STATUSES:
                    computers_without_mac.append(
                        {
                            "computer_id": str(computer.id),
                            "computer_name": computer.computer_name,
                            "asset_number": asset.asset_number,
                            "status": status,
                        }
                    )
        if nic_mac and denorm and nic_mac.strip().upper() != denorm.strip().upper():
            mac_mismatch.append(
                {
                    "computer_id": str(computer.id),
                    "computer_name": computer.computer_name,
                    "asset_number": asset.asset_number if asset else None,
                    "nic_mac": nic_mac,
                    "computer_mac": denorm,
                }
            )
    return [
        _issue(
            code="computer_mac_nic_mismatch",
            severity="warning",
            domain="computers",
            title="Computer MAC differs from primary NIC (NIC is source of truth)",
            count=len(mac_mismatch),
            samples=mac_mismatch,
        ),
        _issue(
            code="computers_without_mac",
            severity="warning",
            domain="computers",
            title="Active computers with no MAC address",
            count=len(computers_without_mac),
            samples=computers_without_mac,
        ),
    ]


def _asset_record_issues(db: Session) -> list[dict]:
    """Duplicate identifiers and missing lifecycle fields on current inventory."""
    assets = list(
        db.scalars(
            select(Asset)
            .where(
                Asset.is_deleted.is_(False),
                Asset.status.in_(CURRENT_INVENTORY_STATUSES),
            )
            .order_by(Asset.asset_number)
        ).all()
    )
    by_serial: dict[str, list[Asset]] = defaultdict(list)
    by_tag: dict[str, list[Asset]] = defaultdict(list)
    missing_serial: list[dict] = []
    missing_warranty: list[dict] = []
    for asset in assets:
        serial = (asset.serial_number or "").strip().upper()
        tag = (asset.service_tag or "").strip().upper()
        if serial:
            by_serial[serial].append(asset)
        if tag:
            by_tag[tag].append(asset)
        if not serial and not tag:
            missing_serial.append(
                {"asset_id": str(asset.id), "asset_number": asset.asset_number, "status": asset.status}
            )
        if asset.warranty_expiry is None and (asset.purchased_by or "organization") == "organization":
            missing_warranty.append(
                {"asset_id": str(asset.id), "asset_number": asset.asset_number, "status": asset.status}
            )

    duplicates: list[dict] = []
    for label, groups in (("serial_number", by_serial), ("service_tag", by_tag)):
        for value, rows in groups.items():
            if len(rows) < 2:
                continue
            for asset in rows:
                duplicates.append(
                    {
                        "asset_id": str(asset.id),
                        "asset_number": asset.asset_number,
                        "field": label,
                        "value": value,
                        "duplicate_count": len(rows),
                    }
                )

    return [
        _issue(
            code="duplicate_asset_identifiers",
            severity="error",
            domain="assets",
            title="Assets sharing a serial number or service tag",
            count=len(duplicates),
            samples=duplicates,
        ),
        _issue(
            code="assets_without_serial",
            severity="warning",
            domain="assets",
            title="Assets with no serial number or service tag",
            count=len(missing_serial),
            samples=missing_serial,
        ),
        _issue(
            code="assets_without_warranty",
            severity="info",
            domain="assets",
            title="Organization-owned assets with no warranty date",
            count=len(missing_warranty),
            samples=missing_warranty,
        ),
    ]


def _seat_issues(db: Session) -> list[dict]:
    """Virtual seat shift assignments still held by inactive / exited employees."""
    rows = db.execute(
        select(WorkstationPackageAssignment, WorkstationPackage.code, User)
        .join(WorkstationPackage, WorkstationPackage.id == WorkstationPackageAssignment.package_id)
        .join(User, User.id == WorkstationPackageAssignment.user_id)
        .where(
            WorkstationPackageAssignment.status == "ACTIVE",
            or_(
                User.is_active.is_(False),
                User.is_deleted.is_(True),
                User.is_archived.is_(True),
            ),
        )
    ).all()
    samples = [
        {
            "user_id": str(user.id),
            "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            "detail": f"Seat {code}",
        }
        for _assignment, code, user in rows
    ]
    return [
        _issue(
            code="seat_assigned_to_inactive_employee",
            severity="error",
            domain="people",
            title="Virtual seat shifts held by inactive employees",
            count=len(samples),
            samples=samples,
        )
    ]


def _inventory_issues(db: Session) -> list[dict]:
    """Consumable stock records and derived virtual seats."""
    from app.models.it_operations import AssetType, InventoryItem
    from app.services import it_inventory_rules as rules
    from app.services import it_stock_service as stock
    from app.services import virtual_seat_service as seats

    rows = stock.item_rows(db)
    no_min = [
        {"item_id": r["id"], "item_name": r["name"], "available": r["available"]}
        for r in rows
        if r["min_stock"] is None
    ]
    low_unsourced = [
        {
            "item_id": r["id"],
            "item_name": r["name"],
            "available": r["available"],
            "detail": ", ".join(
                label
                for label, missing in (
                    ("no supplier", not r["supplier_id"]),
                    ("no reorder qty", not r["reorder_qty"] and r["target_stock"] is None),
                )
                if missing
            ),
        }
        for r in rows
        if r["stock_status"] in {stock.STATUS_LOW, stock.STATUS_OUT}
        and (not r["supplier_id"] or (not r["reorder_qty"] and r["target_stock"] is None))
    ]
    no_history = [
        {"item_id": r["id"], "item_name": r["name"], "on_hand": r["on_hand"]}
        for r in rows
        if not r["has_movements"]
    ]
    invalid_qty = [
        {
            "item_id": str(item.id),
            "item_name": item.name,
            "on_hand": item.on_hand_qty,
            "detail": "Negative on-hand quantity"
            if (item.on_hand_qty or 0) < 0
            else "Minimum above target stock",
        }
        for item in db.scalars(select(InventoryItem).where(InventoryItem.is_deleted.is_(False))).all()
        if (item.on_hand_qty or 0) < 0
        or (
            item.min_stock is not None
            and item.target_stock is not None
            and item.min_stock > item.target_stock
        )
    ]

    derived = seats.derive_seats(db)
    peripherals_without_primary = [
        {
            "user_id": s["user_id"],
            "user_name": s["user_name"],
            "detail": f"{len(s['components'])} peripheral(s), no computer assigned",
        }
        for s in derived
        if not s["primary"] and s["components"]
    ]
    seat_conflicts = [
        {
            "user_id": s["user_id"],
            "user_name": s["user_name"],
            "asset_number": s["primary"]["asset_number"],
            "detail": "Overlaps with "
            + ", ".join(
                f"{c.get('user_name') or 'unknown'} ({c.get('shift_display') or 'no shift'})"
                for c in s["conflicts"]
            ),
        }
        for s in derived
        if s["primary"] and s["conflicts"]
    ]

    untyped_computers = []
    for asset, asset_type in db.execute(
        select(Asset, AssetType)
        .join(AssetType, AssetType.id == Asset.asset_type_id)
        .where(Asset.is_deleted.is_(False), Asset.status.in_(CURRENT_INVENTORY_STATUSES))
        .order_by(Asset.asset_number)
    ).all():
        if rules.role_for_asset_type(asset_type) == rules.ROLE_COMPUTER and not asset.computer_type:
            untyped_computers.append(
                {"asset_id": str(asset.id), "asset_number": asset.asset_number, "status": asset.status}
            )

    return [
        _issue(
            code="consumables_without_min_stock",
            severity="warning",
            domain="inventory",
            title="Consumable stock items with no minimum stock",
            count=len(no_min),
            samples=no_min,
        ),
        _issue(
            code="low_stock_without_reorder_info",
            severity="warning",
            domain="inventory",
            title="Low / out-of-stock items missing supplier or reorder quantity",
            count=len(low_unsourced),
            samples=low_unsourced,
        ),
        _issue(
            code="invalid_stock_quantities",
            severity="error",
            domain="inventory",
            title="Stock items with invalid quantities or thresholds",
            count=len(invalid_qty),
            samples=invalid_qty,
        ),
        _issue(
            code="stock_items_without_movements",
            severity="info",
            domain="inventory",
            title="Stock items with no movement history",
            count=len(no_history),
            samples=no_history,
        ),
        _issue(
            code="peripherals_without_primary_device",
            severity="warning",
            domain="seats",
            title="Employees with peripherals but no primary computer",
            count=len(peripherals_without_primary),
            samples=peripherals_without_primary,
        ),
        _issue(
            code="virtual_seat_conflicts",
            severity="error",
            domain="seats",
            title="Virtual seats with overlapping shift assignments",
            count=len(seat_conflicts),
            samples=seat_conflicts,
        ),
        _issue(
            code="computers_without_computer_type",
            severity="info",
            domain="computers",
            title="Computers with no computer type (seat requirements cannot be checked)",
            count=len(untyped_computers),
            samples=untyped_computers,
        ),
    ]


def _href_for_sample(sample: dict) -> str | None:
    if sample.get("item_id"):
        return f"/it/inventory?item={sample['item_id']}"
    asset_number = sample.get("asset_number")
    if isinstance(asset_number, str) and asset_number.strip():
        return f"/it/assets?search={asset_number}"
    if sample.get("user_id"):
        return f"/it/accounts?user={sample['user_id']}&status=all"
    if sample.get("pool_id") or sample.get("software_id"):
        return "/it/software?tab=licenses"
    if sample.get("address"):
        return "/it/networks"
    return None


def _annotate_sample_hrefs(issues: list[dict]) -> None:
    for issue in issues:
        for sample in issue.get("samples") or []:
            if sample.get("href"):
                continue
            href = _href_for_sample(sample)
            if href:
                sample["href"] = href


def build_data_quality_report(db: Session) -> dict:
    """Catalog-driven data-quality report for IT + Resource Planning."""
    computer_report = recon.computer_data_quality_report(db)
    gaps = resource_it_gap_service.get_resource_gaps(db)

    issues = (
        _computer_domain_issues(computer_report)
        + _people_domain_issues(computer_report, gaps)
        + _network_issues(db)
        + _license_domain_issues(gaps)
        + _lifecycle_issues(db)
        + _identity_issues(db)
        + _asset_record_issues(db)
        + _seat_issues(db)
        + _inventory_issues(db)
    )
    _annotate_sample_hrefs(issues)

    open_issues = [row for row in issues if int(row["count"]) > 0]
    by_severity = {"error": 0, "warning": 0, "info": 0}
    for row in open_issues:
        severity = row["severity"]
        if severity in by_severity:
            by_severity[severity] += 1

    repairs = [
        {
            "code": "repair_orphan_assigned",
            "label": "Reset orphan assigned computer statuses to available",
            "available": int(computer_report.get("assigned_without_employee") or 0) > 0,
            "endpoint": "POST /it/computers/reconcile-orphan-assigned",
            "permission": "manage_it_assets",
        }
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "issue_types": len(open_issues),
            "error": by_severity["error"],
            "warning": by_severity["warning"],
            "info": by_severity["info"],
            "computers_total": int(computer_report.get("computers_total") or 0),
        },
        "issues": issues,
        "open_issues": open_issues,
        "repairs": repairs,
        "computer_report": computer_report,
    }
