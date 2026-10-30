"""Workflow automation administration and the decision audit (Admin only)."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.permissions import is_admin
from app.models.enums import ActivityAction
from app.models.models import Activity, Milestone, Project, User
from app.models.workflow import (
    EXEC_FAILED,
    EXEC_PENDING_REVIEW,
    AutomationExecution,
    AutomationRule,
    ProjectTemplateReconciliation,
)
from app.services.automation import engine
from app.services.automation.rules import describe


def _require_admin(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not is_admin(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Automation and decision audit are restricted to administrators.")
    return current_user


router = APIRouter(prefix="/automation", tags=["automation"], dependencies=[Depends(_require_admin)])

_DECISION_ACTIONS = (ActivityAction.milestone_lifecycle_changed, ActivityAction.automation_rule_changed)


class RuleToggle(BaseModel):
    is_enabled: bool
    reason: str | None = Field(default=None, max_length=500)


class SweepRequest(BaseModel):
    rule_keys: list[str] | None = None


class ReviewRequest(BaseModel):
    decision: Literal["acknowledge", "dismiss"]
    note: str | None = Field(default=None, max_length=1000)


def _names(db: Session, ids: set[UUID | None]) -> dict[UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {
        u.id: (f"{u.first_name} {u.last_name}".strip() or u.email)
        for u in db.scalars(select(User).where(User.id.in_(ids))).all()
    }


def _projects(db: Session, ids: set[UUID | None]) -> dict[UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {p.id: (p.code or p.tool_number or str(p.id)[:8]) for p in db.scalars(select(Project).where(Project.id.in_(ids))).all()}


def _execution_read(row: AutomationExecution, users: dict, projects: dict) -> dict:
    try:
        payload = json.loads(row.result_json or "{}")
    except ValueError:
        payload = {}
    definition = engine.REGISTRY.get(row.rule_key)
    return {
        "id": row.id,
        "rule_key": row.rule_key,
        "rule_name": definition.name if definition else row.rule_key,
        "trigger_event": row.trigger_event,
        "actor_type": row.actor_type,
        "actor_name": users.get(row.actor_id) if row.actor_id else None,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "project_id": row.project_id,
        "project_label": projects.get(row.project_id) if row.project_id else None,
        "status": row.status,
        "summary": row.summary,
        "result": payload.get("result"),
        "error_message": row.error_message,
        "attempts": row.attempts,
        "reviewed_by_name": users.get(row.reviewed_by_id) if row.reviewed_by_id else None,
        "reviewed_at": row.reviewed_at,
        "review_note": row.review_note,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
    }


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    rows = {r.rule_key: r for r in db.scalars(select(AutomationRule)).all()}
    counts = {
        (key, st): int(n)
        for key, st, n in db.execute(
            select(AutomationExecution.rule_key, AutomationExecution.status, func.count())
            .group_by(AutomationExecution.rule_key, AutomationExecution.status)
        ).all()
    }
    result = []
    for definition in engine.all_rules():
        row = rows.get(definition.key)
        result.append({
            **describe(definition),
            "is_enabled": bool(row and row.is_enabled),
            "last_run_at": row.last_run_at if row else None,
            "last_status": row.last_status if row else None,
            "last_error": row.last_error if row else None,
            "failed_count": counts.get((definition.key, EXEC_FAILED), 0),
            "pending_review_count": counts.get((definition.key, EXEC_PENDING_REVIEW), 0),
            "execution_count": sum(n for (k, _s), n in counts.items() if k == definition.key),
        })
    return result


@router.patch("/rules/{rule_key}")
def toggle_rule(rule_key: str, payload: RuleToggle, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        engine.set_enabled(db, rule_key, payload.is_enabled, actor=current_user, reason=payload.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown rule") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return next(r for r in list_rules(db) if r["key"] == rule_key)


@router.post("/run-sweeps")
def run_sweeps_now(payload: SweepRequest | None = None, db: Session = Depends(get_db)):
    """Evaluate the enabled sweep rules now. Deduplication makes repeated runs safe."""
    return engine.run_sweeps(db, rule_keys=payload.rule_keys if payload else None)


@router.get("/executions")
def list_executions(
    rule_key: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    project_id: UUID | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(AutomationExecution)
    if rule_key:
        stmt = stmt.where(AutomationExecution.rule_key == rule_key)
    if status_filter:
        stmt = stmt.where(AutomationExecution.status == status_filter)
    if project_id:
        stmt = stmt.where(AutomationExecution.project_id == project_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(AutomationExecution.summary.ilike(like), AutomationExecution.error_message.ilike(like),
                              AutomationExecution.dedupe_key.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(AutomationExecution.started_at.desc()).offset((page - 1) * page_size).limit(page_size)).all())
    users = _names(db, {r.actor_id for r in rows} | {r.reviewed_by_id for r in rows})
    projects = _projects(db, {r.project_id for r in rows})
    return {"items": [_execution_read(r, users, projects) for r in rows], "total": int(total), "page": page, "page_size": page_size}


def _execution_or_404(db: Session, execution_id: UUID) -> AutomationExecution:
    row = db.get(AutomationExecution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return row


@router.post("/executions/{execution_id}/retry")
def retry_execution(execution_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = _execution_or_404(db, execution_id)
    try:
        row = engine.retry(db, row, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    users = _names(db, {row.actor_id, row.reviewed_by_id})
    return _execution_read(row, users, _projects(db, {row.project_id}))


@router.post("/executions/{execution_id}/review")
def review_execution(execution_id: UUID, payload: ReviewRequest, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    row = _execution_or_404(db, execution_id)
    try:
        row = engine.review(db, row, actor=current_user, decision=payload.decision, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    users = _names(db, {row.actor_id, row.reviewed_by_id})
    return _execution_read(row, users, _projects(db, {row.project_id}))


@router.get("/decision-audit")
def decision_audit(
    search: str | None = None,
    kind: Literal["template_change", "lifecycle", "rule_change", "automation"] | None = None,
    project_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """One searchable list of consequential decisions: template reconciliations,
    milestone lifecycle changes, rule switches and automation outcomes."""
    start = datetime.combine(date_from, time.min) if date_from else None
    end = datetime.combine(date_to, time.max) if date_to else None
    like = f"%{search.strip()}%" if search else None
    window = page * page_size
    items: list[dict] = []
    total = 0

    if kind in (None, "template_change"):
        stmt = select(ProjectTemplateReconciliation)
        if project_id:
            stmt = stmt.where(ProjectTemplateReconciliation.project_id == project_id)
        if start:
            stmt = stmt.where(ProjectTemplateReconciliation.confirmed_at >= start)
        if end:
            stmt = stmt.where(ProjectTemplateReconciliation.confirmed_at <= end)
        if like:
            stmt = stmt.where(or_(ProjectTemplateReconciliation.new_template_name.ilike(like),
                                  ProjectTemplateReconciliation.previous_template_name.ilike(like),
                                  ProjectTemplateReconciliation.reason.ilike(like),
                                  ProjectTemplateReconciliation.error_message.ilike(like)))
        total += db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        for r in db.scalars(stmt.order_by(ProjectTemplateReconciliation.confirmed_at.desc()).limit(window)).all():
            items.append({
                "kind": "template_change", "id": r.id, "time": r.confirmed_at, "actor_id": r.confirmed_by_id,
                "action": "Template change applied" if r.status == "applied" else "Template change failed",
                "target": "project", "target_id": r.project_id, "project_id": r.project_id,
                "previous_value": f"{r.previous_template_name} v{r.previous_template_version}" if r.previous_template_name else None,
                "new_value": f"{r.new_template_name} v{r.new_template_version}: {r.added_count} added, {r.matched_count} matched, "
                             f"{r.merged_count} merged, {r.superseded_count} superseded, {r.archived_count} archived",
                "trigger": "Confirmed in the reconciliation preview", "reason": r.reason,
                "approval_reference": f"reconciliation:{r.id}", "result": r.status, "error": r.error_message,
            })

    if kind in (None, "lifecycle", "rule_change"):
        actions = {
            None: _DECISION_ACTIONS,
            "lifecycle": (ActivityAction.milestone_lifecycle_changed,),
            "rule_change": (ActivityAction.automation_rule_changed,),
        }[kind]
        stmt = select(Activity).where(Activity.action.in_(actions))
        if start:
            stmt = stmt.where(Activity.created_at >= start)
        if end:
            stmt = stmt.where(Activity.created_at <= end)
        if like:
            stmt = stmt.where(or_(Activity.new_value.ilike(like), Activity.old_value.ilike(like)))
        if project_id:
            stmt = stmt.where(Activity.entity_id.in_(select(Milestone.id).where(Milestone.project_id == project_id)))
        total += db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(stmt.order_by(Activity.created_at.desc()).limit(window)).all()
        owners = {
            m.id: m.project_id
            for m in db.scalars(select(Milestone).where(Milestone.id.in_({a.entity_id for a in rows}))).all()
        } if rows else {}
        for a in rows:
            lifecycle = a.action == ActivityAction.milestone_lifecycle_changed
            items.append({
                "kind": "lifecycle" if lifecycle else "rule_change", "id": a.id, "time": a.created_at, "actor_id": a.user_id,
                "action": "Milestone lifecycle changed" if lifecycle else "Automation rule switched",
                "target": "milestone" if lifecycle else "automation_rule", "target_id": a.entity_id,
                "project_id": owners.get(a.entity_id), "previous_value": a.old_value, "new_value": a.new_value,
                "trigger": "Template reconciliation" if lifecycle else "Administrator", "reason": None,
                "approval_reference": None, "result": a.outcome or "success", "error": None,
            })

    if kind in (None, "automation"):
        stmt = select(AutomationExecution)
        if project_id:
            stmt = stmt.where(AutomationExecution.project_id == project_id)
        if start:
            stmt = stmt.where(AutomationExecution.started_at >= start)
        if end:
            stmt = stmt.where(AutomationExecution.started_at <= end)
        if like:
            stmt = stmt.where(or_(AutomationExecution.summary.ilike(like), AutomationExecution.rule_key.ilike(like),
                                  AutomationExecution.error_message.ilike(like)))
        total += db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        for e in db.scalars(stmt.order_by(AutomationExecution.started_at.desc()).limit(window)).all():
            definition = engine.REGISTRY.get(e.rule_key)
            items.append({
                "kind": "automation", "id": e.id, "time": e.started_at, "actor_id": e.actor_id,
                "action": definition.name if definition else e.rule_key, "target": e.target_type, "target_id": e.target_id,
                "project_id": e.project_id, "previous_value": None, "new_value": e.summary,
                "trigger": e.trigger_event, "reason": definition.conditions if definition else None,
                "approval_reference": (f"reviewed:{e.reviewed_at.isoformat()}" if e.reviewed_at else None),
                "result": e.status, "error": e.error_message,
            })

    items.sort(key=lambda row: row["time"] or datetime.min, reverse=True)
    page_items = items[(page - 1) * page_size: page * page_size]
    users = _names(db, {i["actor_id"] for i in page_items})
    projects = _projects(db, {i["project_id"] for i in page_items})
    for item in page_items:
        item["actor_name"] = users.get(item["actor_id"]) if item["actor_id"] else ("System" if item["kind"] == "automation" else None)
        item["project_label"] = projects.get(item["project_id"]) if item["project_id"] else None
    return {"items": page_items, "total": int(total), "page": page, "page_size": page_size}
