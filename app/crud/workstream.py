"""CRUD helpers for workstreams and project assignments."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.crud.base import CRUDBase
from app.models.models import Project, Team, User
from app.models.workstream import ProjectSavedView, ProjectWorkstream, Workstream
from app.schemas.workstream import (
    ProjectSavedViewCreate,
    ProjectSavedViewRead,
    ProjectSavedViewUpdate,
    ProjectWorkstreamCreate,
    ProjectWorkstreamRead,
    ProjectWorkstreamsReplace,
    WorkstreamCreate,
    WorkstreamUpdate,
)

_SYSTEM_VIEW_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


class CRUDWorkstream(CRUDBase[Workstream, WorkstreamCreate, WorkstreamUpdate]):
    def delete(self, db: Session, *, record_id: UUID) -> Workstream | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        in_use = db.scalar(
            select(func.count())
            .select_from(ProjectWorkstream)
            .where(ProjectWorkstream.workstream_id == record_id)
        )
        if in_use:
            raise ProTrackValidationError(
                "Workstream is assigned to projects — deactivate it instead of deleting"
            )
        return super().delete(db, record_id=record_id)


workstream = CRUDWorkstream(Workstream)


def _user_display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email


def build_project_workstream_read(
    db: Session, link: ProjectWorkstream
) -> ProjectWorkstreamRead:
    ws = db.get(Workstream, link.workstream_id)
    team = db.get(Team, link.team_id) if link.team_id else None
    lead = db.get(User, link.lead_id) if link.lead_id else None
    estimated = link.estimated_hours
    actual = link.actual_hours
    remaining = None
    if estimated is not None:
        remaining = Decimal(estimated) - Decimal(actual or 0)
    return ProjectWorkstreamRead(
        id=link.id,
        project_id=link.project_id,
        workstream_id=link.workstream_id,
        team_id=link.team_id,
        lead_id=link.lead_id,
        status=link.status,
        start_date=link.start_date,
        due_date=link.due_date,
        estimated_hours=link.estimated_hours,
        actual_hours=link.actual_hours,
        progress_percent=link.progress_percent,
        health=link.health,
        priority=link.priority,
        notes=link.notes,
        workstream_name=ws.name if ws else None,
        workstream_code=ws.code if ws else None,
        team_name=team.name if team else None,
        lead_name=_user_display_name(lead),
        remaining_hours=remaining,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def list_project_workstreams(db: Session, project_id: UUID) -> list[ProjectWorkstreamRead]:
    links = list(
        db.scalars(
            select(ProjectWorkstream)
            .where(ProjectWorkstream.project_id == project_id)
            .order_by(ProjectWorkstream.created_at)
        ).all()
    )
    return [build_project_workstream_read(db, link) for link in links]


def replace_project_workstreams(
    db: Session, project: Project, payload: ProjectWorkstreamsReplace
) -> list[ProjectWorkstreamRead]:
    seen: set[UUID] = set()
    for item in payload.items:
        if item.workstream_id in seen:
            raise ProTrackValidationError("Duplicate workstream_id in assignment list")
        seen.add(item.workstream_id)
        ws = db.get(Workstream, item.workstream_id)
        if ws is None or not ws.is_active:
            raise ProTrackValidationError(
                f"workstream_id {item.workstream_id} must reference an active workstream"
            )
        if item.team_id is not None and db.get(Team, item.team_id) is None:
            raise ProTrackValidationError("team_id must reference an existing team")
        if item.lead_id is not None and db.get(User, item.lead_id) is None:
            raise ProTrackValidationError("lead_id must reference an existing user")

    existing = list(
        db.scalars(
            select(ProjectWorkstream).where(ProjectWorkstream.project_id == project.id)
        ).all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    for item in payload.items:
        data = item.model_dump()
        link = ProjectWorkstream(project_id=project.id, **data)
        db.add(link)
    db.commit()
    return list_project_workstreams(db, project.id)


SYSTEM_SAVED_VIEWS: list[dict] = [
    {
        "key": "sys-all",
        "name": "All",
        "filter_json": {},
        "display_json": {"layout": "list"},
        "display_order": 0,
    },
    {
        "key": "sys-my-projects",
        "name": "My Projects",
        "filter_json": {"scope": "my_projects"},
        "display_json": {"layout": "list"},
        "display_order": 10,
    },
    {
        "key": "sys-my-team",
        "name": "My Team",
        "filter_json": {"scope": "my_team"},
        "display_json": {"layout": "list"},
        "display_order": 20,
    },
    {
        "key": "sys-due-soon",
        "name": "Due Soon",
        "filter_json": {"dueDate": "week"},
        "display_json": {"layout": "list"},
        "display_order": 30,
    },
    {
        "key": "sys-overdue",
        "name": "Overdue",
        "filter_json": {"dueDate": "overdue"},
        "display_json": {"layout": "list"},
        "display_order": 40,
    },
    {
        "key": "sys-at-risk",
        "name": "At Risk",
        "filter_json": {"health": "red"},
        "display_json": {"layout": "list"},
        "display_order": 50,
    },
    {
        "key": "sys-recent",
        "name": "Recently Updated",
        "filter_json": {"sort": "updated_desc"},
        "display_json": {"layout": "list"},
        "display_order": 60,
    },
]


def _parse_json_field(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def saved_view_to_read(row: ProjectSavedView) -> ProjectSavedViewRead:
    return ProjectSavedViewRead(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        is_system=row.is_system,
        filter_json=_parse_json_field(row.filter_json),
        display_json=_parse_json_field(row.display_json),
        is_default=row.is_default,
        display_order=row.display_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_saved_views(db: Session, user: User) -> list[ProjectSavedViewRead]:
    epoch = datetime(2020, 1, 1, tzinfo=UTC)
    system = [
        ProjectSavedViewRead(
            id=uuid.uuid5(_SYSTEM_VIEW_NS, item["key"]),
            user_id=None,
            name=item["name"],
            is_system=True,
            filter_json=item["filter_json"],
            display_json=item["display_json"],
            is_default=False,
            display_order=item["display_order"],
            created_at=epoch,
            updated_at=epoch,
        )
        for item in SYSTEM_SAVED_VIEWS
    ]

    rows = list(
        db.scalars(
            select(ProjectSavedView)
            .where(ProjectSavedView.user_id == user.id)
            .order_by(ProjectSavedView.display_order, ProjectSavedView.name)
        ).all()
    )
    return system + [saved_view_to_read(row) for row in rows]


def create_saved_view(
    db: Session, user: User, payload: ProjectSavedViewCreate
) -> ProjectSavedViewRead:
    if payload.is_default:
        _clear_default_views(db, user.id)
    row = ProjectSavedView(
        user_id=user.id,
        name=payload.name,
        is_system=False,
        filter_json=json.dumps(payload.filter_json or {}),
        display_json=json.dumps(payload.display_json or {}),
        is_default=payload.is_default,
        display_order=payload.display_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return saved_view_to_read(row)


def update_saved_view(
    db: Session, user: User, view_id: UUID, payload: ProjectSavedViewUpdate
) -> ProjectSavedViewRead:
    row = db.get(ProjectSavedView, view_id)
    if row is None or row.user_id != user.id or row.is_system:
        raise ProTrackValidationError("Saved view not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_default"):
        _clear_default_views(db, user.id)
    if "filter_json" in data and data["filter_json"] is not None:
        data["filter_json"] = json.dumps(data["filter_json"])
    if "display_json" in data and data["display_json"] is not None:
        data["display_json"] = json.dumps(data["display_json"])
    for key, value in data.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return saved_view_to_read(row)


def delete_saved_view(db: Session, user: User, view_id: UUID) -> None:
    row = db.get(ProjectSavedView, view_id)
    if row is None or row.user_id != user.id or row.is_system:
        raise ProTrackValidationError("Saved view not found")
    db.delete(row)
    db.commit()


def _clear_default_views(db: Session, user_id: UUID) -> None:
    for row in db.scalars(
        select(ProjectSavedView).where(
            ProjectSavedView.user_id == user_id, ProjectSavedView.is_default.is_(True)
        )
    ).all():
        row.is_default = False
