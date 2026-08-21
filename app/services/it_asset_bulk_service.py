"""Bulk IT asset operations — validated, audited, transactional where required."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import (
    MODULE_IT_OPERATIONS,
    SPECIAL_ASSIGN_IT_ASSETS,
    SPECIAL_MANAGE_IT_ASSETS,
    SPECIAL_RETURN_CUSTOMER_ASSETS,
    user_has_special,
)
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import get_role_name
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import Asset, Computer, IPAssignmentHistory
from app.models.models import Customer, User
from app.services import it_asset_service
from app.services.activity_service import log_activity

MODULE = MODULE_IT_OPERATIONS

BulkAction = Literal[
    "delete",
    "assign_user",
    "assign_location",
    "change_status",
    "change_ownership",
    "renumber",
    "return_to_customer",
]

MAX_BULK_IDS = 2000

_STATUS_RULES: dict[tuple[str, str], str] = {
    ("disposed", "available"): "force",
    ("disposed", "assigned"): "block",
    ("disposed", "maintenance"): "force",
    ("retired", "assigned"): "force",
    ("retired", "available"): "force",
    ("returned_to_customer", "available"): "force",
    ("returned_to_customer", "assigned"): "block",
    ("maintenance", "assigned"): "force",
}


def _role(db: Session, user: User) -> str:
    return get_role_name(db, user) or ""


def _require_special(db: Session, user: User, special: str) -> None:
    role = _role(db, user)
    if not user_has_special(user, role, special):
        raise ProTrackValidationError(f"Requires {special} permission.")


def list_asset_ids(
    db: Session,
    *,
    status: str | None = None,
    asset_type_id: UUID | None = None,
    search: str | None = None,
    inventory_scope: str = "current",
    purchased_by: str | None = None,
    owner_customer_id: UUID | None = None,
    customer_used_for_id: UUID | None = None,
    limit: int = MAX_BULK_IDS,
) -> tuple[list[UUID], int]:
    rows, total = it_asset_service.list_assets(
        db,
        status=status,
        asset_type_id=asset_type_id,
        search=search,
        inventory_scope=inventory_scope,
        purchased_by=purchased_by,
        owner_customer_id=owner_customer_id,
        customer_used_for_id=customer_used_for_id,
        skip=0,
        limit=min(max(limit, 1), MAX_BULK_IDS),
    )
    return [r.id for r in rows], total


def _load_assets(db: Session, asset_ids: list[UUID]) -> list[Asset]:
    if not asset_ids:
        return []
    if len(asset_ids) > MAX_BULK_IDS:
        raise ProTrackValidationError(
            f"At most {MAX_BULK_IDS} assets can be selected for a bulk action."
        )
    rows = list(
        db.scalars(
            select(Asset)
            .options(
                selectinload(Asset.asset_type),
                selectinload(Asset.computer),
                selectinload(Asset.assignments),
            )
            .where(Asset.id.in_(asset_ids), Asset.is_deleted.is_(False))
        ).all()
    )
    by_id = {a.id: a for a in rows}
    missing = [i for i in asset_ids if i not in by_id]
    if missing:
        raise ProTrackValidationError(
            f"{len(missing)} selected asset(s) were not found or are deleted."
        )
    return [by_id[i] for i in asset_ids]


def _assignee_label(db: Session, asset: Asset) -> str | None:
    asg = it_asset_service.get_current_assignment(db, asset.id)
    if asg is None:
        return None
    user = db.get(User, asg.assigned_to_user_id)
    if user is None:
        return str(asg.assigned_to_user_id)
    name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
    return name or user.email


def _active_ip_for_asset(db: Session, asset_id: UUID) -> IPAssignmentHistory | None:
    return db.scalar(
        select(IPAssignmentHistory)
        .where(
            IPAssignmentHistory.assigned_to_asset_id == asset_id,
            IPAssignmentHistory.released_date.is_(None),
        )
        .limit(1)
    )


def collect_delete_dependencies(
    db: Session, assets: list[Asset]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for asset in assets:
        blockers: list[str] = []
        warnings: list[str] = []
        if it_asset_service.get_current_assignment(db, asset.id) is not None:
            name = _assignee_label(db, asset) or "employee"
            blockers.append(f"Assigned to {name}")
        if asset.status == "returned_to_customer":
            blockers.append("Returned to customer (history must be retained)")
        if asset.status == "maintenance":
            warnings.append("Under maintenance")
        computer = asset.computer or db.scalar(
            select(Computer).where(Computer.asset_id == asset.id).limit(1)
        )
        if computer is not None:
            warnings.append(f"Linked computer {computer.computer_name}")
        if _active_ip_for_asset(db, asset.id) is not None:
            warnings.append("Has active IP assignment")
        out.append(
            {
                "asset_id": asset.id,
                "asset_number": asset.asset_number,
                "status": asset.status,
                "blockers": blockers,
                "warnings": warnings,
                "can_delete": len(blockers) == 0,
            }
        )
    return out


def _build_renumber_preview(
    db: Session, assets: list[Asset], params: dict[str, Any]
) -> dict[str, Any]:
    prefix = str(params.get("prefix") if params.get("prefix") is not None else "IT-")
    try:
        start = int(params.get("starting_number", 1))
        digits = int(params.get("digits", 3))
    except (TypeError, ValueError) as exc:
        raise ProTrackValidationError(
            "starting_number and digits must be integers."
        ) from exc
    if digits < 1 or digits > 10:
        raise ProTrackValidationError("digits must be between 1 and 10.")
    if start < 0:
        raise ProTrackValidationError("starting_number must be >= 0.")
    suffix = str(params.get("suffix") or "")
    mappings: list[dict[str, Any]] = []
    generated: list[str] = []
    for i, asset in enumerate(assets):
        new_number = f"{prefix}{str(start + i).zfill(digits)}{suffix}"
        generated.append(new_number)
        mappings.append(
            {
                "asset_id": asset.id,
                "current": asset.asset_number,
                "new": new_number,
            }
        )

    seen: set[str] = set()
    batch_dupes: list[str] = []
    for n in generated:
        if n in seen:
            batch_dupes.append(n)
        seen.add(n)

    conflicts: list[str] = []
    for mapping in mappings:
        existing = db.scalar(
            select(Asset).where(
                Asset.asset_number == mapping["new"],
                Asset.is_deleted.is_(False),
            )
        )
        if existing is None:
            continue
        if existing.id == mapping["asset_id"]:
            continue
        other_map = next((m for m in mappings if m["asset_id"] == existing.id), None)
        if other_map is None:
            conflicts.append(mapping["new"])
        elif other_map["new"] == mapping["new"]:
            conflicts.append(mapping["new"])

    return {
        "preview": mappings,
        "batch_duplicates": batch_dupes,
        "existing_conflicts": sorted(set(conflicts)),
        "can_apply": not batch_dupes and not conflicts,
        "warning": "Changing asset numbers may affect references to these assets.",
    }


def preview_bulk_action(
    db: Session,
    *,
    actor: User,
    action: BulkAction,
    asset_ids: list[UUID],
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = parameters or {}
    assets = _load_assets(db, asset_ids)
    base: dict[str, Any] = {
        "action": action,
        "selected": len(assets),
        "asset_numbers": [a.asset_number for a in assets],
    }
    if action == "delete":
        _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
        deps = collect_delete_dependencies(db, assets)
        blocked = [d for d in deps if not d["can_delete"]]
        return {
            **base,
            "dependencies": deps,
            "blocked_count": len(blocked),
            "eligible_count": len(assets) - len(blocked),
        }
    if action == "assign_user":
        _require_special(db, actor, SPECIAL_ASSIGN_IT_ASSETS)
        assigned = []
        available = []
        ineligible = []
        for a in assets:
            if a.status == "returned_to_customer":
                ineligible.append(
                    {"asset_number": a.asset_number, "reason": f"Status is {a.status}"}
                )
            elif it_asset_service.get_current_assignment(db, a.id) is not None:
                assigned.append(
                    {
                        "asset_number": a.asset_number,
                        "assignee": _assignee_label(db, a),
                        "has_computer": bool(
                            a.computer
                            or db.scalar(
                                select(Computer.id)
                                .where(Computer.asset_id == a.id)
                                .limit(1)
                            )
                        ),
                    }
                )
            elif a.status != "available":
                ineligible.append(
                    {
                        "asset_number": a.asset_number,
                        "reason": f"Must be available (current: {a.status})",
                    }
                )
            else:
                available.append(a.asset_number)
        return {
            **base,
            "already_assigned": assigned,
            "available": available,
            "ineligible": ineligible,
        }
    if action == "change_status":
        _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
        target = str(params.get("status") or "").strip()
        transitions = []
        for a in assets:
            rule = _STATUS_RULES.get((a.status, target))
            reason = None
            if target == "assigned":
                reason = "Use Assign User to set assigned status"
                rule = "block"
            elif target == "available" and it_asset_service.get_current_assignment(
                db, a.id
            ):
                reason = "Return the asset before setting Available"
                rule = "block"
            elif rule == "block":
                reason = f"Cannot change {a.status} → {target}"
            elif rule == "force":
                reason = f"Requires administrator confirmation ({a.status} → {target})"
            transitions.append(
                {
                    "asset_number": a.asset_number,
                    "from_status": a.status,
                    "to_status": target,
                    "rule": rule or "ok",
                    "reason": reason,
                }
            )
        return {**base, "transitions": transitions, "target_status": target}
    if action == "renumber":
        _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
        return {**base, **_build_renumber_preview(db, assets, params)}
    if action == "return_to_customer":
        _require_special(db, actor, SPECIAL_RETURN_CUSTOMER_ASSETS)
        eligible = []
        ineligible = []
        for a in assets:
            if a.purchased_by != "customer":
                ineligible.append(
                    {"asset_number": a.asset_number, "reason": "Not customer-owned"}
                )
            elif a.status == "returned_to_customer":
                ineligible.append(
                    {"asset_number": a.asset_number, "reason": "Already returned"}
                )
            else:
                eligible.append(a.asset_number)
        return {**base, "eligible": eligible, "ineligible": ineligible}
    return base


def _log_bulk_summary(
    db: Session,
    *,
    actor: User,
    action: str,
    asset_ids: list[UUID],
    details: dict[str, Any],
) -> None:
    if not asset_ids:
        return
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_asset,
        entity_id=asset_ids[0],
        action=ActivityAction.it_asset_updated,
        new_value={
            "bulk_action": action,
            "record_count": len(asset_ids),
            "asset_ids": [str(i) for i in asset_ids[:50]],
            **details,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )


def execute_bulk_action(
    db: Session,
    *,
    actor: User,
    action: BulkAction,
    asset_ids: list[UUID],
    parameters: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = dict(parameters or {})
    opts = dict(options or {})
    assets = _load_assets(db, asset_ids)

    if action == "delete":
        return _bulk_delete(db, actor=actor, assets=assets, opts=opts)
    if action == "assign_user":
        return _bulk_assign_user(
            db, actor=actor, assets=assets, params=params, opts=opts
        )
    if action == "assign_location":
        return _bulk_assign_location(db, actor=actor, assets=assets, params=params)
    if action == "change_status":
        return _bulk_change_status(
            db, actor=actor, assets=assets, params=params, opts=opts
        )
    if action == "change_ownership":
        return _bulk_change_ownership(db, actor=actor, assets=assets, params=params)
    if action == "renumber":
        return _bulk_renumber(db, actor=actor, assets=assets, params=params)
    if action == "return_to_customer":
        return _bulk_return_to_customer(
            db, actor=actor, assets=assets, params=params, opts=opts
        )
    raise ProTrackValidationError(f"Unknown bulk action '{action}'.")


def _result(
    *,
    action: str,
    selected: int,
    updated: list[str],
    skipped: list[dict[str, str]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "action": action,
        "selected": selected,
        "updated": len(updated),
        "updated_asset_numbers": updated,
        "skipped": len(skipped),
        "skipped_details": skipped,
        "failed": 0,
        "failed_details": [],
    }
    if extra:
        body.update(extra)
    return body


def _bulk_delete(
    db: Session, *, actor: User, assets: list[Asset], opts: dict[str, Any]
) -> dict[str, Any]:
    _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
    deps = collect_delete_dependencies(db, assets)
    blocked = {d["asset_number"]: d for d in deps if not d["can_delete"]}
    allow_partial = bool(opts.get("allow_partial", False))
    if blocked and not allow_partial:
        raise ProTrackValidationError(
            f"{len(blocked)} of {len(assets)} selected assets cannot be deleted due to "
            "active relationships. Review dependencies and retry."
        )
    updated: list[str] = []
    skipped: list[dict[str, str]] = []
    for asset in assets:
        if asset.asset_number in blocked:
            skipped.append(
                {
                    "asset_number": asset.asset_number,
                    "reason": "; ".join(blocked[asset.asset_number]["blockers"]),
                }
            )
            continue
        it_asset_service.soft_delete_asset(db, asset, actor=actor, commit=False)
        updated.append(asset.asset_number)
    _log_bulk_summary(
        db,
        actor=actor,
        action="delete",
        asset_ids=[a.id for a in assets if a.asset_number in updated],
        details={"deleted": updated, "skipped": skipped},
    )
    db.commit()
    return _result(
        action="delete",
        selected=len(assets),
        updated=updated,
        skipped=skipped,
        extra={"dependencies": deps},
    )


def _bulk_assign_user(
    db: Session,
    *,
    actor: User,
    assets: list[Asset],
    params: dict[str, Any],
    opts: dict[str, Any],
) -> dict[str, Any]:
    _require_special(db, actor, SPECIAL_ASSIGN_IT_ASSETS)
    user_id_raw = params.get("user_id") or params.get("employee_id")
    if not user_id_raw:
        raise ProTrackValidationError("user_id is required.")
    user_id = UUID(str(user_id_raw))
    assignee = db.get(User, user_id)
    if assignee is None or assignee.is_deleted:
        raise ProTrackValidationError("Assignee user not found.")
    when_raw = params.get("assigned_date")
    assigned_date = date.fromisoformat(str(when_raw)) if when_raw else date.today()
    notes = str(params.get("notes") or "").strip() or None
    replace = bool(opts.get("replace_assignments", False))
    only_unassigned = bool(opts.get("only_unassigned", False))

    already = [
        a
        for a in assets
        if it_asset_service.get_current_assignment(db, a.id) is not None
    ]
    if already and not replace and not only_unassigned:
        raise ProTrackValidationError(
            f"{len(already)} assets are currently assigned. Choose replace_assignments "
            "or only_unassigned."
        )

    updated: list[str] = []
    skipped: list[dict[str, str]] = []
    for asset in assets:
        open_asg = it_asset_service.get_current_assignment(db, asset.id)
        try:
            if open_asg is not None:
                if only_unassigned and not replace:
                    skipped.append(
                        {
                            "asset_number": asset.asset_number,
                            "reason": "Already assigned",
                        }
                    )
                    continue
                if not replace:
                    skipped.append(
                        {
                            "asset_number": asset.asset_number,
                            "reason": "Already assigned",
                        }
                    )
                    continue
                it_asset_service.transfer_asset(
                    db,
                    asset,
                    to_user_id=user_id,
                    by_user=actor,
                    assigned_date=assigned_date,
                    notes=notes,
                    commit=False,
                )
            else:
                if asset.status != "available":
                    skipped.append(
                        {
                            "asset_number": asset.asset_number,
                            "reason": f"Status is {asset.status}",
                        }
                    )
                    continue
                it_asset_service.assign_asset(
                    db,
                    asset,
                    user_id=user_id,
                    by_user=actor,
                    assigned_date=assigned_date,
                    notes=notes,
                    commit=False,
                )
            updated.append(asset.asset_number)
        except ProTrackValidationError as exc:
            skipped.append({"asset_number": asset.asset_number, "reason": str(exc)})

    _log_bulk_summary(
        db,
        actor=actor,
        action="assign_user",
        asset_ids=[a.id for a in assets if a.asset_number in updated],
        details={
            "assigned_to_user_id": str(user_id),
            "updated": updated,
            "skipped": skipped,
        },
    )
    db.commit()
    return _result(
        action="assign_user", selected=len(assets), updated=updated, skipped=skipped
    )


def _bulk_assign_location(
    db: Session, *, actor: User, assets: list[Asset], params: dict[str, Any]
) -> dict[str, Any]:
    _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
    if "location" not in params:
        raise ProTrackValidationError("location is required.")
    location = str(params.get("location") or "").strip() or None
    updated: list[str] = []
    for asset in assets:
        old_loc = asset.location
        asset.location = location
        db.add(asset)
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_asset,
            entity_id=asset.id,
            action=ActivityAction.it_asset_updated,
            old_value={"location": old_loc},
            new_value={"location": location},
            outcome="success",
            module=MODULE,
            commit=False,
        )
        updated.append(asset.asset_number)
    _log_bulk_summary(
        db,
        actor=actor,
        action="assign_location",
        asset_ids=[a.id for a in assets],
        details={"location": location, "updated": updated},
    )
    db.commit()
    return _result(
        action="assign_location", selected=len(assets), updated=updated, skipped=[]
    )


def _bulk_change_status(
    db: Session,
    *,
    actor: User,
    assets: list[Asset],
    params: dict[str, Any],
    opts: dict[str, Any],
) -> dict[str, Any]:
    _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
    target = str(params.get("status") or "").strip()
    if target not in it_asset_service.ASSET_STATUSES:
        raise ProTrackValidationError(f"Invalid asset status '{target}'.")
    force = bool(opts.get("force_status", False))
    allow_partial = bool(opts.get("allow_partial", False))

    updated: list[str] = []
    skipped: list[dict[str, str]] = []
    for asset in assets:
        rule = _STATUS_RULES.get((asset.status, target))
        reason = None
        if target == "assigned":
            reason = "Use Assign User to set assigned status"
            rule = "block"
        elif target == "available" and it_asset_service.get_current_assignment(
            db, asset.id
        ):
            reason = "Return the asset before setting Available"
            rule = "block"
        elif rule == "block":
            reason = f"Cannot change {asset.status} → {target}"
        elif rule == "force" and not force:
            reason = f"Requires confirmation for {asset.status} → {target}"
            rule = "block"

        if rule == "block":
            skipped.append(
                {
                    "asset_number": asset.asset_number,
                    "reason": reason or "Blocked transition",
                }
            )
            continue
        old = asset.status
        asset.status = target
        db.add(asset)
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_asset,
            entity_id=asset.id,
            action=ActivityAction.it_asset_updated,
            old_value={"status": old},
            new_value={"status": target},
            outcome="success",
            module=MODULE,
            commit=False,
        )
        updated.append(asset.asset_number)

    if skipped and not allow_partial:
        db.rollback()
        raise ProTrackValidationError(
            f"{len(skipped)} of {len(assets)} assets cannot use this status change. "
            "Adjust selection, confirm forced transitions, or enable allow_partial."
        )

    _log_bulk_summary(
        db,
        actor=actor,
        action="change_status",
        asset_ids=[a.id for a in assets if a.asset_number in updated],
        details={"status": target, "updated": updated, "skipped": skipped},
    )
    db.commit()
    return _result(
        action="change_status", selected=len(assets), updated=updated, skipped=skipped
    )


def _bulk_change_ownership(
    db: Session, *, actor: User, assets: list[Asset], params: dict[str, Any]
) -> dict[str, Any]:
    _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
    purchased_by = str(params.get("purchased_by") or "").strip()
    if not purchased_by:
        raise ProTrackValidationError("purchased_by is required.")
    owner_raw = params.get("owner_customer_id")
    owner_customer_id = UUID(str(owner_raw)) if owner_raw else None
    touch_used_for = "customer_used_for_id" in params
    used_for_raw = params.get("customer_used_for_id")
    used_for_id = UUID(str(used_for_raw)) if used_for_raw not in (None, "") else None

    it_asset_service._validate_ownership(
        purchased_by=purchased_by, owner_customer_id=owner_customer_id
    )
    if owner_customer_id is not None and db.get(Customer, owner_customer_id) is None:
        raise ProTrackValidationError("Owner customer not found.")
    if touch_used_for and used_for_id is not None and db.get(Customer, used_for_id) is None:
        raise ProTrackValidationError("Customer used for not found.")

    updated: list[str] = []
    for asset in assets:
        old = {
            "purchased_by": asset.purchased_by,
            "owner_customer_id": str(asset.owner_customer_id)
            if asset.owner_customer_id
            else None,
            "customer_used_for_id": str(asset.customer_used_for_id)
            if asset.customer_used_for_id
            else None,
        }
        asset.purchased_by = purchased_by
        asset.owner_customer_id = owner_customer_id
        if touch_used_for:
            asset.customer_used_for_id = used_for_id
        db.add(asset)
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_asset,
            entity_id=asset.id,
            action=ActivityAction.it_asset_ownership_changed,
            old_value=old,
            new_value={
                "purchased_by": asset.purchased_by,
                "owner_customer_id": str(asset.owner_customer_id)
                if asset.owner_customer_id
                else None,
                "customer_used_for_id": str(asset.customer_used_for_id)
                if asset.customer_used_for_id
                else None,
            },
            outcome="success",
            module=MODULE,
            commit=False,
        )
        updated.append(asset.asset_number)

    _log_bulk_summary(
        db,
        actor=actor,
        action="change_ownership",
        asset_ids=[a.id for a in assets],
        details={
            "purchased_by": purchased_by,
            "owner_customer_id": str(owner_customer_id) if owner_customer_id else None,
            "updated": updated,
        },
    )
    db.commit()
    return _result(
        action="change_ownership", selected=len(assets), updated=updated, skipped=[]
    )


def _bulk_renumber(
    db: Session, *, actor: User, assets: list[Asset], params: dict[str, Any]
) -> dict[str, Any]:
    _require_special(db, actor, SPECIAL_MANAGE_IT_ASSETS)
    preview = _build_renumber_preview(db, assets, params)
    if not preview["can_apply"]:
        conflicts = preview["existing_conflicts"] or preview["batch_duplicates"]
        raise ProTrackValidationError(
            f"Generated asset number {conflicts[0]} already exists."
            if conflicts
            else "Renumber preview failed validation."
        )

    token = uuid4().hex[:12]
    for i, mapping in enumerate(preview["preview"]):
        asset = assets[i]
        assert asset.id == mapping["asset_id"]
        asset.asset_number = f"__tmp_{token}_{i}"
        db.add(asset)
    db.flush()

    updated: list[str] = []
    for i, mapping in enumerate(preview["preview"]):
        asset = assets[i]
        old_number = mapping["current"]
        new_number = mapping["new"]
        if not asset.legacy_asset_number:
            asset.legacy_asset_number = old_number
        asset.asset_number = new_number
        db.add(asset)
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_asset,
            entity_id=asset.id,
            action=ActivityAction.it_asset_updated,
            old_value={
                "asset_number": old_number,
                "previous_asset_number": old_number,
            },
            new_value={
                "asset_number": new_number,
                "legacy_asset_number": asset.legacy_asset_number,
            },
            outcome="success",
            module=MODULE,
            commit=False,
        )
        updated.append(f"{old_number}→{new_number}")

    _log_bulk_summary(
        db,
        actor=actor,
        action="renumber",
        asset_ids=[a.id for a in assets],
        details={"mappings": preview["preview"], "warning": preview["warning"]},
    )
    db.commit()
    return _result(
        action="renumber",
        selected=len(assets),
        updated=updated,
        skipped=[],
        extra={"preview": preview["preview"]},
    )


def _bulk_return_to_customer(
    db: Session,
    *,
    actor: User,
    assets: list[Asset],
    params: dict[str, Any],
    opts: dict[str, Any],
) -> dict[str, Any]:
    _require_special(db, actor, SPECIAL_RETURN_CUSTOMER_ASSETS)
    allow_partial = bool(opts.get("allow_partial", True))
    when_raw = params.get("return_date")
    return_date = date.fromisoformat(str(when_raw)) if when_raw else date.today()
    owner_raw = params.get("owner_customer_id")
    owner_customer_id = UUID(str(owner_raw)) if owner_raw else None
    notes = str(params.get("notes") or "").strip() or None
    received_by = str(params.get("received_by_name") or "").strip() or None
    condition = str(params.get("condition_at_return") or "").strip() or None
    reason = str(params.get("return_reason") or "").strip() or None

    updated: list[str] = []
    skipped: list[dict[str, str]] = []
    for asset in assets:
        try:
            it_asset_service.return_asset_to_customer(
                db,
                asset,
                by_user=actor,
                return_date=return_date,
                owner_customer_id=owner_customer_id,
                received_by_name=received_by,
                condition_at_return=condition,
                return_reason=reason,
                notes=notes,
                commit=False,
            )
            updated.append(asset.asset_number)
        except ProTrackValidationError as exc:
            skipped.append({"asset_number": asset.asset_number, "reason": str(exc)})

    if skipped and not allow_partial:
        db.rollback()
        raise ProTrackValidationError(
            f"{len(skipped)} of {len(assets)} assets cannot be returned to customer."
        )

    _log_bulk_summary(
        db,
        actor=actor,
        action="return_to_customer",
        asset_ids=[a.id for a in assets if a.asset_number in updated],
        details={"updated": updated, "skipped": skipped},
    )
    db.commit()
    return _result(
        action="return_to_customer",
        selected=len(assets),
        updated=updated,
        skipped=skipped,
    )
