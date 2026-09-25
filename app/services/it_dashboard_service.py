"""IT Operations dashboard aggregates and settings helpers."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_IT_OPERATIONS
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import Asset, AssetAssignment, IPAddress, ITSettings, Network
from app.models.models import OnboardingChecklist, OnboardingChecklistItem, Ticket, User
from app.services.activity_service import log_activity
from app.services.it_asset_service import (
    CURRENT_INVENTORY_STATUSES,
    get_or_create_settings,
    warranty_alert_days,
)
from app.services.onboarding_task_service import UNRESOLVED_STATUSES, LEGACY_STATUS_MAP
from app.services.ticketing_service import OPEN_STATUSES

MODULE = MODULE_IT_OPERATIONS

UNRESOLVED_TASK_STATUSES = sorted(
    set(UNRESOLVED_STATUSES) | {k for k, v in LEGACY_STATUS_MAP.items() if v in UNRESOLVED_STATUSES}
)


def list_pending_it_onboarding_tasks(db: Session, *, limit: int = 50) -> list[dict]:
    """Pending onboarding checklist rows owned by the IT responsibility bucket."""
    rows = db.execute(
        select(OnboardingChecklistItem, OnboardingChecklist)
        .join(
            OnboardingChecklist,
            OnboardingChecklist.id == OnboardingChecklistItem.checklist_id,
        )
        .where(
            OnboardingChecklistItem.responsibility == "it",
            OnboardingChecklistItem.status.in_(UNRESOLVED_TASK_STATUSES),
        )
        .order_by(OnboardingChecklistItem.sort_order)
        .limit(limit)
    ).all()
    result: list[dict] = []
    for item, checklist in rows:
        result.append(
            {
                "item_id": item.id,
                "checklist_id": checklist.id,
                "item_text": item.item_text,
                "employee_name": checklist.employee_name,
                "employee_code": checklist.employee_code,
                "employee_user_id": checklist.employee_user_id,
                "joining_date": checklist.joining_date,
                "help_ticket_id": item.help_ticket_id,
                "owner_user_id": item.owner_user_id,
            }
        )
    return result


def _onboarding_attention_count(db: Session, *, responsibility: str) -> int:
    """Unresolved tasks with an actionable problem (missing/closed/cancelled request, blocked, overdue)."""
    from sqlalchemy.orm import selectinload

    from app.services.onboarding_task_service import attention_codes

    items = db.scalars(
        select(OnboardingChecklistItem)
        .join(OnboardingChecklist, OnboardingChecklist.id == OnboardingChecklistItem.checklist_id)
        .where(
            OnboardingChecklist.status == "in_progress",
            OnboardingChecklistItem.responsibility == responsibility,
            OnboardingChecklistItem.status.in_(UNRESOLVED_TASK_STATUSES),
        )
        .options(
            selectinload(OnboardingChecklistItem.help_ticket),
            selectinload(OnboardingChecklistItem.checklist),
        )
    ).all()
    return sum(1 for item in items if set(attention_codes(item)) - {"unassigned"})


def _recent_asset_movements(db: Session, *, limit: int = 10) -> list[dict]:
    """Latest assignment starts / returns, newest first."""
    rows = db.execute(
        select(AssetAssignment, Asset.asset_number, User.first_name, User.last_name)
        .join(Asset, Asset.id == AssetAssignment.asset_id)
        .join(User, User.id == AssetAssignment.assigned_to_user_id)
        .where(Asset.is_deleted.is_(False))
        .order_by(AssetAssignment.updated_at.desc())
        .limit(limit)
    ).all()
    movements: list[dict] = []
    for assignment, asset_number, first_name, last_name in rows:
        returned = assignment.returned_date is not None
        movements.append(
            {
                "asset_id": str(assignment.asset_id),
                "asset_number": asset_number,
                "user_id": str(assignment.assigned_to_user_id),
                "user_name": f"{first_name} {last_name}".strip(),
                "movement": "returned" if returned else "assigned",
                "date": (assignment.returned_date if returned else assignment.assigned_date),
            }
        )
    return movements


def dashboard_summary(db: Session, *, warranty_days: int | None = None) -> dict:
    today = date.today()
    window_days = warranty_days or warranty_alert_days(db)
    status_counts = {
        str(status): int(count)
        for status, count in db.execute(
            select(Asset.status, func.count())
            .where(Asset.is_deleted.is_(False))
            .group_by(Asset.status)
        ).all()
    }
    total_assets = sum(status_counts.get(s, 0) for s in CURRENT_INVENTORY_STATUSES)
    assigned_assets = status_counts.get("assigned", 0)
    available_assets = status_counts.get("available", 0)
    maintenance_assets = status_counts.get("maintenance", 0)

    in_inventory = (Asset.is_deleted.is_(False), Asset.status.in_(CURRENT_INVENTORY_STATUSES))
    warranty_expiring = int(
        db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(
                *in_inventory,
                Asset.warranty_expiry.is_not(None),
                Asset.warranty_expiry >= today,
                Asset.warranty_expiry <= today + timedelta(days=window_days),
            )
        )
        or 0
    )
    warranty_expired = int(
        db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(*in_inventory, Asset.warranty_expiry.is_not(None), Asset.warranty_expiry < today)
        )
        or 0
    )
    warranty_missing = int(
        db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(*in_inventory, Asset.warranty_expiry.is_(None))
        )
        or 0
    )

    it_open = (Ticket.category == "it", Ticket.status.in_(OPEN_STATUSES))
    open_it_requests = int(
        db.scalar(select(func.count()).select_from(Ticket).where(*it_open)) or 0
    )
    overdue_it_requests = int(
        db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(*it_open, Ticket.due_date.is_not(None), Ticket.due_date < today)
        )
        or 0
    )
    unassigned_it_requests = int(
        db.scalar(
            select(func.count()).select_from(Ticket).where(*it_open, Ticket.assignee_id.is_(None))
        )
        or 0
    )
    pending_onboarding_tasks = int(
        db.scalar(
            select(func.count())
            .select_from(OnboardingChecklistItem)
            .where(
                OnboardingChecklistItem.responsibility == "it",
                OnboardingChecklistItem.status.in_(UNRESOLVED_TASK_STATUSES),
            )
        )
        or 0
    )
    onboarding_it_attention = _onboarding_attention_count(db, responsibility="it")
    networks = int(
        db.scalar(
            select(func.count()).select_from(Network).where(Network.is_active.is_(True))
        )
        or 0
    )
    allocated_ips = int(
        db.scalar(
            select(func.count())
            .select_from(IPAddress)
            .where(IPAddress.status == "allocated")
        )
        or 0
    )
    from app.services import it_people_service

    computer_stats = it_people_service.computer_availability_summary(db)
    employees_without = it_people_service.count_active_employees_without_computer(db)
    from app.services import it_software_service

    software_stats = it_software_service.software_counts_for_dashboard(
        db, expiring_within_days=window_days
    )
    from app.services import resource_it_gap_service

    gap_stats = resource_it_gap_service.gap_counts_for_dashboard(db)

    from app.services import it_data_quality_service

    dq = it_data_quality_service.build_data_quality_report(db)
    open_issues = dq.get("open_issues") or []
    open_by_code = {row["code"]: int(row["count"]) for row in open_issues}

    from app.services import it_stock_service, virtual_seat_service

    stock_rows = it_stock_service.item_rows(db)
    demand = it_stock_service.upcoming_demand(db)
    seat_counts = virtual_seat_service.seat_summary(virtual_seat_service.derive_seats(db))
    return {
        "virtual_seats_total": seat_counts["total_seats"],
        "virtual_seats_incomplete": seat_counts["incomplete"],
        "stock_low_items": sum(1 for r in stock_rows if r["stock_status"] == it_stock_service.STATUS_LOW),
        "stock_out_items": sum(1 for r in stock_rows if r["stock_status"] == it_stock_service.STATUS_OUT),
        "stock_reorder_needed": sum(1 for r in stock_rows if r["reorder_needed"]),
        "stock_pending_restock": sum(r["pending_restock_requests"] for r in stock_rows),
        "stock_incoming_units": sum(r["incoming"] for r in stock_rows),
        "stock_upcoming_shortages": sum(1 for row in demand if row["shortage"]),
        "virtual_seat_conflicts": open_by_code.get("virtual_seat_conflicts", 0),
        "total_assets": total_assets,
        "assigned_assets": assigned_assets,
        "available_assets": available_assets,
        "maintenance_assets": maintenance_assets,
        "awaiting_return_assets": status_counts.get("awaiting_return", 0),
        "lost_assets": status_counts.get("lost", 0),
        "damaged_assets": status_counts.get("damaged", 0),
        "warranty_window_days": window_days,
        "warranty_expiring_assets": warranty_expiring,
        "warranty_expired_assets": warranty_expired,
        "warranty_missing_assets": warranty_missing,
        "open_it_requests": open_it_requests,
        "overdue_it_requests": overdue_it_requests,
        "unassigned_it_requests": unassigned_it_requests,
        "pending_onboarding_tasks": pending_onboarding_tasks,
        "onboarding_it_attention": onboarding_it_attention,
        "networks": networks,
        "allocated_ips": allocated_ips,
        **computer_stats,
        "employees_without_computer": employees_without,
        **software_stats,
        **gap_stats,
        "returned_assets": status_counts.get("returned_to_customer", 0),
        "retired_assets": status_counts.get("retired", 0),
        "disposed_assets": status_counts.get("disposed", 0),
        "computers_without_ip": open_by_code.get("computers_without_ip", 0),
        "computers_without_mac": open_by_code.get("computers_without_mac", 0),
        "data_quality_open_issues": int((dq.get("totals") or {}).get("issue_types") or 0),
        "data_quality_open_records": sum(open_by_code.values()),
        "recent_movements": _recent_asset_movements(db),
    }


def get_settings(db: Session) -> ITSettings:
    return get_or_create_settings(db)


def update_settings(
    db: Session,
    *,
    actor: User,
    asset_numbering_pattern: str | None = None,
    computer_naming_pattern: str | None = None,
    default_domain: str | None = None,
    default_email_domain: str | None = None,
    ip_allocation_strategy: str | None = None,
    settings_json: str | None = None,
    fields_set: set[str] | None = None,
) -> ITSettings:
    settings = get_or_create_settings(db)
    touched = fields_set or set()
    old = {
        "asset_numbering_pattern": settings.asset_numbering_pattern,
        "computer_naming_pattern": settings.computer_naming_pattern,
    }
    if "asset_numbering_pattern" in touched or (
        fields_set is None and asset_numbering_pattern is not None
    ):
        settings.asset_numbering_pattern = (
            asset_numbering_pattern or settings.asset_numbering_pattern
        ).strip()
    if "computer_naming_pattern" in touched or (
        fields_set is None and computer_naming_pattern is not None
    ):
        settings.computer_naming_pattern = (
            computer_naming_pattern or settings.computer_naming_pattern
        ).strip()
    if "default_domain" in touched or (fields_set is None and default_domain is not None):
        settings.default_domain = (default_domain or "").strip() or None
    if "default_email_domain" in touched or (
        fields_set is None and default_email_domain is not None
    ):
        settings.default_email_domain = (default_email_domain or "").strip() or None
    if "ip_allocation_strategy" in touched or (
        fields_set is None and ip_allocation_strategy is not None
    ):
        strategy = (ip_allocation_strategy or settings.ip_allocation_strategy).strip().lower()
        settings.ip_allocation_strategy = strategy
    if "settings_json" in touched or (fields_set is None and settings_json is not None):
        settings.settings_json = settings_json
    db.add(settings)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_settings,
        entity_id=settings.id,
        action=ActivityAction.it_settings_updated,
        old_value=old,
        new_value={
            "asset_numbering_pattern": settings.asset_numbering_pattern,
            "computer_naming_pattern": settings.computer_naming_pattern,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(settings)
    return settings
