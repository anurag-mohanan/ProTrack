"""Public API v1 — versioned partner surface (R10)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.public_deps import require_api_key, require_scope
from app.models.integrations import ApiKey
from app.models.models import Milestone, Project, User
from app.services import api_key_service

router = APIRouter(tags=["public-api"])


class PublicHealthRead(BaseModel):
    status: str = "ok"
    api: str = "public"
    version: str = "v1"


class PublicMeRead(BaseModel):
    key_id: UUID
    key_name: str
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    tenant_id: UUID


class PublicProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tool_number: str
    part_description: str
    code: str | None = None
    customer_id: UUID | None = None
    due_date: date | None = None
    execution_status: str | None = None
    project_stage: str | None = None
    health: str | None = None
    priority: str | None = None


class PublicProjectList(BaseModel):
    items: list[PublicProjectRead] = Field(default_factory=list)
    count: int = 0


class PublicMilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    status: str | None = None
    due_date: date | None = None
    completed_at: str | None = None


class PublicMilestoneList(BaseModel):
    items: list[PublicMilestoneRead] = Field(default_factory=list)
    count: int = 0


class PublicUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    designation: str | None = None
    is_active: bool


class PublicUserList(BaseModel):
    items: list[PublicUserRead] = Field(default_factory=list)
    count: int = 0


def _project_read(row: Project) -> PublicProjectRead:
    return PublicProjectRead(
        id=row.id,
        tool_number=row.tool_number,
        part_description=row.part_description,
        code=row.code,
        customer_id=row.customer_id,
        due_date=row.due_date,
        execution_status=str(getattr(row.execution_status, "value", row.execution_status)),
        project_stage=str(getattr(row.project_stage, "value", row.project_stage)),
        health=str(getattr(row.health, "value", row.health)),
        priority=str(getattr(row.priority, "value", row.priority)),
    )


def _milestone_read(row: Milestone) -> PublicMilestoneRead:
    completed = row.completed_at.isoformat() if row.completed_at else None
    return PublicMilestoneRead(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        status=str(getattr(row.status, "value", row.status)),
        due_date=row.due_date,
        completed_at=completed,
    )


@router.get("/health", response_model=PublicHealthRead)
def public_health():
    return PublicHealthRead()


@router.get("/me", response_model=PublicMeRead)
def public_me(key: ApiKey = Depends(require_api_key)):
    return PublicMeRead(
        key_id=key.id,
        key_name=key.name,
        key_prefix=key.key_prefix,
        scopes=api_key_service.parse_scopes(key),
        tenant_id=key.tenant_id,
    )


@router.get("/projects", response_model=PublicProjectList)
def list_projects(
    db: Session = Depends(get_db),
    key: ApiKey = Depends(require_api_key),
):
    require_scope(key, "projects:read")
    rows = list(
        db.scalars(
            select(Project)
            .where(Project.is_deleted.is_(False))
            .order_by(Project.tool_number)
            .limit(200)
        ).all()
    )
    items = [_project_read(row) for row in rows]
    return PublicProjectList(items=items, count=len(items))


@router.get("/projects/{project_id}", response_model=PublicProjectRead)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(require_api_key),
):
    require_scope(key, "projects:read")
    row = db.get(Project, project_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_read(row)


@router.get(
    "/projects/{project_id}/milestones",
    response_model=PublicMilestoneList,
)
def list_project_milestones(
    project_id: UUID,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(require_api_key),
):
    require_scope(key, "milestones:read")
    project = db.get(Project, project_id)
    if project is None or project.is_deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    rows = list(
        db.scalars(
            select(Milestone)
            .where(Milestone.project_id == project_id)
            .order_by(Milestone.name)
            .limit(500)
        ).all()
    )
    items = [_milestone_read(row) for row in rows]
    return PublicMilestoneList(items=items, count=len(items))


@router.get("/users", response_model=PublicUserList)
def list_users(
    db: Session = Depends(get_db),
    key: ApiKey = Depends(require_api_key),
):
    require_scope(key, "users:read")
    rows = list(
        db.scalars(
            select(User)
            .where(
                User.is_deleted.is_(False),
                User.is_archived.is_(False),
            )
            .order_by(User.last_name, User.first_name)
            .limit(500)
        ).all()
    )
    items = [
        PublicUserRead(
            id=row.id,
            email=row.email,
            first_name=row.first_name,
            last_name=row.last_name,
            designation=row.designation,
            is_active=row.is_active,
        )
        for row in rows
    ]
    return PublicUserList(items=items, count=len(items))
