"""IT offboard deprovisioning task generation (ticket-based, non-destructive)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Ticket, User
from app.services import it_account_service, it_asset_service, it_network_service
from app.services import ticketing_service as tickets
from app.services.ticketing_service import OPEN_STATUSES

OFFBOARD_TICKET_MARKER = "IT offboard deprovision"


def _employee_label(user: User) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.email or str(user.id)


def find_open_offboard_ticket(db: Session, user_id: UUID) -> Ticket | None:
    rows = db.scalars(
        select(Ticket).where(
            Ticket.category == "it",
            Ticket.status.in_(OPEN_STATUSES),
            Ticket.title.contains(OFFBOARD_TICKET_MARKER),
        )
    ).all()
    needle = str(user_id)
    for ticket in rows:
        if ticket.description and needle in ticket.description:
            return ticket
    return None


def ensure_offboard_tasks(
    db: Session,
    *,
    user: User,
    actor: User | None,
) -> Ticket | None:
    """Create (or reuse) an IT Help Desk ticket listing assets/accounts/IPs to reclaim.

    Does not auto-return assets, release IPs, or deactivate accounts — IT confirms
    those actions through the existing IT Operations workflows.
    """
    existing = find_open_offboard_ticket(db, user.id)
    if existing is not None:
        return existing

    assets = it_asset_service.list_assets_for_user(db, user.id)
    accounts = [
        row
        for row in it_account_service.list_accounts(db, user_id=user.id)
        if row.status == "active"
    ]
    ips = it_network_service.list_ips_for_user(db, user.id)

    if not assets and not accounts and not ips:
        return None

    label = _employee_label(user)
    asset_lines = "\n".join(
        f"- Asset {asset.asset_number} ({asset.status})"
        + (f" · {asset.make or ''} {asset.model or ''}".rstrip() if asset.make or asset.model else "")
        for asset in assets
    ) or "- None"
    account_lines = "\n".join(
        f"- {account.account_type}: {account.username or account.display_name or account.id}"
        for account in accounts
    ) or "- None"
    ip_lines = "\n".join(f"- {ip.address}" for ip in ips) or "- None"

    description = (
        f"{OFFBOARD_TICKET_MARKER} for {label}.\n"
        f"Employee user_id: {user.id}\n"
        f"Leaving date: {user.leaving_date.isoformat() if user.leaving_date else 'TBD'}\n\n"
        f"Assigned assets to return:\n{asset_lines}\n\n"
        f"Active IT accounts to deactivate:\n{account_lines}\n\n"
        f"Allocated IPs to release:\n{ip_lines}\n\n"
        "Complete each action in IT Operations, then close this ticket."
    )

    requester = actor if actor is not None else user
    assignee_id = tickets.category_contact_id(db, "it")
    ticket = Ticket(
        ticket_number=tickets.next_ticket_number(db),
        title=f"{OFFBOARD_TICKET_MARKER} · {label}",
        description=description,
        category="it",
        priority="high",
        status="open",
        requester_id=requester.id,
        assignee_id=assignee_id,
        org_department_id=tickets.default_department_id_for_category(db, "it"),
    )
    db.add(ticket)
    db.flush()
    return ticket
