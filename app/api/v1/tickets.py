"""Help-desk / ticketing API.

Any user with the Tickets module may raise a ticket and track their own.
Agents (Admin, executives, IT / HR / Office-Administrator roles) work the
queues they own. Management actions (assign, status change, edit) are gated by
:func:`ticketing_service.can_manage_ticket`.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth_deps import get_current_user, require_module_action, require_roles
from app.api.deps import get_db
from app.core.access_control import MODULE_TICKETS
from app.core.module_actions import MODULE_ACTION_VIEW
from app.models.enums import ActivityAction, EntityType
from app.models.models import Ticket, TicketCategoryRoute, TicketComment, User
from app.schemas.ticket import (
    TicketAssignRequest,
    TicketCategoryRouteRead,
    TicketCategoryRouteUpdate,
    TicketCommentCreate,
    TicketCommentRead,
    TicketCreate,
    TicketDetailRead,
    TicketRead,
    TicketStats,
    TicketStatusRequest,
    TicketUpdate,
)
from app.services import ticketing_service as tickets
from app.services.activity_service import log_activity

router = APIRouter(
    prefix="/tickets",
    tags=["tickets"],
    dependencies=[Depends(require_module_action(MODULE_TICKETS, MODULE_ACTION_VIEW))],
)

MODULE = "tickets"


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip()


def _comment_read(comment: TicketComment) -> TicketCommentRead:
    return TicketCommentRead(
        id=comment.id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        ticket_id=comment.ticket_id,
        author_id=comment.author_id,
        author_name=_full_name(comment.author),
        body=comment.body,
        is_internal=comment.is_internal,
    )


def _to_read(
    db: Session,
    ticket: Ticket,
    current_user: User,
    *,
    comment_count: int | None = None,
) -> TicketRead:
    if comment_count is None:
        comment_count = len(ticket.comments)
    return TicketRead(
        id=ticket.id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        category=ticket.category,
        category_label=tickets.CATEGORY_LABELS.get(ticket.category, ticket.category),
        priority=ticket.priority,
        status=ticket.status,
        status_label=tickets.STATUS_LABELS.get(ticket.status, ticket.status),
        requester_id=ticket.requester_id,
        requester_name=_full_name(ticket.requester),
        assignee_id=ticket.assignee_id,
        assignee_name=_full_name(ticket.assignee),
        org_department_id=ticket.org_department_id,
        location=ticket.location,
        due_date=ticket.due_date,
        resolution=ticket.resolution,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        comment_count=comment_count,
        can_manage=tickets.can_manage_ticket(db, current_user, ticket),
    )


def _get_ticket_or_404(db: Session, ticket_id: UUID) -> Ticket:
    ticket = db.scalar(
        select(Ticket)
        .options(
            selectinload(Ticket.requester),
            selectinload(Ticket.assignee),
            selectinload(Ticket.comments).selectinload(TicketComment.author),
        )
        .where(Ticket.id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return ticket


@router.get("/stats", response_model=TicketStats)
def ticket_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TicketStats(**tickets.compute_stats(db, current_user))


admin_only = Depends(require_roles("Admin"))


def _route_read(db: Session, category: str, route: TicketCategoryRoute | None) -> TicketCategoryRouteRead:
    assignee_name = None
    assignee_id = None
    org_department_id = None
    if route is not None:
        assignee_id = route.assignee_user_id
        org_department_id = route.org_department_id
        if route.assignee is not None:
            assignee_name = _full_name(route.assignee)
    return TicketCategoryRouteRead(
        category=category,
        category_label=tickets.CATEGORY_LABELS.get(category, category),
        assignee_user_id=assignee_id,
        assignee_name=assignee_name,
        org_department_id=org_department_id,
        fallback_roles=tickets.fallback_role_names(category),
    )


@router.get("/routes", response_model=list[TicketCategoryRouteRead], dependencies=[admin_only])
def list_category_routes(db: Session = Depends(get_db)):
    """List the configured contact per ticket category (Admin)."""
    existing = tickets.category_route_map(db)
    return [
        _route_read(db, category, existing.get(category))
        for category in tickets.CATEGORY_LABELS
    ]


@router.put(
    "/routes/{category}",
    response_model=TicketCategoryRouteRead,
    dependencies=[admin_only],
)
def set_category_route(
    category: str,
    payload: TicketCategoryRouteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set (or clear) the default contact / department for a category (Admin)."""
    if category not in tickets.CATEGORY_LABELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown ticket category."
        )
    if payload.assignee_user_id is not None:
        assignee = db.get(User, payload.assignee_user_id)
        if assignee is None or assignee.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found."
            )

    route = db.scalar(
        select(TicketCategoryRoute).where(TicketCategoryRoute.category == category)
    )
    if route is None:
        route = TicketCategoryRoute(category=category)
        db.add(route)
    route.assignee_user_id = payload.assignee_user_id
    route.org_department_id = payload.org_department_id
    db.flush()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.ticket,
        entity_id=route.id,
        action=ActivityAction.ticket_updated,
        new_value={
            "category": category,
            "assignee_user_id": str(payload.assignee_user_id) if payload.assignee_user_id else None,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(route)
    return _route_read(db, category, route)


@router.get("", response_model=list[TicketRead])
def list_tickets(
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    scope: str | None = Query(default=None, description="mine | assigned | queue"),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = tickets.build_visible_tickets_query(db, current_user)
    if status_filter and status_filter != "all":
        stmt = stmt.where(Ticket.status == status_filter)
    if category and category != "all":
        stmt = stmt.where(Ticket.category == category)
    if priority and priority != "all":
        stmt = stmt.where(Ticket.priority == priority)
    if scope == "mine":
        stmt = stmt.where(Ticket.requester_id == current_user.id)
    elif scope == "assigned":
        stmt = stmt.where(Ticket.assignee_id == current_user.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (Ticket.title.ilike(like)) | (Ticket.ticket_number.ilike(like))
        )
    stmt = stmt.order_by(Ticket.created_at.desc())
    rows = db.scalars(stmt).all()
    return [_to_read(db, ticket, current_user, comment_count=0) for ticket in rows]


@router.get("/{ticket_id}", response_model=TicketDetailRead)
def get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    if not tickets.can_view_ticket(db, current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")
    base = _to_read(db, ticket, current_user, comment_count=len(ticket.comments))
    is_agent = tickets.can_manage_ticket(db, current_user, ticket)
    comments = [
        _comment_read(comment)
        for comment in ticket.comments
        if is_agent or not comment.is_internal
    ]
    return TicketDetailRead(**base.model_dump(), comments=comments)


@router.post("", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Auto-assign to the admin-configured contact for this category, if any.
    contact_id = tickets.category_contact_id(db, payload.category)
    ticket = Ticket(
        ticket_number=tickets.next_ticket_number(db),
        title=payload.title.strip(),
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        status="open",
        requester_id=current_user.id,
        assignee_id=contact_id,
        location=payload.location,
        due_date=payload.due_date,
        org_department_id=(
            payload.org_department_id
            or tickets.default_department_id_for_category(db, payload.category)
        ),
    )
    db.add(ticket)
    db.flush()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.ticket,
        entity_id=ticket.id,
        action=ActivityAction.ticket_created,
        new_value={"ticket": ticket.ticket_number, "category": ticket.category},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    ticket = _get_ticket_or_404(db, ticket.id)
    base = _to_read(db, ticket, current_user, comment_count=0)
    return TicketDetailRead(**base.model_dump(), comments=[])


@router.patch("/{ticket_id}", response_model=TicketDetailRead)
def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    data = payload.model_dump(exclude_unset=True)

    is_manager = tickets.can_manage_ticket(db, current_user, ticket)
    is_requester = ticket.requester_id == current_user.id

    # Requesters may edit only the descriptive fields of their own ticket while
    # it is still open; everything else (status, assignee, priority, category,
    # resolution) requires agent rights.
    requester_editable = {"title", "description", "location", "due_date"}
    if not is_manager:
        if not is_requester:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")
        illegal = set(data.keys()) - requester_editable
        if illegal:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an agent can change status, priority, category, or assignment.",
            )
        if ticket.status not in tickets.OPEN_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This ticket is closed and can no longer be edited.",
            )

    status_changed = "status" in data and data["status"] != ticket.status
    old_status = ticket.status

    for field, value in data.items():
        if field == "status":
            continue
        setattr(ticket, field, value)
    if status_changed:
        tickets.apply_status_timestamps(ticket, data["status"])

    db.flush()
    if status_changed:
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.ticket,
            entity_id=ticket.id,
            action=ActivityAction.ticket_status_changed,
            old_value={"status": old_status},
            new_value={"status": ticket.status},
            outcome="success",
            module=MODULE,
            commit=False,
        )
    else:
        log_activity(
            db,
            user=current_user,
            entity_type=EntityType.ticket,
            entity_id=ticket.id,
            action=ActivityAction.ticket_updated,
            new_value={"fields": sorted(data.keys())},
            outcome="success",
            module=MODULE,
            commit=False,
        )
    db.commit()
    ticket = _get_ticket_or_404(db, ticket.id)
    return get_ticket(ticket.id, db=db, current_user=current_user)


@router.post("/{ticket_id}/assign", response_model=TicketDetailRead)
def assign_ticket(
    ticket_id: UUID,
    payload: TicketAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    if not tickets.can_manage_ticket(db, current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")

    if payload.assignee_id is not None:
        assignee = db.get(User, payload.assignee_id)
        if assignee is None or assignee.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found.")

    ticket.assignee_id = payload.assignee_id
    # Picking up an unassigned open ticket moves it into progress.
    if payload.assignee_id is not None and ticket.status == "open":
        tickets.apply_status_timestamps(ticket, "in_progress")
    db.flush()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.ticket,
        entity_id=ticket.id,
        action=ActivityAction.ticket_assigned,
        new_value={"assignee_id": str(payload.assignee_id) if payload.assignee_id else None},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    return get_ticket(ticket_id, db=db, current_user=current_user)


@router.post("/{ticket_id}/status", response_model=TicketDetailRead)
def change_status(
    ticket_id: UUID,
    payload: TicketStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    is_manager = tickets.can_manage_ticket(db, current_user, ticket)
    is_requester = ticket.requester_id == current_user.id

    # Requesters may cancel their own open ticket or reopen a resolved one.
    if not is_manager:
        allowed_for_requester = (
            (payload.status == "cancelled" and ticket.status in tickets.OPEN_STATUSES)
            or (payload.status == "open" and ticket.status == "resolved")
        )
        if not (is_requester and allowed_for_requester):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")

    old_status = ticket.status
    if payload.resolution is not None:
        ticket.resolution = payload.resolution
    tickets.apply_status_timestamps(ticket, payload.status)
    db.flush()
    action = ActivityAction.ticket_status_changed
    if payload.status == "resolved":
        action = ActivityAction.ticket_resolved
    elif payload.status == "closed":
        action = ActivityAction.ticket_closed
    elif payload.status == "open" and old_status in tickets.TERMINAL_STATUSES:
        action = ActivityAction.ticket_reopened
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.ticket,
        entity_id=ticket.id,
        action=action,
        old_value={"status": old_status},
        new_value={"status": ticket.status},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    return get_ticket(ticket_id, db=db, current_user=current_user)


@router.post(
    "/{ticket_id}/comments",
    response_model=TicketCommentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    ticket_id: UUID,
    payload: TicketCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    if not tickets.can_view_ticket(db, current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")

    is_manager = tickets.can_manage_ticket(db, current_user, ticket)
    # Only agents can post internal (private) notes.
    is_internal = bool(payload.is_internal) and is_manager

    comment = TicketComment(
        ticket_id=ticket.id,
        author_id=current_user.id,
        body=payload.body.strip(),
        is_internal=is_internal,
    )
    db.add(comment)
    db.flush()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.ticket,
        entity_id=ticket.id,
        action=ActivityAction.ticket_commented,
        new_value={"internal": is_internal},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(comment)
    comment.author = current_user
    return _comment_read(comment)
