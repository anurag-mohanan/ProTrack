"""Help-desk / ticketing domain logic: routing, access, scoping, lifecycle.

Any authenticated employee can raise a ticket. Tickets are routed by
``category`` to a responsible group ("agents"), who work them through a simple
status lifecycle. Administrators and the executive tier manage every category;
IT / HR / Office-Administrator roles manage the categories they own. The
requester and the assignee can always see (and comment on) their own ticket.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import EXECUTIVE_ROLES
from app.core.permissions import get_role_name, is_admin
from app.models.models import Ticket, TicketCategoryRoute, User

# --- Display labels -------------------------------------------------------
CATEGORY_LABELS: dict[str, str] = {
    "it": "IT Support",
    "facility": "Facility / Infrastructure",
    "admin": "Administration",
    "hr": "Human Resources",
    "other": "Other",
}
STATUS_LABELS: dict[str, str] = {
    "open": "Open",
    "in_progress": "In Progress",
    "on_hold": "On Hold",
    "resolved": "Resolved",
    "closed": "Closed",
    "cancelled": "Cancelled",
}
PRIORITY_LABELS: dict[str, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "urgent": "Urgent",
}

OPEN_STATUSES = frozenset({"open", "in_progress", "on_hold"})
TERMINAL_STATUSES = frozenset({"resolved", "closed", "cancelled"})

# --- Agent routing --------------------------------------------------------
IT_AGENT_ROLES = frozenset(
    {"Director of IT", "IT Manager", "System Administrator", "IT Executive", "IT Support Engineer"}
)
HR_AGENT_ROLES = frozenset(
    {"Director of HR", "HR Manager", "HR Executive", "HR", "HR Assistant"}
)
OFFICE_ADMIN_ROLES = frozenset({"Office Administrator"})

# category -> roles that own (manage) that category's queue
CATEGORY_RESPONDER_ROLES: dict[str, frozenset[str]] = {
    "it": IT_AGENT_ROLES,
    "facility": OFFICE_ADMIN_ROLES | {"Director of HR", "HR Manager"},
    "admin": OFFICE_ADMIN_ROLES | HR_AGENT_ROLES,
    "hr": HR_AGENT_ROLES,
    "other": OFFICE_ADMIN_ROLES,
}

# category -> org department code used to tag routing (best-effort)
CATEGORY_DEPARTMENT_CODE: dict[str, str] = {
    "it": "it",
    "facility": "hr_admin",
    "admin": "hr_admin",
    "hr": "hr_admin",
}

ALL_AGENT_ROLES = IT_AGENT_ROLES | HR_AGENT_ROLES | OFFICE_ADMIN_ROLES


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Configured routing (admin-set contact per category) ------------------
def category_route_map(db: Session) -> dict[str, TicketCategoryRoute]:
    """Return the admin-configured route rows keyed by category."""
    rows = db.scalars(select(TicketCategoryRoute)).all()
    return {row.category: row for row in rows}


def category_contact_id(db: Session, category: str) -> UUID | None:
    """The admin-configured default assignee for a category, if any."""
    return db.scalar(
        select(TicketCategoryRoute.assignee_user_id).where(
            TicketCategoryRoute.category == category
        )
    )


def _categories_where_user_is_contact(db: Session, user: User) -> set[str]:
    rows = db.execute(
        select(TicketCategoryRoute.category).where(
            TicketCategoryRoute.assignee_user_id == user.id
        )
    ).all()
    return {row[0] for row in rows}


# --- Access ---------------------------------------------------------------
def can_manage_all_tickets(db: Session, user: User) -> bool:
    """Admin and the executive tier oversee every category."""
    if is_admin(db, user):
        return True
    return get_role_name(db, user) in EXECUTIVE_ROLES


def manageable_categories(db: Session, user: User) -> set[str]:
    """Categories whose queue this user works. Empty for a plain requester.

    Combines the role-based responder queues with any category this user is the
    admin-configured contact for.
    """
    if can_manage_all_tickets(db, user):
        return set(CATEGORY_LABELS.keys())
    role_name = get_role_name(db, user)
    categories = {
        category
        for category, roles in CATEGORY_RESPONDER_ROLES.items()
        if role_name in roles
    }
    categories |= _categories_where_user_is_contact(db, user)
    return categories


def is_ticket_agent(db: Session, user: User) -> bool:
    """Whether the user works any ticket queue (sees the agent dashboard)."""
    return bool(manageable_categories(db, user))


def can_manage_ticket(db: Session, user: User, ticket: Ticket) -> bool:
    """Whether the user may triage / update / assign this specific ticket."""
    if can_manage_all_tickets(db, user):
        return True
    if ticket.assignee_id == user.id:
        return True
    return ticket.category in manageable_categories(db, user)


def can_view_ticket(db: Session, user: User, ticket: Ticket) -> bool:
    if ticket.requester_id == user.id:
        return True
    return can_manage_ticket(db, user, ticket)


# --- Ticket number --------------------------------------------------------
def next_ticket_number(db: Session) -> str:
    count = db.scalar(select(func.count(Ticket.id))) or 0
    candidate_index = count + 1
    while True:
        number = f"TKT-{candidate_index:06d}"
        exists = db.scalar(select(Ticket.id).where(Ticket.ticket_number == number))
        if exists is None:
            return number
        candidate_index += 1


def default_department_id_for_category(db: Session, category: str) -> UUID | None:
    # An explicit admin-configured department wins over the category default.
    configured = db.scalar(
        select(TicketCategoryRoute.org_department_id).where(
            TicketCategoryRoute.category == category
        )
    )
    if configured is not None:
        return configured
    code = CATEGORY_DEPARTMENT_CODE.get(category)
    if code is None:
        return None
    from app.models.models import OrgDepartment

    return db.scalar(select(OrgDepartment.id).where(OrgDepartment.code == code))


def fallback_role_names(category: str) -> list[str]:
    """Role names that own a category when no explicit contact is configured."""
    return sorted(CATEGORY_RESPONDER_ROLES.get(category, frozenset()))


# --- Lifecycle ------------------------------------------------------------
def apply_status_timestamps(ticket: Ticket, new_status: str) -> None:
    """Maintain resolved_at / closed_at as the status moves through its lifecycle."""
    if new_status == "resolved" and ticket.resolved_at is None:
        ticket.resolved_at = _now()
    if new_status == "closed" and ticket.closed_at is None:
        ticket.closed_at = _now()
    if new_status in OPEN_STATUSES:
        # Reopened — clear terminal markers.
        ticket.resolved_at = None
        ticket.closed_at = None
    ticket.status = new_status


# --- Queries --------------------------------------------------------------
def build_visible_tickets_query(db: Session, user: User):
    """Base select for tickets this user may see, eager-loading people."""
    stmt = select(Ticket).options(
        selectinload(Ticket.requester),
        selectinload(Ticket.assignee),
    )
    if can_manage_all_tickets(db, user):
        return stmt
    categories = manageable_categories(db, user)
    conditions = [Ticket.requester_id == user.id, Ticket.assignee_id == user.id]
    if categories:
        conditions.append(Ticket.category.in_(categories))
    return stmt.where(or_(*conditions))


def compute_stats(db: Session, user: User) -> dict[str, int]:
    base = build_visible_tickets_query(db, user).subquery()
    counts_by_status = dict(
        db.execute(
            select(base.c.status, func.count()).group_by(base.c.status)
        ).all()
    )
    total = sum(int(v) for v in counts_by_status.values())
    assigned_to_me = int(
        db.scalar(
            select(func.count()).select_from(base).where(base.c.assignee_id == user.id)
        )
        or 0
    )
    raised_by_me = int(
        db.scalar(
            select(func.count()).select_from(base).where(base.c.requester_id == user.id)
        )
        or 0
    )
    return {
        "total": total,
        "open": int(counts_by_status.get("open", 0)),
        "in_progress": int(counts_by_status.get("in_progress", 0)),
        "on_hold": int(counts_by_status.get("on_hold", 0)),
        "resolved": int(counts_by_status.get("resolved", 0)),
        "closed": int(counts_by_status.get("closed", 0)),
        "cancelled": int(counts_by_status.get("cancelled", 0)),
        "assigned_to_me": assigned_to_me,
        "raised_by_me": raised_by_me,
    }
