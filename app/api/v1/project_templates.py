from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db
from app.core.exceptions import ProTrackValidationError
from app.core.pagination import PaginatedResponse, pagination_query, PaginationParams
from app.crud.project_template import project_template as project_template_crud
from app.models.models import User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.templates import (
    ProjectTemplateCreate,
    ProjectTemplateDetailRead,
    ProjectTemplateMatchRead,
    ProjectTemplateMilestoneRead,
    ProjectTemplateRead,
    ProjectTemplateUpdate,
)
from app.services.project_template_service import list_matching_templates
from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)

router = APIRouter(prefix="/project-templates", tags=["project-templates"])
admin_access = Depends(require_roles("Admin"))
write_access = Depends(require_roles("Admin"))


def _build_template_read(
    template,
    *,
    milestone_count: int | None = None,
    projects_using_count: int = 0,
) -> ProjectTemplateRead:
    count = milestone_count if milestone_count is not None else len(template.milestones)
    return ProjectTemplateRead(
        id=template.id,
        name=template.name,
        description=template.description,
        project_type_id=template.project_type_id,
        customer_id=template.customer_id,
        default_team_id=template.default_team_id,
        is_default=template.is_default,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
        milestone_count=count,
        projects_using_count=projects_using_count,
        project_type_name=template.project_type.name if template.project_type else None,
        customer_name=template.customer.name if template.customer else None,
    )


def _build_template_detail(template) -> ProjectTemplateDetailRead:
    base = _build_template_read(template)
    return ProjectTemplateDetailRead(
        **base.model_dump(),
        milestones=[
            ProjectTemplateMilestoneRead.model_validate(milestone)
            for milestone in template.milestones
        ],
    )


@router.get("/match", response_model=list[ProjectTemplateMatchRead])
def match_project_templates(
    project_type_id: UUID = Query(...),
    customer_id: UUID = Query(...),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    templates = list_matching_templates(
        db,
        project_type_id=project_type_id,
        customer_id=customer_id,
    )
    return [
        ProjectTemplateMatchRead(
            id=template.id,
            name=template.name,
            description=template.description,
            project_type_id=template.project_type_id,
            customer_id=template.customer_id,
            is_default=template.is_default,
            is_customer_specific=template.customer_id is not None,
            customer_name=template.customer.name if template.customer else None,
            default_team_id=template.default_team_id,
            milestone_count=len(template.milestones),
        )
        for template in templates
    ]


@router.get(
    "",
    response_model=PaginatedResponse[ProjectTemplateRead],
    dependencies=[Depends(require_roles("Admin"))],
)
def list_project_templates(
    pagination: PaginationParams = Depends(pagination_query),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    page = project_template_crud.get_multi_paginated_with_counts(
        db,
        page=pagination.page,
        page_size=pagination.page_size,
        skip=pagination.skip,
        limit=pagination.limit,
        search=search,
    )
    items = [
        _build_template_read(
            template,
            milestone_count=milestone_count,
            projects_using_count=projects_using_count,
        )
        for template, milestone_count, projects_using_count in page.items
    ]
    return PaginatedResponse.build(
        items=items,
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get(
    "/{record_id}",
    response_model=ProjectTemplateDetailRead,
    dependencies=[Depends(require_roles("Admin"))],
)
def get_project_template(record_id: UUID, db: Session = Depends(get_db)):
    template = project_template_crud.get_with_milestones(db, record_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _build_template_detail(template)


@router.get(
    "/{record_id}/delete-check",
    response_model=DeleteCheckResponse,
    dependencies=[admin_access],
)
def delete_check(record_id: UUID, db: Session = Depends(get_db)):
    try:
        return run_delete_check(db, "project_template", record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post(
    "",
    response_model=ProjectTemplateDetailRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("Admin"))],
)
def create_project_template(
    obj_in: ProjectTemplateCreate,
    db: Session = Depends(get_db),
):
    template = project_template_crud.create(db, obj_in=obj_in)
    return _build_template_detail(template)


@router.patch(
    "/{record_id}",
    response_model=ProjectTemplateDetailRead,
    dependencies=[Depends(require_roles("Admin"))],
)
def update_project_template(
    record_id: UUID,
    obj_in: ProjectTemplateUpdate,
    db: Session = Depends(get_db),
):
    template = project_template_crud.get_with_milestones(db, record_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        updated = project_template_crud.update(db, db_obj=template, obj_in=obj_in)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _build_template_detail(updated)


@router.post(
    "/{record_id}/duplicate",
    response_model=ProjectTemplateDetailRead,
    dependencies=[Depends(require_roles("Admin"))],
)
def duplicate_project_template(record_id: UUID, db: Session = Depends(get_db)):
    try:
        duplicate = project_template_crud.duplicate(db, template_id=record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_template_detail(duplicate)


@router.post(
    "/{record_id}/deactivate",
    response_model=ProjectTemplateRead,
    dependencies=[Depends(require_roles("Admin"))],
)
def deactivate_project_template(record_id: UUID, db: Session = Depends(get_db)):
    try:
        template = project_template_crud.deactivate(db, template_id=record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_template_read(template)


@router.post(
    "/{record_id}/reactivate",
    response_model=ProjectTemplateRead,
    dependencies=[Depends(require_roles("Admin"))],
)
def reactivate_project_template(record_id: UUID, db: Session = Depends(get_db)):
    try:
        template = project_template_crud.reactivate(db, template_id=record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_template_read(template)


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[admin_access],
)
def delete_project_template(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = project_template_crud.get_with_milestones(db, record_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        ensure_can_delete(db, "project_template", record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    deleted = project_template_crud.delete(db, record_id=record_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    log_record_deleted(
        db,
        user=current_user,
        entity_key="project_template",
        record_id=record_id,
        record_name=template.name,
    )
