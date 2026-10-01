"""Help-desk / ticketing domain logic: vocabulary, routing, access, scoping, stats.

There is one ticket store (``tickets``) for every module. Tickets are routed by
``category`` (and optionally ``subcategory`` / ``source_module``) to a queue whose
owners are configured by administrators (primary, backup, escalation). Admins
and the executive tier manage every queue; queue owners and role-based responder
groups manage their categories. The requester and the assignee can always see
(and comment on) their own ticket. Lifecycle changes live in
:mod:`app.services.ticket_workflow_service`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.access_control import EXECUTIVE_ROLES
from app.core.permissions import get_role_name, is_admin
from app.models.models import Ticket, TicketCategoryRoute, TicketRoutingRule, User

# --- Vocabulary -----------------------------------------------------------
CATEGORY_LABELS: dict[str, str] = {
    "it": "IT Support",
    "facility": "Facility / Infrastructure",
    "admin": "Administration",
    "hr": "Human Resources",
    "other": "Other",
}

NEW = "new"
OPEN = "open"
IN_PROGRESS = "in_progress"
PENDING_REQUESTER = "pending_requester"
PENDING_INTERNAL = "pending_internal"
PENDING_VENDOR = "pending_vendor"
LEGACY_ON_HOLD = "on_hold"
RESOLVED = "resolved"
CLOSED = "closed"
CANCELLED = "cancelled"

STATUS_LABELS: dict[str, str] = {
    NEW: "New",
    OPEN: "Open",
    IN_PROGRESS: "In Progress",
    PENDING_REQUESTER: "Waiting on requester",
    PENDING_INTERNAL: "Waiting (internal)",
    PENDING_VENDOR: "Waiting on vendor",
    LEGACY_ON_HOLD: "On Hold",
    RESOLVED: "Resolved",
    CLOSED: "Closed",
    CANCELLED: "Cancelled",
}
STATUS_ORDER: tuple[str, ...] = (
    NEW,
    OPEN,
    IN_PROGRESS,
    PENDING_REQUESTER,
    PENDING_INTERNAL,
    PENDING_VENDOR,
    RESOLVED,
    CLOSED,
    CANCELLED,
)

PENDING_STATUSES = frozenset({PENDING_REQUESTER, PENDING_INTERNAL, PENDING_VENDOR, LEGACY_ON_HOLD})
OPEN_STATUSES = frozenset({NEW, OPEN, IN_PROGRESS}) | PENDING_STATUSES
DONE_STATUSES = frozenset({RESOLVED, CLOSED})
TERMINAL_STATUSES = frozenset({RESOLVED, CLOSED, CANCELLED})

PRIORITY_LABELS: dict[str, str] = {
    "low": "Low",
    "normal": "Normal",
    "medium": "Normal",
    "high": "High",
    "urgent": "Urgent",
}
PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "urgent")
PRIORITY_RANK: dict[str, int] = {"urgent": 0, "high": 1, "normal": 2, "medium": 2, "low": 3}
HIGH_PRIORITIES = frozenset({"high", "urgent"})

# Request catalogue: category -> subcategory -> label. Families group them for
# the work-queue cards and saved views.
SUBCATEGORY_LABELS: dict[str, dict[str, str]] = {
    "it": {
        "hardware.computer": "Hardware · Computer / workstation",
        "hardware.peripheral": "Hardware · Monitor / mouse / peripheral",
        "hardware.repair": "Hardware · Fault / repair",
        "access.email": "Access · Email account",
        "access.domain": "Access · Domain / network login",
        "access.collaboration": "Access · Teams / collaboration",
        "access.storage": "Access · OneDrive / file storage",
        "software.install": "Software · Installation",
        "software.license": "Software · License",
        "asset.assign": "Asset · Assign",
        "asset.return": "Asset · Return",
        "asset.transfer": "Asset · Transfer",
        "asset.issue": "Asset · Issue / damage",
        "stock.restock": "Stock · Restock",
        "onboarding.provisioning": "Onboarding · IT provisioning",
        "offboarding.deprovision": "Offboarding · Deprovisioning",
        "general": "General IT request",
    },
}
SUBCATEGORY_FAMILY: dict[str, str] = {
    "hardware": "hardware",
    "access": "software",
    "software": "software",
    "asset": "asset",
    "stock": "asset",
    "onboarding": "onboarding",
    "offboarding": "offboarding",
}
FAMILY_LABELS: dict[str, str] = {
    "hardware": "Hardware",
    "software": "Software / License",
    "asset": "Asset issues",
    "onboarding": "Onboarding",
    "offboarding": "Offboarding",
}

SOURCE_LABELS: dict[str, str] = {
    "help_desk": "Help Desk",
    "onboarding": "Onboarding",
    "it_provisioning": "IT provisioning",
    "it_offboarding": "Offboarding",
    "it_stock": "Low stock",
    "it_asset": "Asset",
}

# --- Role-based responder groups (fallback when no named owner exists) -----
IT_AGENT_ROLES = frozenset(
    {"Director of IT", "IT Manager", "System Administrator", "IT Executive", "IT Support Engineer"}
)
HR_AGENT_ROLES = frozenset(
    {"Director of HR", "HR Manager", "HR Executive", "HR", "HR Assistant"}
)
OFFICE_ADMIN_ROLES = frozenset({"Office Administrator"})

CATEGORY_RESPONDER_ROLES: dict[str, frozenset[str]] = {
    "it": IT_AGENT_ROLES,
    "facility": OFFICE_ADMIN_ROLES | {"Director of HR", "HR Manager"},
    "admin": OFFICE_ADMIN_ROLES | HR_AGENT_ROLES,
    "hr": HR_AGENT_ROLES,
    "other": OFFICE_ADMIN_ROLES,
}

CATEGORY_DEPARTMENT_CODE: dict[str, str] = {
    "it": "it",
    "facility": "hr_admin",
    "admin": "hr_admin",
    "hr": "hr_admin",
}

ALL_AGENT_ROLES = IT_AGENT_ROLES | HR_AGENT_ROLES | OFFICE_ADMIN_ROLES


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_priority(value: str | None) -> str:
    raw = (value or "normal").strip().lower()
    if raw == "medium":
        return "normal"
    return raw if raw in PRIORITIES else "normal"


def priority_filter_values(value: str) -> list[str]:
    """Stored values matching a filter (legacy ``medium`` rows are Normal)."""
    normalized = normalize_priority(value)
    return ["normal", "medium"] if normalized == "normal" else [normalized]


def subcategory_family(subcategory: str | None) -> str | None:
    if not subcategory:
        return None
    return SUBCATEGORY_FAMILY.get(subcategory.split(".", 1)[0])


def subcategory_label(category: str, subcategory: str | None) -> str | None:
    if not subcategory:
        return None
    return SUBCATEGORY_LABELS.get(category, {}).get(subcategory, subcategory)


def family_subcategories(family: str) -> list[str]:
    prefixes = {prefix for prefix, fam in SUBCATEGORY_FAMILY.items() if fam == family}
    return [
        key
        for catalogue in SUBCATEGORY_LABELS.values()
        for key in catalogue
        if key.split(".", 1)[0] in prefixes
    ]


def is_overdue(ticket: Ticket, *, now: datetime | None = None) -> bool:
    if ticket.status not in OPEN_STATUSES:
        return False
    moment = now or _now()
    if ticket.due_date is not None and ticket.due_date < moment.date():
        return True
    return ticket.sla_due_at is not None and ticket.sla_due_at < moment


# --- Configured routing ---------------------------------------------------
def category_route_map(db: Session) -> dict[str, TicketCategoryRoute]:
    rows = db.scalars(select(TicketCategoryRoute)).all()
    return {row.category: row for row in rows}


def _route_in_effect(route: TicketCategoryRoute | TicketRoutingRule | None, today: date) -> bool:
    if route is None or not route.is_active:
        return False
    return route.effective_from is None or route.effective_from <= today


def category_contact_id(db: Session, category: str) -> UUID | None:
    """The configured primary contact for a category, if in effect."""
    route = db.scalar(select(TicketCategoryRoute).where(TicketCategoryRoute.category == category))
    if not _route_in_effect(route, date.today()):
        return None
    return route.assignee_user_id


def _configured_owner_categories(db: Session, user: User) -> set[str]:
    categories: set[str] = set()
    for row in db.execute(
        select(TicketCategoryRoute.category).where(
            or_(
                TicketCategoryRoute.assignee_user_id == user.id,
                TicketCategoryRoute.backup_user_id == user.id,
                TicketCategoryRoute.escalation_user_id == user.id,
            )
        )
    ).all():
        categories.add(row[0])
    for row in db.execute(
        select(TicketRoutingRule.category).where(
            TicketRoutingRule.is_active.is_(True),
            or_(
                TicketRoutingRule.primary_user_id == user.id,
                TicketRoutingRule.backup_user_id == user.id,
                TicketRoutingRule.escalation_user_id == user.id,
            ),
        )
    ).all():
        categories.add(row[0])
    return categories


# --- Access ---------------------------------------------------------------
def can_manage_all_tickets(db: Session, user: User) -> bool:
    if is_admin(db, user):
        return True
    return get_role_name(db, user) in EXECUTIVE_ROLES


def manageable_categories(db: Session, user: User) -> set[str]:
    """Queues this user works: responder role groups, configured owners, IT managers."""
    if can_manage_all_tickets(db, user):
        return set(CATEGORY_LABELS.keys())
    role_name = get_role_name(db, user)
    categories = {
        category
        for category, roles in CATEGORY_RESPONDER_ROLES.items()
        if role_name in roles
    }
    categories |= _configured_owner_categories(db, user)
    from app.core.access_control import (
        SPECIAL_MANAGE_IT_ASSETS,
        SPECIAL_MANAGE_IT_REQUESTS,
        user_has_special,
    )

    if user_has_special(user, role_name, SPECIAL_MANAGE_IT_REQUESTS) or user_has_special(
        user, role_name, SPECIAL_MANAGE_IT_ASSETS
    ):
        categories.add("it")
    return categories


def is_ticket_agent(db: Session, user: User) -> bool:
    return bool(manageable_categories(db, user))


def can_manage_ticket(db: Session, user: User, ticket: Ticket) -> bool:
    if can_manage_all_tickets(db, user):
        return True
    if ticket.assignee_id == user.id:
        return True
    return ticket.category in manageable_categories(db, user)


def can_view_ticket(db: Session, user: User, ticket: Ticket) -> bool:
    if ticket.requester_id == user.id:
        return True
    return can_manage_ticket(db, user, ticket)


def can_view_internal(db: Session, user: User, ticket: Ticket) -> bool:
    """Internal notes are visible to the people who work the ticket only."""
    return can_manage_ticket(db, user, ticket)


# --- Ticket number --------------------------------------------------------
TICKET_PREFIX = "TKT-"


def next_ticket_number(db: Session) -> str:
    """Next number after the highest existing ``TKT-nnnnnn``.

    Collisions under concurrency are resolved by the unique constraint plus the
    retry loop in :func:`ticket_workflow_service.create_ticket`.
    """
    highest = 0
    for number in db.scalars(
        select(Ticket.ticket_number)
        .where(Ticket.ticket_number.like(f"{TICKET_PREFIX}%"))
        .order_by(Ticket.ticket_number.desc())
        .limit(20)
    ).all():
        tail = number[len(TICKET_PREFIX):]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return f"{TICKET_PREFIX}{highest + 1:06d}"


def default_department_id_for_category(db: Session, category: str) -> UUID | None:
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
    return sorted(CATEGORY_RESPONDER_ROLES.get(category, frozenset()))


# --- Lifecycle timestamps -------------------------------------------------
def apply_status_timestamps(ticket: Ticket, new_status: str) -> None:
    """Maintain resolved_at / closed_at / started_at as the status moves."""
    now = _now()
    if new_status == RESOLVED and ticket.resolved_at is None:
        ticket.resolved_at = now
    if new_status == CLOSED and ticket.closed_at is None:
        ticket.closed_at = now
        if ticket.resolved_at is None:
            ticket.resolved_at = now
    if new_status == IN_PROGRESS and ticket.started_at is None:
        ticket.started_at = now
    if new_status in OPEN_STATUSES:
        ticket.resolved_at = None
        ticket.closed_at = None
    ticket.status = new_status
    ticket.last_activity_at = now


# --- Queries --------------------------------------------------------------
def build_visible_tickets_query(db: Session, user: User):
    stmt = select(Ticket).options(
        selectinload(Ticket.requester),
        selectinload(Ticket.assignee),
        selectinload(Ticket.affected_user),
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
    counts_by_status = {
        str(status): int(count)
        for status, count in db.execute(
            select(base.c.status, func.count()).group_by(base.c.status)
        ).all()
    }
    total = sum(counts_by_status.values())
    assigned_to_me = int(
        db.scalar(
            select(func.count())
            .select_from(base)
            .where(base.c.assignee_id == user.id, base.c.status.in_(OPEN_STATUSES))
        )
        or 0
    )
    raised_by_me = int(
        db.scalar(
            select(func.count()).select_from(base).where(base.c.requester_id == user.id)
        )
        or 0
    )
    pending = sum(counts_by_status.get(s, 0) for s in PENDING_STATUSES)
    return {
        "total": total,
        "new": counts_by_status.get(NEW, 0),
        "open": counts_by_status.get(OPEN, 0),
        "in_progress": counts_by_status.get(IN_PROGRESS, 0),
        "pending": pending,
        "on_hold": pending,
        "resolved": counts_by_status.get(RESOLVED, 0),
        "closed": counts_by_status.get(CLOSED, 0),
        "cancelled": counts_by_status.get(CANCELLED, 0),
        "active": sum(counts_by_status.get(s, 0) for s in OPEN_STATUSES),
        "assigned_to_me": assigned_to_me,
        "raised_by_me": raised_by_me,
    }
