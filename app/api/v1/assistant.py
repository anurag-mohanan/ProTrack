"""Engineering management assistant API. Conversations are private to their owner."""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.permissions import is_admin
from app.models.assistant import REC_STATUSES, AIConversation, AIMessage, AIRecommendation, AIToolExecution
from app.models.models import Project, User
from app.services.assistant import recommendations as rec_service
from app.services.assistant.context import build_context
from app.services.assistant.orchestrator import run_turn
from app.services.assistant.provider import provider_status
from app.services.assistant.registry import available_modules
from app.services.assistant.suggestions import available_suggestions, find_suggestion

router = APIRouter(prefix="/assistant", tags=["assistant"], dependencies=[Depends(get_current_user)])

DEFAULT_TITLE = "New conversation"

_rate_lock = threading.Lock()
_recent_calls: dict[UUID, deque] = defaultdict(deque)


def reset_rate_limits() -> None:
    with _rate_lock:
        _recent_calls.clear()


def _check_rate(user: User) -> None:
    from app.core import config

    now = time.monotonic()
    with _rate_lock:
        calls = _recent_calls[user.id]
        while calls and now - calls[0] > 60:
            calls.popleft()
        if len(calls) >= config.AI_RATE_LIMIT_PER_MINUTE:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Too many assistant questions in the last minute. Wait a moment and try again.")
        calls.append(now)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    suggestion_id: str | None = Field(default=None, max_length=60)


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"] | None = None
    comment: str | None = Field(default=None, max_length=2000)


class RecommendationDecision(BaseModel):
    status: Literal["accepted", "rejected", "deferred", "completed"]
    note: str | None = Field(default=None, max_length=2000)
    feedback: str | None = Field(default=None, max_length=2000)


def _loads(raw: str | None, default):
    return json.loads(raw) if raw else default


def _own_conversation(db: Session, user: User, conversation_id: UUID) -> AIConversation:
    row = db.get(AIConversation, conversation_id)
    if row is None or row.owner_id != user.id or row.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return row


def _conversation_read(row: AIConversation, message_count: int | None = None) -> dict:
    return {"id": row.id, "title": row.title, "module": row.module, "project_id": row.project_id,
            "created_at": row.created_at, "last_message_at": row.last_message_at, "message_count": message_count}


def _message_read(row: AIMessage, recs: list[AIRecommendation]) -> dict:
    return {
        "id": row.id, "role": row.role, "content": row.content, "status": row.status, "error_code": row.error_code,
        "sources": _loads(row.sources_json, []), "tables": _loads(row.tables_json, []),
        "limitations": _loads(row.limitations_json, []), "follow_ups": _loads(row.follow_ups_json, []),
        "tool_calls": _loads(row.tool_calls_json, []), "provider": row.provider, "model": row.model,
        "feedback": row.feedback, "feedback_comment": row.feedback_comment, "created_at": row.created_at,
        "recommendations": [{"id": r.id, "title": r.title, "status": r.status, "priority": r.priority} for r in recs],
    }


def _recs_by_message(db: Session, message_ids: list[UUID]) -> dict[UUID, list[AIRecommendation]]:
    out: dict[UUID, list[AIRecommendation]] = defaultdict(list)
    if message_ids:
        for rec in db.scalars(select(AIRecommendation).where(AIRecommendation.message_id.in_(message_ids))).all():
            out[rec.message_id].append(rec)
    return out


@router.get("/status")
def assistant_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.core import config

    ctx = build_context(db, current_user)
    modules = available_modules(ctx)
    return {
        **provider_status(),
        "capabilities": {m: m in modules for m in ("projects", "resources", "finance", "management")},
        "limits": {"max_input_chars": config.AI_MAX_INPUT_CHARS, "questions_per_minute": config.AI_RATE_LIMIT_PER_MINUTE},
        "streaming": False,
    }


@router.get("/suggestions")
def suggestions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ctx = build_context(db, current_user)
    return [{"id": s.id, "category": s.category, "text": s.text} for s in available_suggestions(ctx)]


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    counts = dict(db.execute(
        select(AIMessage.conversation_id, func.count(AIMessage.id)).join(AIConversation)
        .where(AIConversation.owner_id == current_user.id).group_by(AIMessage.conversation_id)
    ).all())
    rows = db.scalars(
        select(AIConversation)
        .where(AIConversation.owner_id == current_user.id, AIConversation.is_deleted.is_(False))
        .order_by(func.coalesce(AIConversation.last_message_at, AIConversation.created_at).desc())
        .limit(200)
    ).all()
    return [_conversation_read(r, counts.get(r.id, 0)) for r in rows]


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    row = AIConversation(owner_id=current_user.id, title=(payload.title or "").strip() or DEFAULT_TITLE)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _conversation_read(row, 0)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    row = _own_conversation(db, current_user, conversation_id)
    messages = db.scalars(
        select(AIMessage).where(AIMessage.conversation_id == row.id).order_by(AIMessage.created_at, AIMessage.role.desc())
    ).all()
    recs = _recs_by_message(db, [m.id for m in messages])
    return {**_conversation_read(row, len(messages)), "messages": [_message_read(m, recs.get(m.id, [])) for m in messages]}


@router.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: UUID, payload: ConversationUpdate, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    row = _own_conversation(db, current_user, conversation_id)
    row.title = payload.title.strip()
    db.commit()
    db.refresh(row)
    return _conversation_read(row)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: UUID, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """Hidden from the owner. Messages, recommendations and the access audit are retained."""
    row = _own_conversation(db, current_user, conversation_id)
    row.is_deleted, row.deleted_at = True, datetime.utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: UUID, payload: MessageCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    from app.core import config

    conversation = _own_conversation(db, current_user, conversation_id)
    text = payload.content.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a question.")
    if len(text) > config.AI_MAX_INPUT_CHARS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Questions are limited to {config.AI_MAX_INPUT_CHARS} characters.")
    _check_rate(current_user)
    suggestion = find_suggestion(payload.suggestion_id)
    if conversation.title == DEFAULT_TITLE:
        conversation.title = text[:80]
    if suggestion is not None and conversation.module is None:
        conversation.module = suggestion.category.lower()
    answer = run_turn(db, current_user, conversation, text, suggestion=suggestion)
    recs = _recs_by_message(db, [answer.id])
    return _message_read(answer, recs.get(answer.id, []))


@router.post("/messages/{message_id}/feedback")
def message_feedback(message_id: UUID, payload: FeedbackRequest, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    message = db.get(AIMessage, message_id)
    if message is None or message.role != "assistant":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    _own_conversation(db, current_user, message.conversation_id)
    message.feedback = payload.rating
    message.feedback_comment = payload.comment
    message.feedback_at = datetime.utcnow()
    db.commit()
    return {"id": message.id, "feedback": message.feedback, "feedback_comment": message.feedback_comment}


def _rec_read(row: AIRecommendation, names: dict[UUID, str], projects: dict[UUID, str]) -> dict:
    return {
        "id": row.id, "title": row.title, "description": row.description, "module": row.module,
        "category": row.category, "priority": row.priority, "status": row.status,
        "project_id": row.project_id, "project_label": projects.get(row.project_id) if row.project_id else None,
        "evidence": _loads(row.evidence_json, []), "suggested_action": row.suggested_action,
        "suggested_owner": names.get(row.suggested_owner_id) if row.suggested_owner_id else None,
        "conversation_id": row.conversation_id, "created_at": row.created_at,
        "created_by": names.get(row.created_by_id), "decided_by": names.get(row.decided_by_id) if row.decided_by_id else None,
        "decided_at": row.decided_at, "completed_by": names.get(row.completed_by_id) if row.completed_by_id else None,
        "completed_at": row.completed_at, "resolution_notes": row.resolution_notes, "feedback": row.feedback,
        "workflow_route": rec_service.workflow_route(row),
        "allowed_transitions": sorted(rec_service.TRANSITIONS.get(row.status, set())),
    }


def _rec_lookups(db: Session, rows: list[AIRecommendation]) -> tuple[dict, dict]:
    user_ids = {i for r in rows for i in (r.created_by_id, r.decided_by_id, r.completed_by_id, r.suggested_owner_id) if i}
    names = {u.id: (f"{u.first_name} {u.last_name}".strip() or u.email)
             for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    project_ids = {r.project_id for r in rows if r.project_id}
    projects = {p.id: (p.code or p.tool_number) for p in db.scalars(select(Project).where(Project.id.in_(project_ids))).all()} if project_ids else {}
    return names, projects


@router.get("/recommendations")
def list_recommendations(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if status_filter is not None and status_filter not in REC_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown status")
    stmt = rec_service.visible_stmt(db, current_user)
    if status_filter:
        stmt = stmt.where(AIRecommendation.status == status_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AIRecommendation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    names, projects = _rec_lookups(db, list(rows))
    return {"items": [_rec_read(r, names, projects) for r in rows], "total": int(total), "page": page, "page_size": page_size}


@router.patch("/recommendations/{rec_id}")
def decide_recommendation(rec_id: UUID, payload: RecommendationDecision, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    try:
        row = rec_service.get_visible(db, current_user, rec_id)
        row = rec_service.decide(db, current_user, row, status=payload.status, note=payload.note, feedback=payload.feedback)
    except rec_service.RecommendationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    names, projects = _rec_lookups(db, [row])
    return _rec_read(row, names, projects)


@router.get("/audit/tool-executions")
def tool_execution_audit(
    tool_name: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    user_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Administrators see which data each user's assistant retrieved (metadata only, never contents)."""
    if not is_admin(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The assistant access audit is restricted to administrators.")
    stmt = select(AIToolExecution)
    if tool_name:
        stmt = stmt.where(AIToolExecution.tool_name == tool_name)
    if status_filter:
        stmt = stmt.where(AIToolExecution.status == status_filter)
    if user_id:
        stmt = stmt.where(AIToolExecution.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AIToolExecution.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    user_ids = {r.user_id for r in rows}
    names = {u.id: (f"{u.first_name} {u.last_name}".strip() or u.email)
             for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    return {
        "items": [{"id": r.id, "time": r.created_at, "user": names.get(r.user_id), "tool": r.tool_name, "status": r.status,
                   "arguments": _loads(r.arguments_json, None), "record_count": r.record_count,
                   "duration_ms": r.duration_ms, "detail": r.detail} for r in rows],
        "total": int(total), "page": page, "page_size": page_size,
    }
