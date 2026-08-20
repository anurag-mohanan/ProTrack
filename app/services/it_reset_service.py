"""Admin-only full IT operational data reset (preserves config + master org data)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_IT_OPERATIONS
from app.core.config import UPLOAD_DIR
from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetCustomerReturn,
    AssetType,
    Computer,
    InventoryItem,
    IPAddress,
    IPAssignmentHistory,
    ITImportBatch,
    ITMigrationException,
    ITSettings,
    ITSupplier,
    ITUserAccount,
    Network,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Customer, Project, Role, Team, TimesheetEntry, User
from app.services.activity_service import log_activity

MODULE = MODULE_IT_OPERATIONS
CONFIRM_PHRASE = "RESET IT DATA"

# Operational tables wiped (children first). Config tables preserved.
_WIPE_ORDER: list[tuple[str, Any]] = [
    ("software_assignments", SoftwareAssignment),
    ("software_license_pools", SoftwareLicensePool),
    ("software_catalog", SoftwareCatalog),
    ("ip_assignment_history", IPAssignmentHistory),
    ("ip_addresses", IPAddress),
    ("networks", Network),
    ("asset_assignments", AssetAssignment),
    ("asset_customer_returns", AssetCustomerReturn),
    ("computers", Computer),
    ("assets", Asset),
    ("inventory_items", InventoryItem),
    ("it_user_accounts", ITUserAccount),
    ("it_suppliers", ITSupplier),
    ("it_migration_exceptions", ITMigrationException),
    ("it_import_batches", ITImportBatch),
]


def _count(db: Session, model: Any, where=None) -> int:
    stmt = select(func.count()).select_from(model)
    if where is not None:
        stmt = stmt.where(where)
    return int(db.scalar(stmt) or 0)


def preview_reset(db: Session) -> dict[str, Any]:
    """Dry-run counts for IT operational wipe vs preserved master data."""
    to_delete = {
        "assets": _count(db, Asset),
        "computers": _count(db, Computer),
        "asset_assignments": _count(db, AssetAssignment),
        "asset_customer_returns": _count(db, AssetCustomerReturn),
        "inventory_items": _count(db, InventoryItem),
        "ip_addresses": _count(db, IPAddress),
        "ip_assignment_history": _count(db, IPAssignmentHistory),
        "networks": _count(db, Network),
        "software_catalog": _count(db, SoftwareCatalog),
        "software_license_pools": _count(db, SoftwareLicensePool),
        "software_assignments": _count(db, SoftwareAssignment),
        "it_user_accounts": _count(db, ITUserAccount),
        "it_suppliers": _count(db, ITSupplier),
        "it_import_batches": _count(db, ITImportBatch),
        "it_migration_exceptions": _count(db, ITMigrationException),
    }
    preserved = {
        "employees_users": _count(db, User),
        "customers": _count(db, Customer),
        "projects": _count(db, Project),
        "teams": _count(db, Team),
        "timesheet_entries": _count(db, TimesheetEntry),
        "roles": _count(db, Role),
        "asset_types": _count(db, AssetType),
        "it_settings": _count(db, ITSettings),
    }
    session_dirs = [
        UPLOAD_DIR / "it_migration",
        UPLOAD_DIR / "it_data_import",
    ]
    session_files = 0
    for d in session_dirs:
        if d.exists():
            session_files += len(list(d.glob("*.json")))

    total_delete = sum(to_delete.values()) + session_files
    return {
        "to_delete": to_delete,
        "session_cache_files": session_files,
        "total_operational_records": sum(to_delete.values()),
        "total_including_session_files": total_delete,
        "will_not_delete": preserved,
        "preserved_notes": [
            "Asset types and IT settings (configuration) are preserved.",
            "Help Desk tickets are not deleted (shared module).",
            "Employees/Users, Teams, Customers, Projects, Timesheets, Roles are preserved.",
        ],
        "confirm_phrase": CONFIRM_PHRASE,
        "message": (
            "Preview only. No data deleted. Admin must POST reset with "
            f'confirmation_phrase="{CONFIRM_PHRASE}".'
        ),
    }


def execute_reset(
    db: Session,
    *,
    actor: User,
    confirmation_phrase: str,
    confirm: bool,
) -> dict[str, Any]:
    if not confirm:
        raise ProTrackValidationError("Reset requires confirm=true.")
    if (confirmation_phrase or "").strip() != CONFIRM_PHRASE:
        raise ProTrackValidationError(
            f'Confirmation phrase must be exactly "{CONFIRM_PHRASE}".'
        )

    before = preview_reset(db)
    deleted: dict[str, int] = {}

    try:
        for label, model in _WIPE_ORDER:
            n = _count(db, model)
            if n:
                db.execute(delete(model))
            deleted[label] = n

        # Soft-deleted assets also wiped above via full table delete.
        db.flush()

        # Clear analyze session caches (filesystem)
        session_cleared = 0
        for d in (UPLOAD_DIR / "it_migration", UPLOAD_DIR / "it_data_import"):
            if not d.exists():
                continue
            for path in d.glob("*.json"):
                try:
                    path.unlink()
                    session_cleared += 1
                except OSError:
                    pass
        deleted["session_cache_files"] = session_cleared

        # Orphan check — operational tables must be empty
        orphans: dict[str, int] = {}
        for label, model in _WIPE_ORDER:
            left = _count(db, model)
            if left:
                orphans[label] = left
        if orphans:
            raise ProTrackValidationError(
                f"Reset left orphan IT rows: {orphans}. Rolling back."
            )

        # Master data must be unchanged vs preview
        after_preserved = {
            "employees_users": _count(db, User),
            "customers": _count(db, Customer),
            "projects": _count(db, Project),
            "teams": _count(db, Team),
            "timesheet_entries": _count(db, TimesheetEntry),
            "roles": _count(db, Role),
            "asset_types": _count(db, AssetType),
            "it_settings": _count(db, ITSettings),
        }
        for key, expected in before["will_not_delete"].items():
            if after_preserved.get(key) != expected:
                raise ProTrackValidationError(
                    f"Master data count changed for {key}: "
                    f"before={expected} after={after_preserved.get(key)}. Rolling back."
                )

        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_settings,
            entity_id=actor.id,
            action=ActivityAction.it_settings_updated,
            new_value={
                "event": "it_operational_data_reset",
                "deleted": deleted,
                "preserved": after_preserved,
            },
            outcome="success",
            module=MODULE,
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "status": "reset_complete",
        "deleted": deleted,
        "will_not_delete": after_preserved,
        "message": (
            "IT operational data reset complete. Configuration and ProTrack master "
            "data preserved. Module is ready for a clean migration."
        ),
    }
