from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_special
from app.api.deps import get_db
from app.core.access_control import SPECIAL_CREATE_PROJECTS, SPECIAL_MANAGE_PROJECT_TEMPLATES
from app.core.exceptions import ProTrackValidationError
from app.core.pagination import PaginatedResponse, pagination_query, PaginationParams
from app.core.permissions import user_holds_special
from app.crud.project_template import project_template as project_template_crud
from app.models.enums import ForecastStatus
from app.models.models import Project, User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.templates import (
    ProjectTemplateCreate,
    ProjectTemplateDetailRead,
    ProjectTemplateMatchRead,
    ProjectTemplateMilestoneRead,
    ProjectTemplateRead,
    ProjectTemplateRevisionCreate,
    ProjectTemplateUpdate,
    ProjectTemplateVersionRead,
    TemplatePreviewMilestone,
    TemplatePreviewRead,
    TemplatePreviewRequest,
)
from app.services.project_template_service import list_matching_templates
from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)
from app.services.scheduling_service import parse_id_list, schedule_template_preview

router = APIRouter(prefix="/project-templates", tags=["project-templates"])
manage_access = Depends(require_special(SPECIAL_MANAGE_PROJECT_TEMPLATES))


def _require_preview_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if user_holds_special(db, current_user, SPECIAL_MANAGE_PROJECT_TEMPLATES) or user_holds_special(
        db, current_user, SPECIAL_CREATE_PROJECTS
    ):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires the 'manage_project_templates' or 'create_projects' permission.",
    )


def _projects_using(db: Session, template_ids: list[UUID]) -> dict[UUID, int]:
    if not template_ids:
        return {}
    rows = db.execute(
        select(Project.project_template_id, func.count(Project.id))
        .where(Project.project_template_id.in_(template_ids))
        .group_by(Project.project_template_id)
    ).all()
    return {template_id: int(count) for template_id, count in rows}


def _milestone_read(milestone) -> ProjectTemplateMilestoneRead:
    read = ProjectTemplateMilestoneRead.model_validate(milestone, from_attributes=True)
    return read.model_copy(
        update={"depends_on": [UUID(value) for value in parse_id_list(milestone.depends_on_ids)]}
    )


def _build_template_read(
    template,
    *,
    milestone_count: int | None = None,
    projects_using_count: int = 0,
    version_count: int = 1,
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
        scheduling_mode=template.scheduling_mode,
        revision_note=template.revision_note,
        created_at=template.created_at,
        updated_at=template.updated_at,
        milestone_count=count,
        projects_using_count=projects_using_count,
        project_type_name=template.project_type.name if template.project_type else None,
        customer_name=template.customer.name if template.customer else None,
        template_family_id=template.template_family_id or template.id,
        version=template.version or 1,
        version_count=version_count,
        activated_at=template.activated_at,
    )


def _build_template_detail(
    db: Session, template, *, created_new_version: bool = False
) -> ProjectTemplateDetailRead:
    base = _build_template_read(
        template,
        projects_using_count=_projects_using(db, [template.id]).get(template.id, 0),
        version_count=project_template_crud.version_count(db, template),
    )
    return ProjectTemplateDetailRead(
        **base.model_dump(),
        milestones=[
            _milestone_read(milestone)
            for milestone in sorted(template.milestones, key=lambda row: row.sort_order)
        ],
        created_new_version=created_new_version,
    )


def _load(db: Session, record_id: UUID):
    template = project_template_crud.get_with_milestones(db, record_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return template


def _unprocessable(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


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
    dependencies=[manage_access],
)
def list_project_templates(
    pagination: PaginationParams = Depends(pagination_query),
    search: str | None = Query(None),
    customer_id: UUID | None = Query(None),
    project_type_id: UUID | None = Query(None),
    scope: str | None = Query(
        None,
        description="Filter by ownership: all | customer | general",
    ),
    db: Session = Depends(get_db),
):
    page = project_template_crud.get_multi_paginated_with_counts(
        db,
        page=pagination.page,
        page_size=pagination.page_size,
        skip=pagination.skip,
        limit=pagination.limit,
        search=search,
        customer_id=customer_id,
        project_type_id=project_type_id,
        scope=scope,
    )
    items = [
        _build_template_read(
            template,
            milestone_count=milestone_count,
            projects_using_count=projects_using_count,
            version_count=project_template_crud.version_count(db, template),
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
    dependencies=[manage_access],
)
def get_project_template(record_id: UUID, db: Session = Depends(get_db)):
    return _build_template_detail(db, _load(db, record_id))


@router.get(
    "/{record_id}/versions",
    response_model=list[ProjectTemplateVersionRead],
    dependencies=[manage_access],
)
def list_template_versions(record_id: UUID, db: Session = Depends(get_db)):
    template = _load(db, record_id)
    versions = project_template_crud.family_versions(db, template)
    usage = _projects_using(db, [row.id for row in versions])
    return [
        ProjectTemplateVersionRead(
            id=row.id,
            version=row.version or 1,
            is_active=row.is_active,
            revision_note=row.revision_note,
            milestone_count=len(row.milestones),
            projects_using_count=usage.get(row.id, 0),
            created_at=row.created_at,
            activated_at=row.activated_at,
        )
        for row in sorted(versions, key=lambda item: item.version or 1, reverse=True)
    ]


@router.post(
    "/{record_id}/preview",
    response_model=TemplatePreviewRead,
)
def preview_project_template(
    record_id: UUID,
    payload: TemplatePreviewRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(_require_preview_access),
):
    template = _load(db, record_id)
    rows = sorted(template.milestones, key=lambda row: row.sort_order)
    result, estimates, warnings, effort = schedule_template_preview(
        db,
        rows,
        start_date=payload.start_date,
        stage_hours=payload.stage_hours,
        mode=template.scheduling_mode,
    )
    scheduled = {item.key: item for item in result.items}
    milestones = []
    for row in rows:
        item = scheduled.get(str(row.id))
        if item is None:
            continue
        estimate = estimates[row.id]
        milestones.append(
            TemplatePreviewMilestone(
                name=row.milestone_name,
                project_stage=row.project_stage,
                sort_order=row.sort_order,
                planned_hours=estimate.hours,
                estimate_basis=estimate.basis,
                start_date=item.start,
                finish_date=item.finish,
                depends_on=parse_id_list(row.depends_on_ids),
            )
        )
    return TemplatePreviewRead(
        template_id=template.id,
        version=template.version or 1,
        start_date=payload.start_date,
        completion_date=result.completion,
        forecast_status=(
            ForecastStatus.invalid.value if result.invalid else ForecastStatus.provisional.value
        ),
        forecast_note=effort.note,
        milestones=milestones,
        warnings=warnings,
    )


@router.get(
    "/{record_id}/delete-check",
    response_model=DeleteCheckResponse,
    dependencies=[manage_access],
)
def delete_check(record_id: UUID, db: Session = Depends(get_db)):
    try:
        return run_delete_check(db, "project_template", record_id)
    except ProTrackValidationError as exc:
        raise _unprocessable(exc) from exc


@router.post(
    "",
    response_model=ProjectTemplateDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_template(
    obj_in: ProjectTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_special(SPECIAL_MANAGE_PROJECT_TEMPLATES)),
):
    try:
        template = project_template_crud.create(db, obj_in=obj_in, created_by_id=current_user.id)
    except ProTrackValidationError as exc:
        raise _unprocessable(exc) from exc
    return _build_template_detail(db, _load(db, template.id))


@router.patch(
    "/{record_id}",
    response_model=ProjectTemplateDetailRead,
)
def update_project_template(
    record_id: UUID,
    obj_in: ProjectTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_special(SPECIAL_MANAGE_PROJECT_TEMPLATES)),
):
    template = _load(db, record_id)
    try:
        updated, created_new_version = project_template_crud.update_with_versioning(
            db, db_obj=template, obj_in=obj_in, updated_by_id=current_user.id
        )
    except ProTrackValidationError as exc:
        raise _unprocessable(exc) from exc
    return _build_template_detail(
        db, _load(db, updated.id), created_new_version=created_new_version
    )


@router.post(
    "/{record_id}/revisions",
    response_model=ProjectTemplateDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_template_revision(
    record_id: UUID,
    payload: ProjectTemplateRevisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_special(SPECIAL_MANAGE_PROJECT_TEMPLATES)),
):
    try:
        revision = project_template_crud.create_revision(
            db,
            template_id=record_id,
            revision_note=payload.revision_note,
            created_by_id=current_user.id,
        )
    except ProTrackValidationError as exc:
        raise _unprocessable(exc) from exc
    return _build_template_detail(db, _load(db, revision.id))


@router.post(
    "/{record_id}/duplicate",
    response_model=ProjectTemplateDetailRead,
)
def duplicate_project_template(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_special(SPECIAL_MANAGE_PROJECT_TEMPLATES)),
):
    try:
        duplicate = project_template_crud.duplicate(
            db, template_id=record_id, created_by_id=current_user.id
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_template_detail(db, _load(db, duplicate.id))


@router.post(
    "/{record_id}/deactivate",
    response_model=ProjectTemplateRead,
    dependencies=[manage_access],
)
def deactivate_project_template(record_id: UUID, db: Session = Depends(get_db)):
    try:
        template = project_template_crud.deactivate(db, template_id=record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_template_read(
        template, version_count=project_template_crud.version_count(db, template)
    )


@router.post(
    "/{record_id}/reactivate",
    response_model=ProjectTemplateRead,
    dependencies=[manage_access],
)
def reactivate_project_template(record_id: UUID, db: Session = Depends(get_db)):
    try:
        template = project_template_crud.reactivate(db, template_id=record_id)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _build_template_read(
        template, version_count=project_template_crud.version_count(db, template)
    )


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_template(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_special(SPECIAL_MANAGE_PROJECT_TEMPLATES)),
):
    template = _load(db, record_id)
    try:
        ensure_can_delete(db, "project_template", record_id)
        deleted = project_template_crud.delete(db, record_id=record_id)
    except ProTrackValidationError as exc:
        raise _unprocessable(exc) from exc
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    log_record_deleted(
        db,
        user=current_user,
        entity_key="project_template",
        record_id=record_id,
        record_name=template.name,
    )
