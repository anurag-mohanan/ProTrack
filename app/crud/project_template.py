from typing import override
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.crud.base import CRUDBase
from app.models.models import (
    Customer,
    Project,
    ProjectTemplate,
    ProjectTemplateMilestone,
    ProjectType,
)
from app.schemas.templates import (
    ProjectTemplateCreate,
    ProjectTemplateMilestoneCreate,
    ProjectTemplateUpdate,
)
from app.services.project_template_service import (
    clear_default_for_type,
    template_is_in_use,
)


def _validate_template_references(
    db: Session,
    *,
    project_type_id: UUID,
    customer_id: UUID | None,
) -> None:
    project_type = db.get(ProjectType, project_type_id)
    if project_type is None or not project_type.is_active:
        raise ProTrackValidationError(
            "project_type_id must reference an active project type"
        )
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if customer is None or not customer.is_active:
            raise ProTrackValidationError(
                "customer_id must reference an active customer"
            )


def _milestone_from_schema(
    template: ProjectTemplate,
    milestone: ProjectTemplateMilestoneCreate,
    *,
    index: int,
) -> ProjectTemplateMilestone:
    return ProjectTemplateMilestone(
        project_template_id=template.id,
        milestone_name=milestone.milestone_name,
        description=milestone.description,
        sort_order=milestone.sort_order or index,
        default_due_offset_days=milestone.default_due_offset_days,
        is_required=milestone.is_required,
        is_visible=milestone.is_visible,
        project_stage=milestone.project_stage,
        estimated_hours=milestone.estimated_hours,
        assigned_role=milestone.assigned_role,
        default_assigned_user_id=milestone.default_assigned_user_id,
    )


def _replace_milestones(
    db: Session,
    template: ProjectTemplate,
    milestones: list[ProjectTemplateMilestoneCreate],
) -> None:
    for existing in list(template.milestones):
        db.delete(existing)
    db.flush()

    for index, milestone in enumerate(milestones, start=1):
        db.add(_milestone_from_schema(template, milestone, index=index))


class CRUDProjectTemplate(
    CRUDBase[ProjectTemplate, ProjectTemplateCreate, ProjectTemplateUpdate]
):
    def get_with_milestones(
        self, db: Session, record_id: UUID
    ) -> ProjectTemplate | None:
        return db.scalar(
            select(ProjectTemplate)
            .options(
                selectinload(ProjectTemplate.milestones),
                selectinload(ProjectTemplate.project_type),
                selectinload(ProjectTemplate.customer),
            )
            .where(ProjectTemplate.id == record_id)
        )

    def get_multi_with_counts(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 500,
    ) -> list[tuple[ProjectTemplate, int, int]]:
        milestone_count = func.count(ProjectTemplateMilestone.id).label("milestone_count")
        rows = db.execute(
            select(ProjectTemplate, milestone_count)
            .outerjoin(
                ProjectTemplateMilestone,
                ProjectTemplateMilestone.project_template_id == ProjectTemplate.id,
            )
            .options(
                selectinload(ProjectTemplate.project_type),
                selectinload(ProjectTemplate.customer),
            )
            .group_by(ProjectTemplate.id)
            .order_by(ProjectTemplate.name)
            .offset(skip)
            .limit(limit)
        ).all()
        template_ids = [template.id for template, _ in rows]
        usage_counts: dict[UUID, int] = {}
        if template_ids:
            usage_rows = db.execute(
                select(Project.project_template_id, func.count())
                .where(
                    Project.project_template_id.in_(template_ids),
                    Project.is_deleted.is_(False),
                )
                .group_by(Project.project_template_id)
            ).all()
            usage_counts = {
                template_id: int(count) for template_id, count in usage_rows if template_id
            }
        return [
            (template, int(count), usage_counts.get(template.id, 0))
            for template, count in rows
        ]

    @override
    def create(self, db: Session, *, obj_in: ProjectTemplateCreate) -> ProjectTemplate:
        _validate_template_references(
            db,
            project_type_id=obj_in.project_type_id,
            customer_id=obj_in.customer_id,
        )
        if obj_in.is_default and obj_in.customer_id is None:
            clear_default_for_type(db, project_type_id=obj_in.project_type_id)

        data = obj_in.model_dump(exclude={"milestones"})
        db_obj = ProjectTemplate(**data)
        db.add(db_obj)
        db.flush()

        if obj_in.milestones:
            _replace_milestones(db, db_obj, obj_in.milestones)

        db.commit()
        db.refresh(db_obj)
        return self.get_with_milestones(db, db_obj.id) or db_obj

    @override
    def update(
        self,
        db: Session,
        *,
        db_obj: ProjectTemplate,
        obj_in: ProjectTemplateUpdate | dict[str, object],
    ) -> ProjectTemplate:
        if isinstance(obj_in, dict):
            update_data: dict[str, object] = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        milestones = update_data.pop("milestones", None)
        project_type_id = update_data.get("project_type_id", db_obj.project_type_id)
        customer_id = update_data.get("customer_id", db_obj.customer_id)
        if not isinstance(project_type_id, UUID):
            raise ProTrackValidationError("project_type_id must be a UUID")
        customer_uuid = customer_id if isinstance(customer_id, UUID) else None
        _validate_template_references(
            db,
            project_type_id=project_type_id,
            customer_id=customer_uuid,
        )

        if update_data.get("is_default") and customer_uuid is None:
            clear_default_for_type(
                db,
                project_type_id=project_type_id,
                exclude_template_id=db_obj.id,
            )

        updated = super().update(db, db_obj=db_obj, obj_in=update_data)

        if milestones is not None:
            if not isinstance(milestones, list):
                raise ProTrackValidationError("milestones must be a list")
            parsed = [
                item
                if isinstance(item, ProjectTemplateMilestoneCreate)
                else ProjectTemplateMilestoneCreate.model_validate(item)
                for item in milestones
            ]
            _replace_milestones(db, updated, parsed)
            db.commit()
            db.refresh(updated)

        return self.get_with_milestones(db, updated.id) or updated

    @override
    def delete(self, db: Session, *, record_id: UUID) -> ProjectTemplate | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        if template_is_in_use(db, record_id):
            raise ProTrackValidationError(
                "Cannot delete a project template that is used by existing projects"
            )
        return super().delete(db, record_id=record_id)

    def duplicate(self, db: Session, *, template_id: UUID) -> ProjectTemplate:
        source = self.get_with_milestones(db, template_id)
        if source is None:
            raise ProTrackValidationError("Project template not found")

        duplicate = ProjectTemplate(
            name=f"{source.name} (Copy)",
            description=source.description,
            project_type_id=source.project_type_id,
            customer_id=source.customer_id,
            default_team_id=source.default_team_id,
            is_default=False,
            is_active=True,
        )
        db.add(duplicate)
        db.flush()

        for milestone in source.milestones:
            db.add(
                ProjectTemplateMilestone(
                    project_template_id=duplicate.id,
                    milestone_name=milestone.milestone_name,
                    description=milestone.description,
                    sort_order=milestone.sort_order,
                    default_due_offset_days=milestone.default_due_offset_days,
                    is_required=milestone.is_required,
                    is_visible=milestone.is_visible,
                    project_stage=milestone.project_stage,
                    estimated_hours=milestone.estimated_hours,
                    assigned_role=milestone.assigned_role,
                    default_assigned_user_id=milestone.default_assigned_user_id,
                )
            )

        db.commit()
        db.refresh(duplicate)
        return self.get_with_milestones(db, duplicate.id) or duplicate

    def deactivate(self, db: Session, *, template_id: UUID) -> ProjectTemplate:
        db_obj = self.get(db, template_id)
        if db_obj is None:
            raise ProTrackValidationError("Project template not found")
        return self.update(db, db_obj=db_obj, obj_in={"is_active": False})


project_template = CRUDProjectTemplate(ProjectTemplate)
