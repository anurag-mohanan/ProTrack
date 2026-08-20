"""IT Operations dashboard aggregates and settings helpers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_IT_OPERATIONS
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import Asset, IPAddress, ITSettings, Network
from app.models.models import OnboardingChecklist, OnboardingChecklistItem, Ticket, User
from app.services.activity_service import log_activity
from app.services.it_asset_service import get_or_create_settings
from app.services.ticketing_service import OPEN_STATUSES

MODULE = MODULE_IT_OPERATIONS


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
            OnboardingChecklistItem.status == "pending",
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


def dashboard_summary(db: Session) -> dict[str, int]:
    total_assets = int(
        db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(
                Asset.is_deleted.is_(False),
                Asset.status.in_(
                    ("available", "assigned", "maintenance", "awaiting_return")
                ),
            )
        )
        or 0
    )
    assigned_assets = int(
        db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(Asset.is_deleted.is_(False), Asset.status == "assigned")
        )
        or 0
    )
    available_assets = int(
        db.scalar(
            select(func.count())
            .select_from(Asset)
            .where(Asset.is_deleted.is_(False), Asset.status == "available")
        )
        or 0
    )
    open_it_requests = int(
        db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.category == "it", Ticket.status.in_(OPEN_STATUSES))
        )
        or 0
    )
    pending_onboarding_tasks = int(
        db.scalar(
            select(func.count())
            .select_from(OnboardingChecklistItem)
            .where(
                OnboardingChecklistItem.responsibility == "it",
                OnboardingChecklistItem.status == "pending",
            )
        )
        or 0
    )
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
    return {
        "total_assets": total_assets,
        "assigned_assets": assigned_assets,
        "available_assets": available_assets,
        "open_it_requests": open_it_requests,
        "pending_onboarding_tasks": pending_onboarding_tasks,
        "networks": networks,
        "allocated_ips": allocated_ips,
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
