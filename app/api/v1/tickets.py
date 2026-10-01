"""Help-desk / ticketing API — the one ticket store for every module.

Any user with the Tickets module may raise a ticket and track their own. Queue
owners and agents work the queues they manage; every write goes through
:mod:`app.services.ticket_workflow_service`, which enforces the lifecycle,
records the audit trail and notifies. Authorization is checked here on every
endpoint (hidden buttons are never the only guard).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.api.auth_deps import get_current_user, require_module_action, require_roles
from app.api.deps import get_db
from app.core.access_control import MODULE_TICKETS
from app.core.exceptions import ProTrackValidationError
from app.core.module_actions import MODULE_ACTION_VIEW
from app.core.permissions import is_admin
from app.models.enums import ActivityAction, EntityType
from app.models.models import (
    Activity,
    OnboardingChecklistItem,
    Role,
    Ticket,
    TicketAssignmentHistory,
    TicketCategoryRoute,
    TicketComment,
    TicketNotificationLog,
    TicketRoutingRule,
    TicketSlaPolicy,
    User,
)
from app.schemas.ticket import (
    EmployeeTicketRow,
    TicketAssignee,
    TicketAssignmentRead,
    TicketAssignRequest,
    TicketCapabilities,
    TicketCatalog,
    TicketCategoryRouteRead,
    TicketCategoryRouteUpdate,
    TicketCommentCreate,
    TicketCommentRead,
    TicketCreate,
    TicketDetailRead,
    TicketLinkedTask,
    TicketNotificationRead,
    TicketPage,
    TicketQueueSummary,
    TicketRead,
    TicketReconciliation,
    TicketRelatedRecord,
    TicketReport,
    TicketReviewRequest,
    TicketRoutingRuleRead,
    TicketRoutingRuleWrite,
    TicketSlaPolicyRead,
    TicketSlaPolicyWrite,
    TicketStats,
    TicketStatusRequest,
    TicketTimelineEvent,
    TicketTransferRequest,
    TicketUpdate,
)
from app.services import onboarding_task_service as onboarding_tasks
from app.services import ticket_workflow_service as workflow
from app.services import ticketing_service as tickets
from app.services.activity_service import log_activity

router = APIRouter(
    prefix="/tickets",
    tags=["tickets"],
    dependencies=[Depends(require_module_action(MODULE_TICKETS, MODULE_ACTION_VIEW))],
)

MODULE = "tickets"
admin_only = Depends(require_roles("Admin"))


def _full_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip()


def _raise(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


class _Viewer:
    """Permission facts for the current user, computed once per request."""

    def __init__(self, db: Session, user: User) -> None:
        self.user = user
        self.all = tickets.can_manage_all_tickets(db, user)
        self.categories = tickets.manageable_categories(db, user)
        self.is_admin = is_admin(db, user)

    def can_manage(self, ticket: Ticket) -> bool:
        return self.all or ticket.assignee_id == self.user.id or ticket.category in self.categories

    def can_view(self, ticket: Ticket) -> bool:
        return ticket.requester_id == self.user.id or self.can_manage(ticket)

    def transitions(self, ticket: Ticket) -> list[str]:
        if self.can_manage(ticket):
            return workflow.allowed_transitions(ticket)
        if ticket.requester_id == self.user.id:
            return workflow.requester_transitions(ticket)
        return []


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


def _to_read(ticket: Ticket, viewer: _Viewer, *, comment_count: int = 0) -> TicketRead:
    return TicketRead(
        id=ticket.id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        category=ticket.category,
        category_label=tickets.CATEGORY_LABELS.get(ticket.category, ticket.category),
        subcategory=ticket.subcategory,
        subcategory_label=tickets.subcategory_label(ticket.category, ticket.subcategory),
        family=tickets.subcategory_family(ticket.subcategory),
        priority=ticket.priority,
        priority_label=tickets.PRIORITY_LABELS.get(ticket.priority, ticket.priority),
        status=ticket.status,
        status_label=tickets.STATUS_LABELS.get(ticket.status, ticket.status),
        requester_id=ticket.requester_id,
        requester_name=_full_name(ticket.requester),
        assignee_id=ticket.assignee_id,
        assignee_name=_full_name(ticket.assignee),
        affected_user_id=ticket.affected_user_id,
        affected_user_name=_full_name(ticket.affected_user),
        org_department_id=ticket.org_department_id,
        location=ticket.location,
        due_date=ticket.due_date,
        sla_due_at=ticket.sla_due_at,
        is_overdue=tickets.is_overdue(ticket),
        resolution=ticket.resolution,
        work_performed=ticket.work_performed,
        resolution_category=ticket.resolution_category,
        closure_reason=ticket.closure_reason,
        cancellation_reason=ticket.cancellation_reason,
        pending_reason=ticket.pending_reason,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        assigned_at=ticket.assigned_at,
        started_at=ticket.started_at,
        first_response_at=ticket.first_response_at,
        last_activity_at=ticket.last_activity_at,
        source_module=ticket.source_module,
        source_label=tickets.SOURCE_LABELS.get(ticket.source_module or "", ticket.source_module),
        source_record_id=ticket.source_record_id,
        onboarding_item_id=ticket.onboarding_item_id,
        related_asset_id=ticket.related_asset_id,
        related_license_pool_id=ticket.related_license_pool_id,
        related_stock_item_id=ticket.related_stock_item_id,
        assignment_group=ticket.assignment_group,
        needs_owner=bool(ticket.needs_owner),
        needs_review=bool(ticket.needs_review),
        review_note=ticket.review_note,
        escalation_level=int(ticket.escalation_level or 0),
        comment_count=comment_count,
        can_manage=viewer.can_manage(ticket),
        allowed_transitions=viewer.transitions(ticket),
    )


def _get_ticket_or_404(db: Session, ticket_id: UUID) -> Ticket:
    ticket = db.scalar(
        select(Ticket)
        .options(
            selectinload(Ticket.requester),
            selectinload(Ticket.assignee),
            selectinload(Ticket.affected_user),
            selectinload(Ticket.comments).selectinload(TicketComment.author),
        )
        .where(Ticket.id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return ticket


def _visible_or_403(db: Session, ticket_id: UUID, viewer: _Viewer) -> Ticket:
    ticket = _get_ticket_or_404(db, ticket_id)
    if not viewer.can_view(ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")
    return ticket


def _manageable_or_403(db: Session, ticket_id: UUID, viewer: _Viewer) -> Ticket:
    ticket = _visible_or_403(db, ticket_id, viewer)
    if not viewer.can_manage(ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted.")
    return ticket


# --- Catalogue / capabilities -------------------------------------------------


@router.get("/catalog", response_model=TicketCatalog)
def ticket_catalog():
    return TicketCatalog(
        categories=tickets.CATEGORY_LABELS,
        subcategories=tickets.SUBCATEGORY_LABELS,
        families=tickets.FAMILY_LABELS,
        statuses={k: v for k, v in tickets.STATUS_LABELS.items()},
        status_order=list(tickets.STATUS_ORDER),
        priorities={p: tickets.PRIORITY_LABELS[p] for p in tickets.PRIORITIES},
        sources=tickets.SOURCE_LABELS,
        closure_reasons=workflow.CLOSURE_REASONS,
        resolution_categories=workflow.RESOLUTION_CATEGORIES,
        transitions={k: sorted(v) for k, v in workflow.TRANSITIONS.items()},
    )


@router.get("/me", response_model=TicketCapabilities)
def ticket_capabilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    return TicketCapabilities(
        is_agent=bool(viewer.categories),
        can_manage_all=viewer.all,
        can_configure=viewer.is_admin,
        manageable_categories=sorted(viewer.categories),
    )


@router.get("/assignees", response_model=list[TicketAssignee])
def list_assignees(
    category: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Active people who can work the given queue (agents only)."""
    viewer = _Viewer(db, current_user)
    if category not in viewer.categories:
        raise HTTPException(status_code=403, detail="Not permitted.")
    rows = db.execute(
        select(User, Role.name)
        .join(Role, Role.id == User.role_id)
        .where(User.is_active.is_(True), User.is_deleted.is_(False))
        .order_by(User.first_name, User.last_name)
    ).all()
    result: list[TicketAssignee] = []
    for user, role_name in rows:
        if category in tickets.manageable_categories(db, user):
            result.append(TicketAssignee(id=user.id, name=_full_name(user) or user.email, role_name=role_name))
    return result


@router.get("/stats", response_model=TicketStats)
def ticket_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TicketStats(**tickets.compute_stats(db, current_user))


# --- Routing configuration (Admin) -------------------------------------------


def _route_read(category: str, route: TicketCategoryRoute | None) -> TicketCategoryRouteRead:
    return TicketCategoryRouteRead(
        category=category,
        category_label=tickets.CATEGORY_LABELS.get(category, category),
        assignee_user_id=route.assignee_user_id if route else None,
        assignee_name=_full_name(route.assignee) if route else None,
        backup_user_id=route.backup_user_id if route else None,
        backup_name=_full_name(route.backup) if route else None,
        escalation_user_id=route.escalation_user_id if route else None,
        escalation_name=_full_name(route.escalation) if route else None,
        org_department_id=route.org_department_id if route else None,
        is_active=route.is_active if route else True,
        effective_from=route.effective_from if route else None,
        fallback_roles=tickets.fallback_role_names(category),
    )


def _require_active_users(db: Session, *user_ids: UUID | None) -> None:
    for user_id in user_ids:
        if user_id is None:
            continue
        user = db.get(User, user_id)
        if user is None or user.is_deleted or not user.is_active:
            raise HTTPException(status_code=404, detail="Selected person not found or inactive.")


@router.get("/routes", response_model=list[TicketCategoryRouteRead], dependencies=[admin_only])
def list_category_routes(db: Session = Depends(get_db)):
    existing = tickets.category_route_map(db)
    return [_route_read(category, existing.get(category)) for category in tickets.CATEGORY_LABELS]


@router.put("/routes/{category}", response_model=TicketCategoryRouteRead, dependencies=[admin_only])
def set_category_route(
    category: str,
    payload: TicketCategoryRouteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if category not in tickets.CATEGORY_LABELS:
        raise HTTPException(status_code=404, detail="Unknown ticket category.")
    _require_active_users(db, payload.assignee_user_id, payload.backup_user_id, payload.escalation_user_id)
    route = db.scalar(select(TicketCategoryRoute).where(TicketCategoryRoute.category == category))
    old = None
    if route is None:
        route = TicketCategoryRoute(category=category)
        db.add(route)
    else:
        old = {
            "assignee_user_id": str(route.assignee_user_id) if route.assignee_user_id else None,
            "backup_user_id": str(route.backup_user_id) if route.backup_user_id else None,
            "escalation_user_id": str(route.escalation_user_id) if route.escalation_user_id else None,
            "is_active": route.is_active,
        }
    route.assignee_user_id = payload.assignee_user_id
    route.backup_user_id = payload.backup_user_id
    route.escalation_user_id = payload.escalation_user_id
    route.org_department_id = payload.org_department_id
    route.is_active = payload.is_active
    route.effective_from = payload.effective_from
    db.flush()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.ticket,
        entity_id=route.id,
        action=ActivityAction.ticket_routing_changed,
        old_value=old,
        new_value={
            "category": category,
            "assignee_user_id": str(payload.assignee_user_id) if payload.assignee_user_id else None,
            "backup_user_id": str(payload.backup_user_id) if payload.backup_user_id else None,
            "escalation_user_id": str(payload.escalation_user_id) if payload.escalation_user_id else None,
            "is_active": payload.is_active,
        },
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(route)
    return _route_read(category, route)


def _rule_read(rule: TicketRoutingRule) -> TicketRoutingRuleRead:
    return TicketRoutingRuleRead(
        id=rule.id,
        category=rule.category,  # type: ignore[arg-type]
        subcategory=rule.subcategory,
        source_module=rule.source_module,
        primary_user_id=rule.primary_user_id,
        backup_user_id=rule.backup_user_id,
        escalation_user_id=rule.escalation_user_id,
        default_priority=rule.default_priority,  # type: ignore[arg-type]
        is_active=rule.is_active,
        effective_from=rule.effective_from,
        notes=rule.notes,
        primary_name=_full_name(rule.primary),
        backup_name=_full_name(rule.backup),
        escalation_name=_full_name(rule.escalation),
    )


@router.get("/routing-rules", response_model=list[TicketRoutingRuleRead], dependencies=[admin_only])
def list_routing_rules(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(TicketRoutingRule).order_by(TicketRoutingRule.category, TicketRoutingRule.subcategory)
    ).all()
    return [_rule_read(rule) for rule in rows]


def _save_rule(
    db: Session, rule: TicketRoutingRule, payload: TicketRoutingRuleWrite, actor: User, created: bool
) -> TicketRoutingRuleRead:
    _require_active_users(db, payload.primary_user_id, payload.backup_user_id, payload.escalation_user_id)
    if payload.subcategory and payload.subcategory not in tickets.SUBCATEGORY_LABELS.get(payload.category, {}):
        raise HTTPException(status_code=422, detail="Unknown subcategory for this category.")
    for field, value in payload.model_dump().items():
        if field == "default_priority" and value is not None:
            value = tickets.normalize_priority(value)
        setattr(rule, field, value)
    db.add(rule)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.ticket,
        entity_id=rule.id,
        action=ActivityAction.ticket_routing_changed,
        new_value={"rule": str(rule.id), "created": created, **json.loads(payload.model_dump_json())},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(rule)
    return _rule_read(rule)


@router.post("/routing-rules", response_model=TicketRoutingRuleRead, status_code=201, dependencies=[admin_only])
def create_routing_rule(
    payload: TicketRoutingRuleWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _save_rule(db, TicketRoutingRule(), payload, current_user, True)


@router.put("/routing-rules/{rule_id}", response_model=TicketRoutingRuleRead, dependencies=[admin_only])
def update_routing_rule(
    rule_id: UUID,
    payload: TicketRoutingRuleWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = db.get(TicketRoutingRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Routing rule not found.")
    return _save_rule(db, rule, payload, current_user, False)


@router.get("/sla-policies", response_model=list[TicketSlaPolicyRead], dependencies=[admin_only])
def list_sla_policies(db: Session = Depends(get_db)):
    workflow.ensure_default_sla_policies(db)
    db.commit()
    rows = db.scalars(select(TicketSlaPolicy).order_by(TicketSlaPolicy.category, TicketSlaPolicy.priority)).all()
    return [TicketSlaPolicyRead.model_validate(row, from_attributes=True) for row in rows]


@router.put("/sla-policies", response_model=TicketSlaPolicyRead, dependencies=[admin_only])
def upsert_sla_policy(
    payload: TicketSlaPolicyWrite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.category != "*" and payload.category not in tickets.CATEGORY_LABELS:
        raise HTTPException(status_code=422, detail="Unknown category.")
    row = db.scalar(
        select(TicketSlaPolicy).where(
            TicketSlaPolicy.category == payload.category,
            TicketSlaPolicy.priority == payload.priority,
        )
    )
    old = None
    if row is None:
        row = TicketSlaPolicy()
    else:
        old = TicketSlaPolicyWrite.model_validate(row, from_attributes=True).model_dump()
    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    db.add(row)
    db.flush()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.ticket,
        entity_id=row.id,
        action=ActivityAction.ticket_routing_changed,
        old_value=old,
        new_value={"sla_policy": payload.model_dump()},
        outcome="success",
        module=MODULE,
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return TicketSlaPolicyRead.model_validate(row, from_attributes=True)


@router.post("/sla/run", response_model=dict)
def run_sla_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send due-soon / overdue / escalation alerts now (each alert is sent once)."""
    viewer = _Viewer(db, current_user)
    if not viewer.categories:
        raise HTTPException(status_code=403, detail="Not permitted.")
    counts = workflow.run_sla_sweep(db)
    db.commit()
    return counts


# --- Queue / list -------------------------------------------------------------

_SORTS = {
    "updated": (Ticket.updated_at.desc(),),
    "created": (Ticket.created_at.desc(),),
    "due": (Ticket.due_date.is_(None), Ticket.due_date.asc(), Ticket.sla_due_at.asc()),
}


def _apply_filters(
    db: Session,
    stmt,
    viewer: _Viewer,
    *,
    view: str | None,
    status_filter: str | None,
    category: str | None,
    subcategory: str | None,
    family: str | None,
    priority: str | None,
    assignee: str | None,
    requester_id: UUID | None,
    affected_user_id: UUID | None,
    source_module: str | None,
    due: str | None,
    created_from: date | None,
    created_to: date | None,
    q: str | None,
):
    now = datetime.utcnow()
    today = now.date()
    overdue_clause = or_(Ticket.due_date < today, Ticket.sla_due_at < now)
    user_id = viewer.user.id
    open_statuses = list(tickets.OPEN_STATUSES)

    if view == "mine":
        stmt = stmt.where(Ticket.assignee_id == user_id, Ticket.status.in_(open_statuses))
    elif view == "raised":
        stmt = stmt.where(Ticket.requester_id == user_id)
    elif view == "team":
        stmt = stmt.where(Ticket.status.in_(open_statuses))
    elif view == "unassigned":
        stmt = stmt.where(Ticket.assignee_id.is_(None), Ticket.status.in_(open_statuses))
    elif view in {"onboarding", "hardware", "software", "asset", "offboarding"}:
        subs = tickets.family_subcategories(view)
        condition = Ticket.subcategory.in_(subs)
        if view == "onboarding":
            condition = or_(condition, Ticket.source_module.in_(["onboarding", "it_provisioning"]))
        stmt = stmt.where(condition, Ticket.status.in_(open_statuses))
    elif view == "overdue":
        stmt = stmt.where(Ticket.status.in_(open_statuses), overdue_clause)
    elif view == "high":
        stmt = stmt.where(Ticket.status.in_(open_statuses), Ticket.priority.in_(list(tickets.HIGH_PRIORITIES)))
    elif view == "due_today":
        stmt = stmt.where(Ticket.status.in_(open_statuses), Ticket.due_date == today)
    elif view == "recently_resolved":
        stmt = stmt.where(
            Ticket.status == tickets.RESOLVED,
            Ticket.resolved_at >= now - timedelta(days=14),
        )
    elif view == "closed":
        stmt = stmt.where(Ticket.status.in_([tickets.CLOSED, tickets.CANCELLED]))
    elif view == "needs_review":
        stmt = stmt.where(Ticket.needs_review.is_(True))

    if status_filter == "active":
        stmt = stmt.where(Ticket.status.in_(open_statuses))
    elif status_filter == "waiting":
        stmt = stmt.where(Ticket.status.in_(list(tickets.PENDING_STATUSES)))
    elif status_filter and status_filter != "all":
        values = [s.strip() for s in status_filter.split(",") if s.strip()]
        if tickets.PENDING_INTERNAL in values:
            values.append(tickets.LEGACY_ON_HOLD)
        stmt = stmt.where(Ticket.status.in_(values))
    if category and category != "all":
        stmt = stmt.where(Ticket.category == category)
    if subcategory:
        stmt = stmt.where(Ticket.subcategory == subcategory)
    if family:
        stmt = stmt.where(Ticket.subcategory.in_(tickets.family_subcategories(family)))
    if priority and priority != "all":
        stmt = stmt.where(Ticket.priority.in_(tickets.priority_filter_values(priority)))
    if assignee == "me":
        stmt = stmt.where(Ticket.assignee_id == user_id)
    elif assignee == "none":
        stmt = stmt.where(Ticket.assignee_id.is_(None))
    elif assignee:
        try:
            stmt = stmt.where(Ticket.assignee_id == UUID(assignee))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid assignee filter.") from exc
    if requester_id:
        stmt = stmt.where(Ticket.requester_id == requester_id)
    if affected_user_id:
        stmt = stmt.where(Ticket.affected_user_id == affected_user_id)
    if source_module:
        stmt = stmt.where(Ticket.source_module == source_module)
    if due == "overdue":
        stmt = stmt.where(Ticket.status.in_(open_statuses), overdue_clause)
    elif due == "today":
        stmt = stmt.where(Ticket.due_date == today)
    elif due == "week":
        stmt = stmt.where(Ticket.due_date >= today, Ticket.due_date <= today + timedelta(days=7))
    if created_from:
        stmt = stmt.where(Ticket.created_at >= datetime.combine(created_from, datetime.min.time()))
    if created_to:
        stmt = stmt.where(Ticket.created_at < datetime.combine(created_to + timedelta(days=1), datetime.min.time()))
    if q and q.strip():
        from app.models.it_operations import Asset

        like = f"%{q.strip()}%"
        requester = aliased(User)
        affected = aliased(User)
        stmt = (
            stmt.outerjoin(requester, requester.id == Ticket.requester_id)
            .outerjoin(affected, affected.id == Ticket.affected_user_id)
            .outerjoin(Asset, Asset.id == Ticket.related_asset_id)
            .where(
                or_(
                    Ticket.ticket_number.ilike(like),
                    Ticket.title.ilike(like),
                    Ticket.description.ilike(like),
                    Ticket.source_record_id.ilike(like),
                    (requester.first_name + " " + requester.last_name).ilike(like),
                    requester.email.ilike(like),
                    (affected.first_name + " " + affected.last_name).ilike(like),
                    affected.email.ilike(like),
                    Asset.asset_number.ilike(like),
                )
            )
        )
    return stmt


def _filters(
    view: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    subcategory: str | None = Query(default=None),
    family: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    assignee: str | None = Query(default=None, description="me | none | <user id>"),
    requester_id: UUID | None = Query(default=None),
    affected_user_id: UUID | None = Query(default=None),
    source_module: str | None = Query(default=None),
    due: str | None = Query(default=None, description="overdue | today | week"),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    q: str | None = Query(default=None),
) -> dict[str, Any]:
    return {
        "view": view,
        "status_filter": status_filter,
        "category": category,
        "subcategory": subcategory,
        "family": family,
        "priority": priority,
        "assignee": assignee,
        "requester_id": requester_id,
        "affected_user_id": affected_user_id,
        "source_module": source_module,
        "due": due,
        "created_from": created_from,
        "created_to": created_to,
        "q": q,
    }


def _sorted(stmt, sort: str | None):
    if sort == "priority":
        from sqlalchemy import case

        rank = case(
            (Ticket.priority == "urgent", 0),
            (Ticket.priority == "high", 1),
            (Ticket.priority.in_(["normal", "medium"]), 2),
            else_=3,
        )
        return stmt.order_by(rank, Ticket.created_at.desc())
    return stmt.order_by(*_SORTS.get(sort or "", (Ticket.created_at.desc(),)))


@router.get("", response_model=list[TicketRead])
def list_tickets(
    scope: str | None = Query(default=None, description="mine | assigned"),
    sort: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    filters: dict[str, Any] = Depends(_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    stmt = tickets.build_visible_tickets_query(db, current_user)
    if scope == "mine":
        stmt = stmt.where(Ticket.requester_id == current_user.id)
    elif scope == "assigned":
        stmt = stmt.where(Ticket.assignee_id == current_user.id)
    stmt = _apply_filters(db, stmt, viewer, **filters)
    rows = db.scalars(_sorted(stmt, sort).limit(limit)).unique().all()
    return [_to_read(ticket, viewer) for ticket in rows]


@router.get("/queue", response_model=TicketPage)
def ticket_queue(
    sort: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    filters: dict[str, Any] = Depends(_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Paginated work queue with saved views and filters (server-side)."""
    viewer = _Viewer(db, current_user)
    stmt = _apply_filters(db, tickets.build_visible_tickets_query(db, current_user), viewer, **filters)
    total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
    rows = db.scalars(
        _sorted(stmt, sort).offset((page - 1) * page_size).limit(page_size)
    ).unique().all()
    return TicketPage(
        items=[_to_read(ticket, viewer) for ticket in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/queue/summary", response_model=TicketQueueSummary)
def queue_summary(
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Counts for the work-queue cards; each card maps to a ``view`` of /queue."""
    viewer = _Viewer(db, current_user)
    base = tickets.build_visible_tickets_query(db, current_user)
    if category and category != "all":
        base = base.where(Ticket.category == category)
    base_sub = base.order_by(None).subquery()
    rows = db.execute(
        select(
            base_sub.c.status,
            base_sub.c.priority,
            base_sub.c.assignee_id,
            base_sub.c.subcategory,
            base_sub.c.source_module,
            base_sub.c.due_date,
            base_sub.c.sla_due_at,
            base_sub.c.resolved_at,
        )
    ).all()
    now = datetime.utcnow()
    today = now.date()
    open_statuses = tickets.OPEN_STATUSES
    counts = {
        key: 0
        for key in (
            "new",
            "open",
            "in_progress",
            "waiting",
            "resolved",
            "closed",
            "overdue",
            "unassigned",
            "high",
            "due_today",
            "onboarding",
            "hardware",
            "software",
            "asset",
            "offboarding",
            "mine",
            "active",
            "recently_resolved",
        )
    }
    for status_value, priority, assignee_id, subcategory, source, due_date, sla_due_at, resolved_at in rows:
        if status_value == tickets.NEW:
            counts["new"] += 1
        elif status_value == tickets.OPEN:
            counts["open"] += 1
        elif status_value == tickets.IN_PROGRESS:
            counts["in_progress"] += 1
        elif status_value in tickets.PENDING_STATUSES:
            counts["waiting"] += 1
        elif status_value == tickets.RESOLVED:
            counts["resolved"] += 1
            if resolved_at is not None and resolved_at >= now - timedelta(days=14):
                counts["recently_resolved"] += 1
        elif status_value in {tickets.CLOSED, tickets.CANCELLED}:
            counts["closed"] += 1
        if status_value not in open_statuses:
            continue
        counts["active"] += 1
        if assignee_id is None:
            counts["unassigned"] += 1
        if assignee_id == current_user.id:
            counts["mine"] += 1
        if priority in tickets.HIGH_PRIORITIES:
            counts["high"] += 1
        if due_date == today:
            counts["due_today"] += 1
        if (due_date is not None and due_date < today) or (sla_due_at is not None and sla_due_at < now):
            counts["overdue"] += 1
        family = tickets.subcategory_family(subcategory)
        if family in counts:
            counts[family] += 1
        if family != "onboarding" and source in {"onboarding", "it_provisioning"}:
            counts["onboarding"] += 1
    return TicketQueueSummary(category=category, counts=counts)


@router.get("/export.csv")
def export_tickets(
    sort: str | None = Query(default=None),
    filters: dict[str, Any] = Depends(_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    if not viewer.categories:
        raise HTTPException(status_code=403, detail="Not permitted.")
    stmt = _apply_filters(db, tickets.build_visible_tickets_query(db, current_user), viewer, **filters)
    rows = db.scalars(_sorted(stmt, sort).limit(10000)).unique().all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Ticket", "Title", "Category", "Subcategory", "Priority", "Status", "Requester",
            "Affected employee", "Assignee", "Source", "Created", "Due", "Overdue",
            "Resolved", "Closed", "Resolution", "Closure reason",
        ]
    )
    for t in rows:
        writer.writerow(
            [
                t.ticket_number,
                t.title,
                tickets.CATEGORY_LABELS.get(t.category, t.category),
                tickets.subcategory_label(t.category, t.subcategory) or "",
                tickets.PRIORITY_LABELS.get(t.priority, t.priority),
                tickets.STATUS_LABELS.get(t.status, t.status),
                _full_name(t.requester) or "",
                _full_name(t.affected_user) or "",
                _full_name(t.assignee) or "Unassigned",
                tickets.SOURCE_LABELS.get(t.source_module or "", t.source_module or ""),
                t.created_at.isoformat() if t.created_at else "",
                t.due_date.isoformat() if t.due_date else "",
                "yes" if tickets.is_overdue(t) else "",
                t.resolved_at.isoformat() if t.resolved_at else "",
                t.closed_at.isoformat() if t.closed_at else "",
                t.resolution or "",
                workflow.CLOSURE_REASONS.get(t.closure_reason or "", t.closure_reason or ""),
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tickets.csv"'},
    )


# --- Reports / reconciliation -------------------------------------------------


@router.get("/reports/summary", response_model=TicketReport)
def ticket_report(
    category: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    if not viewer.categories:
        raise HTTPException(status_code=403, detail="Not permitted.")
    stmt = tickets.build_visible_tickets_query(db, current_user)
    if category and category != "all":
        stmt = stmt.where(Ticket.category == category)
    if date_from:
        stmt = stmt.where(Ticket.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Ticket.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    rows = db.scalars(stmt).unique().all()
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_family: dict[str, int] = {}
    by_subcategory: dict[str, int] = {}
    by_source: dict[str, int] = {}
    assignees: dict[str, dict[str, Any]] = {}
    resolution_hours: list[float] = []
    response_hours: list[float] = []
    breached = overdue = 0
    for t in rows:
        status_label = tickets.STATUS_LABELS.get(t.status, t.status)
        by_status[status_label] = by_status.get(status_label, 0) + 1
        priority_label = tickets.PRIORITY_LABELS.get(t.priority, t.priority)
        by_priority[priority_label] = by_priority.get(priority_label, 0) + 1
        family = tickets.FAMILY_LABELS.get(tickets.subcategory_family(t.subcategory) or "", "Unclassified")
        by_family[family] = by_family.get(family, 0) + 1
        sub = tickets.subcategory_label(t.category, t.subcategory) or "Unclassified"
        by_subcategory[sub] = by_subcategory.get(sub, 0) + 1
        source = tickets.SOURCE_LABELS.get(t.source_module or "", "Unrecorded (legacy)")
        by_source[source] = by_source.get(source, 0) + 1
        key = str(t.assignee_id) if t.assignee_id else "unassigned"
        bucket = assignees.setdefault(
            key,
            {"assignee": _full_name(t.assignee) or "Unassigned", "open": 0, "resolved": 0, "overdue": 0},
        )
        if t.status in tickets.OPEN_STATUSES:
            bucket["open"] += 1
        elif t.status in tickets.DONE_STATUSES:
            bucket["resolved"] += 1
        if tickets.is_overdue(t):
            bucket["overdue"] += 1
            overdue += 1
        if t.resolved_at and t.created_at:
            resolution_hours.append((t.resolved_at - t.created_at).total_seconds() / 3600)
            if t.sla_due_at and t.resolved_at > t.sla_due_at:
                breached += 1
        if t.first_response_at and t.created_at:
            response_hours.append((t.first_response_at - t.created_at).total_seconds() / 3600)
    totals = {
        "tickets": len(rows),
        "open": sum(1 for t in rows if t.status in tickets.OPEN_STATUSES),
        "overdue": overdue,
        "sla_breached": breached,
        "avg_resolution_hours": round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None,
        "avg_first_response_hours": round(sum(response_hours) / len(response_hours), 1) if response_hours else None,
        "needs_owner": sum(1 for t in rows if t.status in tickets.OPEN_STATUSES and t.assignee_id is None),
        "needs_review": sum(1 for t in rows if t.needs_review),
    }
    return TicketReport(
        filters={"category": category, "date_from": date_from, "date_to": date_to},
        totals=totals,
        by_status=by_status,
        by_priority=by_priority,
        by_family=by_family,
        by_subcategory=by_subcategory,
        by_source=by_source,
        by_assignee=sorted(assignees.values(), key=lambda row: (-row["open"], row["assignee"])),
    )


@router.get("/reconciliation", response_model=TicketReconciliation)
def ticket_reconciliation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records needing attention: legacy shared tickets, ownerless tickets,
    ticket-required tasks without a ticket, broken links, and tasks whose
    ticket finished while the task did not."""
    viewer = _Viewer(db, current_user)
    if not viewer.categories:
        raise HTTPException(status_code=403, detail="Not permitted.")
    rows: list[dict[str, Any]] = []
    visible = tickets.build_visible_tickets_query(db, current_user)
    for t in db.scalars(visible.where(Ticket.needs_review.is_(True))).unique().all():
        rows.append({"kind": "legacy_grouped", "ticket_id": str(t.id), "ticket_number": t.ticket_number,
                     "title": t.title, "status": t.status, "note": t.review_note})
    for t in db.scalars(
        visible.where(Ticket.assignee_id.is_(None), Ticket.status.in_(list(tickets.OPEN_STATUSES)))
    ).unique().all():
        rows.append({"kind": "needs_owner", "ticket_id": str(t.id), "ticket_number": t.ticket_number,
                     "title": t.title, "status": t.status, "note": "No active owner."})
    from app.services import onboarding_checklist_service as onboard

    for checklist in onboard.load_checklists(db, status="in_progress"):
        for item in checklist.items:
            if item.responsibility and item.responsibility != "it" and "it" not in viewer.categories and not viewer.all:
                continue
            codes = set(onboarding_tasks.attention_codes(item)) & {
                "request_missing", "link_broken", "request_resolved", "request_cancelled", "legacy_grouped"
            }
            for code in sorted(codes):
                rows.append({
                    "kind": f"task_{code}",
                    "checklist_id": str(checklist.id),
                    "item_id": str(item.id),
                    "employee_name": checklist.employee_name,
                    "title": item.item_text,
                    "status": onboarding_tasks.current_status(item),
                    "ticket_number": item.help_ticket.ticket_number if item.help_ticket else None,
                    "note": onboarding_tasks.ATTENTION_LABELS.get(code, code),
                })
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    return TicketReconciliation(counts=counts, rows=rows)


# --- Employee profile ------------------------------------------------------------


@router.get("/employee/{user_id}", response_model=list[EmployeeTicketRow])
def employee_tickets(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tickets raised by or about an employee. Agents and the employee get full
    rows; HR and the reporting manager see status-level rows only (no notes)."""
    from app.services import onboarding_checklist_service as onboard

    viewer = _Viewer(db, current_user)
    employee = db.get(User, user_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    hr_view = onboard.can_manage_onboarding(db, current_user) or employee.manager_id == current_user.id
    if current_user.id != user_id and not hr_view and not viewer.categories:
        raise HTTPException(status_code=403, detail="Not permitted.")
    rows = db.scalars(
        select(Ticket)
        .options(selectinload(Ticket.assignee))
        .where(or_(Ticket.affected_user_id == user_id, Ticket.requester_id == user_id))
        .order_by(Ticket.created_at.desc())
        .limit(200)
    ).all()
    result: list[EmployeeTicketRow] = []
    for t in rows:
        can_open = viewer.can_view(t)
        if not can_open and not hr_view and current_user.id != user_id:
            continue
        result.append(
            EmployeeTicketRow(
                id=t.id,
                ticket_number=t.ticket_number,
                title=t.title,
                category_label=tickets.CATEGORY_LABELS.get(t.category, t.category),
                status=t.status,
                status_label=tickets.STATUS_LABELS.get(t.status, t.status),
                priority_label=tickets.PRIORITY_LABELS.get(t.priority, t.priority),
                assignee_name=_full_name(t.assignee),
                due_date=t.due_date,
                is_overdue=tickets.is_overdue(t),
                updated_at=t.updated_at,
                relation="affected" if t.affected_user_id == user_id else "requester",
                can_open=can_open,
            )
        )
    return result


# --- Single ticket ---------------------------------------------------------------


def _timeline(db: Session, ticket: Ticket, *, include_internal: bool) -> list[TicketTimelineEvent]:
    events: list[TicketTimelineEvent] = []
    activity_rows = db.execute(
        select(Activity, User.first_name, User.last_name)
        .outerjoin(User, User.id == Activity.user_id)
        .where(Activity.entity_type == EntityType.ticket, Activity.entity_id == ticket.id)
        .order_by(Activity.created_at.asc())
    ).all()

    def parse(raw: Any) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    for activity, first, last in activity_rows:
        if activity.action == ActivityAction.ticket_commented:
            continue
        new = parse(activity.new_value)
        old = parse(activity.old_value)
        actor = f"{first or ''} {last or ''}".strip() or ("System" if activity.user_id is None else None)
        action = activity.action.value if hasattr(activity.action, "value") else str(activity.action)
        label = tickets.STATUS_LABELS
        if action == "ticket_created":
            summary = f"Created via {tickets.SOURCE_LABELS.get(new.get('source_module') or '', 'Help Desk')}"
            detail = None if new.get("assignee_id") else "No owner configured — placed in the queue."
        elif action in {"ticket_status_changed", "ticket_resolved", "ticket_closed", "ticket_cancelled", "ticket_reopened"}:
            summary = f"{label.get(old.get('status') or '', old.get('status') or '—')} → {label.get(new.get('status') or '', new.get('status') or '—')}"
            detail = new.get("reason") or (new.get("resolution") if new.get("status") == "resolved" else None)
        elif action in {"ticket_assigned", "ticket_transferred"}:
            summary = "Transferred" if action == "ticket_transferred" else "Assignment changed"
            detail = new.get("reason")
        elif action == "ticket_escalated":
            summary = "Escalated (overdue)"
            detail = None
        elif action == "ticket_updated":
            summary = "Updated " + ", ".join(sorted(k for k in new if k != "ticket"))
            detail = None
        elif action == "ticket_reviewed":
            summary = "Marked reviewed"
            detail = new.get("note")
        else:
            summary = action.replace("_", " ").capitalize()
            detail = None
        events.append(TicketTimelineEvent(at=activity.created_at, kind=action, actor_name=actor, summary=summary, detail=detail))
    for comment in ticket.comments:
        if comment.is_internal and not include_internal:
            continue
        events.append(
            TicketTimelineEvent(
                at=comment.created_at,
                kind="comment",
                actor_name=_full_name(comment.author),
                summary="Internal note" if comment.is_internal else "Comment",
                detail=comment.body,
                is_internal=comment.is_internal,
            )
        )
    events.sort(key=lambda e: e.at or datetime.min)
    return events


def _related_records(db: Session, ticket: Ticket) -> list[TicketRelatedRecord]:
    from app.models.it_operations import (
        Asset,
        InventoryItem,
        ItProvisioningRequest,
        SoftwareCatalog,
        SoftwareLicensePool,
    )

    records: list[TicketRelatedRecord] = []
    if ticket.affected_user_id and ticket.affected_user is not None:
        records.append(TicketRelatedRecord(kind="employee", id=str(ticket.affected_user_id),
                                           label=_full_name(ticket.affected_user) or "Employee",
                                           href=f"/users/{ticket.affected_user_id}"))
    if ticket.related_asset_id:
        asset = db.get(Asset, ticket.related_asset_id)
        if asset is not None:
            records.append(TicketRelatedRecord(kind="asset", id=str(asset.id), label=asset.asset_number,
                                               href=f"/it/assets?asset={asset.id}"))
    if ticket.related_license_pool_id:
        pool = db.get(SoftwareLicensePool, ticket.related_license_pool_id)
        if pool is not None:
            software = db.get(SoftwareCatalog, pool.software_id)
            records.append(TicketRelatedRecord(kind="license", id=str(pool.id),
                                               label=software.name if software else "License pool",
                                               href="/it/software?tab=licenses"))
    if ticket.related_stock_item_id:
        item = db.get(InventoryItem, ticket.related_stock_item_id)
        if item is not None:
            records.append(TicketRelatedRecord(kind="stock_item", id=str(item.id), label=item.name,
                                               href="/it/inventory?view=low-stock"))
    request = db.scalar(select(ItProvisioningRequest).where(ItProvisioningRequest.ticket_id == ticket.id))
    if request is not None:
        records.append(TicketRelatedRecord(kind="provisioning_request", id=str(request.id),
                                           label=f"IT provisioning ({request.status})",
                                           href=f"/it/requests?tab=provisioning&request={request.id}"))
    return records


def _detail(db: Session, ticket: Ticket, viewer: _Viewer) -> TicketDetailRead:
    from app.models.it_operations import ItProvisioningRequest

    can_manage = viewer.can_manage(ticket)
    base = _to_read(ticket, viewer, comment_count=len(ticket.comments))
    comments = [_comment_read(c) for c in ticket.comments if can_manage or not c.is_internal]
    history_rows = db.scalars(
        select(TicketAssignmentHistory)
        .options(
            selectinload(TicketAssignmentHistory.previous_assignee),
            selectinload(TicketAssignmentHistory.new_assignee),
            selectinload(TicketAssignmentHistory.changed_by),
        )
        .where(TicketAssignmentHistory.ticket_id == ticket.id)
        .order_by(TicketAssignmentHistory.created_at.asc())
    ).all()
    linked = db.scalars(
        select(OnboardingChecklistItem).where(
            or_(
                OnboardingChecklistItem.help_ticket_id == ticket.id,
                OnboardingChecklistItem.id == ticket.onboarding_item_id,
            )
        )
    ).all()
    notifications: list[TicketNotificationRead] = []
    if can_manage:
        for row, first, last in db.execute(
            select(TicketNotificationLog, User.first_name, User.last_name)
            .join(User, User.id == TicketNotificationLog.user_id)
            .where(TicketNotificationLog.ticket_id == ticket.id)
            .order_by(TicketNotificationLog.created_at.asc())
        ).all():
            notifications.append(TicketNotificationRead(
                at=row.created_at, event_key=row.event_key.split(":")[0],
                user_name=f"{first} {last}".strip(), status=row.status, error=row.error, attempts=row.attempts,
            ))
    request_id = db.scalar(select(ItProvisioningRequest.id).where(ItProvisioningRequest.ticket_id == ticket.id))
    return TicketDetailRead(
        **base.model_dump(),
        comments=comments,
        timeline=_timeline(db, ticket, include_internal=can_manage),
        assignment_history=[
            TicketAssignmentRead(
                at=row.created_at,
                previous_assignee_name=_full_name(row.previous_assignee),
                new_assignee_name=_full_name(row.new_assignee),
                previous_group=row.previous_group,
                new_group=row.new_group,
                changed_by_name=_full_name(row.changed_by),
                change_type=row.change_type,
                reason=row.reason,
            )
            for row in history_rows
        ],
        linked_tasks=[
            TicketLinkedTask(
                checklist_id=item.checklist_id,
                item_id=item.id,
                employee_name=item.checklist.employee_name if item.checklist else None,
                item_text=item.item_text,
                status=onboarding_tasks.current_status(item),
                status_label=onboarding_tasks.STATUS_LABELS.get(
                    onboarding_tasks.current_status(item), item.status
                ),
                execution_type=onboarding_tasks.execution_type(item),
            )
            for item in linked
        ],
        related_records=_related_records(db, ticket),
        notifications=notifications,
        can_comment_internal=can_manage,
        provisioning_request_id=request_id,
    )


def _reload(db: Session, ticket_id: UUID, viewer: _Viewer) -> TicketDetailRead:
    db.expire_all()
    return _detail(db, _get_ticket_or_404(db, ticket_id), viewer)


@router.get("/{ticket_id}", response_model=TicketDetailRead)
def get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    return _detail(db, _visible_or_403(db, ticket_id, viewer), viewer)


@router.post("", response_model=TicketDetailRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    if payload.subcategory and payload.subcategory not in tickets.SUBCATEGORY_LABELS.get(payload.category, {}):
        raise HTTPException(status_code=422, detail="Unknown subcategory for this category.")
    is_agent = payload.category in viewer.categories
    try:
        ticket, _created = workflow.create_ticket(
            db,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            subcategory=payload.subcategory,
            priority=payload.priority,
            requester=current_user,
            actor=current_user,
            source_module="help_desk",
            affected_user_id=payload.affected_user_id if is_agent else None,
            related_asset_id=payload.related_asset_id,
            related_license_pool_id=payload.related_license_pool_id,
            due_date=payload.due_date,
            location=payload.location,
            org_department_id=payload.org_department_id,
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _raise(exc) from exc
    db.commit()
    return _reload(db, ticket.id, viewer)


@router.patch("/{ticket_id}", response_model=TicketDetailRead)
def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    ticket = _visible_or_403(db, ticket_id, viewer)
    data = payload.model_dump(exclude_unset=True)
    is_manager = viewer.can_manage(ticket)
    is_requester = ticket.requester_id == current_user.id
    requester_editable = {"title", "description", "location", "due_date"}
    if not is_manager:
        if not is_requester:
            raise HTTPException(status_code=403, detail="Not permitted.")
        if set(data) - requester_editable:
            raise HTTPException(
                status_code=403,
                detail="Only an agent can change status, priority, category, or assignment.",
            )
        if ticket.status not in tickets.OPEN_STATUSES:
            raise HTTPException(status_code=422, detail="This ticket is closed and can no longer be edited.")
    try:
        if "assignee_id" in data:
            workflow.assign(db, ticket, assignee_id=data.pop("assignee_id"), actor=current_user, reason=data.get("reason"))
        new_status = data.pop("status", None)
        resolution = data.pop("resolution", None)
        work = data.pop("work_performed", None)
        reason = data.pop("reason", None)
        workflow.update_fields(db, ticket, actor=current_user, data=data)
        if new_status and new_status != ticket.status:
            workflow.transition(
                db, ticket, to_status=new_status, actor=current_user,
                resolution=resolution, work_performed=work, reason=reason,
            )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _raise(exc) from exc
    db.commit()
    return _reload(db, ticket_id, viewer)


@router.post("/{ticket_id}/assign", response_model=TicketDetailRead)
def assign_ticket(
    ticket_id: UUID,
    payload: TicketAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    ticket = _manageable_or_403(db, ticket_id, viewer)
    if payload.assignee_id is not None:
        assignee = db.get(User, payload.assignee_id)
        if assignee is None or assignee.is_deleted:
            raise HTTPException(status_code=404, detail="Assignee not found.")
    try:
        workflow.assign(
            db, ticket, assignee_id=payload.assignee_id, actor=current_user, reason=payload.reason,
            change_type="take" if payload.assignee_id == current_user.id else "assign",
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _raise(exc) from exc
    db.commit()
    return _reload(db, ticket_id, viewer)


@router.post("/{ticket_id}/take", response_model=TicketDetailRead)
def take_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Take ownership and start work."""
    viewer = _Viewer(db, current_user)
    ticket = _manageable_or_403(db, ticket_id, viewer)
    try:
        workflow.assign(db, ticket, assignee_id=current_user.id, actor=current_user, change_type="take")
        if ticket.status in {tickets.NEW, tickets.OPEN}:
            workflow.transition(db, ticket, to_status=tickets.IN_PROGRESS, actor=current_user)
    except ProTrackValidationError as exc:
        db.rollback()
        raise _raise(exc) from exc
    db.commit()
    return _reload(db, ticket_id, viewer)


@router.post("/{ticket_id}/transfer", response_model=TicketDetailRead)
def transfer_ticket(
    ticket_id: UUID,
    payload: TicketTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    ticket = _manageable_or_403(db, ticket_id, viewer)
    if payload.subcategory and payload.subcategory not in tickets.SUBCATEGORY_LABELS.get(payload.category, {}):
        raise HTTPException(status_code=422, detail="Unknown subcategory for this category.")
    try:
        workflow.transfer(
            db, ticket, category=payload.category, subcategory=payload.subcategory,
            actor=current_user, reason=payload.reason, assignee_id=payload.assignee_id,
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _raise(exc) from exc
    db.commit()
    ticket = _get_ticket_or_404(db, ticket_id)
    if not viewer.can_view(ticket):
        base = _to_read(ticket, viewer)
        return TicketDetailRead(**base.model_dump())
    return _reload(db, ticket_id, viewer)


@router.post("/{ticket_id}/status", response_model=TicketDetailRead)
def change_status(
    ticket_id: UUID,
    payload: TicketStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    ticket = _visible_or_403(db, ticket_id, viewer)
    if payload.status not in viewer.transitions(ticket) and not viewer.can_manage(ticket):
        raise HTTPException(status_code=403, detail="Not permitted.")
    closure = payload.closure_reason
    if (
        payload.status == tickets.CLOSED
        and not viewer.can_manage(ticket)
        and ticket.requester_id == current_user.id
    ):
        closure = "confirmed_by_requester"
    try:
        workflow.transition(
            db,
            ticket,
            to_status=payload.status,
            actor=current_user,
            resolution=payload.resolution,
            work_performed=payload.work_performed,
            resolution_category=payload.resolution_category,
            closure_reason=closure,
            reason=payload.reason,
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _raise(exc) from exc
    db.commit()
    return _reload(db, ticket_id, viewer)


@router.post("/{ticket_id}/review", response_model=TicketDetailRead)
def review_ticket(
    ticket_id: UUID,
    payload: TicketReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear the legacy-review flag after a person has checked the record."""
    viewer = _Viewer(db, current_user)
    ticket = _manageable_or_403(db, ticket_id, viewer)
    if not ticket.needs_review:
        raise HTTPException(status_code=422, detail="This ticket is not flagged for review.")
    old_note = ticket.review_note
    ticket.needs_review = False
    ticket.review_note = f"{old_note or ''}\nReviewed: {payload.note.strip()}".strip()
    db.flush()
    log_activity(
        db, user=current_user, entity_type=EntityType.ticket, entity_id=ticket.id,
        action=ActivityAction.ticket_reviewed, old_value={"needs_review": True, "note": old_note},
        new_value={"ticket": ticket.ticket_number, "note": payload.note.strip()},
        outcome="success", module=MODULE, commit=False,
    )
    db.commit()
    return _reload(db, ticket_id, viewer)


@router.post("/{ticket_id}/notifications/retry", response_model=dict)
def retry_notifications(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    ticket = _manageable_or_403(db, ticket_id, viewer)
    sent = workflow.retry_failed_notifications(db, ticket)
    db.commit()
    return {"sent": sent}


@router.post("/{ticket_id}/comments", response_model=TicketCommentRead, status_code=status.HTTP_201_CREATED)
def add_comment(
    ticket_id: UUID,
    payload: TicketCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    viewer = _Viewer(db, current_user)
    ticket = _visible_or_403(db, ticket_id, viewer)
    try:
        comment = workflow.add_comment(
            db, ticket, actor=current_user, body=payload.body,
            is_internal=payload.is_internal, is_agent=viewer.can_manage(ticket),
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise _raise(exc) from exc
    db.commit()
    db.refresh(comment)
    comment.author = current_user
    return _comment_read(comment)
