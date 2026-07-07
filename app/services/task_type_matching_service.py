"""Centralized task type normalization and matching for imports."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Stream, TaskType

TASK_TYPE_ALIASES: dict[str, str] = {
    "design": "Design",
    "surfacing": "Surfacing",
    "drawing": "2D Drawings",
    "2d drawing": "2D Drawings",
    "2d drawings": "2D Drawings",
    "drafting": "2D Drawings",
    "sub-task": "Sub Task",
    "sub task": "Sub Task",
    "subtask": "Sub Task",
    "feasibility": "Feasibility Assessment",
    "checking": "Design Review",
    "review": "Design Review",
    "bom": "Bill of Materials",
}


def normalize_task_type_value(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().lower().replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def canonicalize_task_type_name(value: str | None) -> str | None:
    normalized = normalize_task_type_value(value)
    if not normalized:
        return None
    return TASK_TYPE_ALIASES.get(normalized, value.strip() if value else None)


def _stream_by_name(db: Session, name: str) -> Stream | None:
    return db.scalar(
        select(Stream).where(Stream.is_active.is_(True), Stream.name == name).order_by(Stream.name)
    )


def resolve_auto_create_stream_id(
    db: Session,
    *,
    explicit_stream_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    if explicit_stream_id is not None:
        stream = db.get(Stream, explicit_stream_id)
        return stream.id if stream and stream.is_active else None
    streams = list(
        db.scalars(select(Stream).where(Stream.is_active.is_(True)).order_by(Stream.name)).all()
    )
    if not streams:
        return None
    if len(streams) == 1:
        return streams[0].id
    mold_design = _stream_by_name(db, "Mold Design")
    if mold_design is not None:
        return mold_design.id
    return None


@dataclass
class TaskTypeMatchResult:
    task_type: TaskType | None
    created: bool = False
    unknown_task_name: str | None = None


def match_task_type(
    db: Session,
    *,
    excel_task_name: str | None,
    stream_id: uuid.UUID | None,
    auto_create: bool = False,
    auto_create_stream_id: uuid.UUID | None = None,
) -> TaskTypeMatchResult:
    original = (excel_task_name or "").strip()
    normalized_input = normalize_task_type_value(original)
    if not normalized_input:
        return TaskTypeMatchResult(task_type=None, unknown_task_name=original)

    canonical = canonicalize_task_type_name(original) or original
    normalized_canonical = normalize_task_type_value(canonical)

    candidates = list(
        db.scalars(select(TaskType).where(TaskType.is_active.is_(True))).all()
    )
    for candidate in candidates:
        if stream_id is not None and candidate.stream_id != stream_id:
            continue
        if normalize_task_type_value(candidate.name) in {normalized_input, normalized_canonical}:
            return TaskTypeMatchResult(task_type=candidate, created=False)

    if not auto_create:
        return TaskTypeMatchResult(task_type=None, unknown_task_name=original)

    target_stream_id = stream_id or resolve_auto_create_stream_id(
        db,
        explicit_stream_id=auto_create_stream_id,
    )
    if target_stream_id is None:
        return TaskTypeMatchResult(task_type=None, unknown_task_name=original)

    created = TaskType(
        stream_id=target_stream_id,
        name=(canonical or original).strip(),
        description="Auto-created during historical import",
        is_active=True,
        is_billable=True,
    )
    db.add(created)
    db.flush()
    return TaskTypeMatchResult(task_type=created, created=True)

