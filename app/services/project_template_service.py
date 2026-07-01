from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import MilestoneStatus
from app.models.models import (
    Customer,
    Milestone,
    Project,
    ProjectTemplate,
    ProjectTemplateMilestone,
    ProjectType,
)


def list_matching_templates(
    db: Session,
    *,
    project_type_id: UUID,
    customer_id: UUID,
) -> list[ProjectTemplate]:
    return list(
        db.scalars(
            select(ProjectTemplate)
            .options(selectinload(ProjectTemplate.milestones))
            .where(
                ProjectTemplate.project_type_id == project_type_id,
                ProjectTemplate.is_active.is_(True),
                or_(
                    ProjectTemplate.customer_id.is_(None),
                    ProjectTemplate.customer_id == customer_id,
                ),
            )
            .order_by(
                ProjectTemplate.customer_id.is_(None),
                ProjectTemplate.is_default.desc(),
                ProjectTemplate.name,
            )
        ).all()
    )


def resolve_template(
    db: Session,
    *,
    project_type_id: UUID,
    customer_id: UUID,
    template_id: UUID | None = None,
) -> ProjectTemplate:
    if template_id is not None:
        template = db.get(ProjectTemplate, template_id)
        if template is None or not template.is_active:
            raise ProTrackValidationError(
                "project_template_id must reference an active project template"
            )
        if template.project_type_id != project_type_id:
            raise ProTrackValidationError(
                "Selected template does not match the chosen project type"
            )
        if template.customer_id not in (None, customer_id):
            raise ProTrackValidationError(
                "Selected template does not apply to the chosen customer"
            )
        return template

    customer = db.get(Customer, customer_id)
    if customer is not None and customer.default_project_template_id is not None:
        default_template = db.get(ProjectTemplate, customer.default_project_template_id)
        if (
            default_template is not None
            and default_template.is_active
            and default_template.project_type_id == project_type_id
            and default_template.customer_id in (None, customer_id)
        ):
            return default_template

    customer_template = db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.project_type_id == project_type_id,
            ProjectTemplate.customer_id == customer_id,
            ProjectTemplate.is_active.is_(True),
        )
    )
    if customer_template is not None:
        return customer_template

    default_template = db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.project_type_id == project_type_id,
            ProjectTemplate.customer_id.is_(None),
            ProjectTemplate.is_default.is_(True),
            ProjectTemplate.is_active.is_(True),
        )
    )
    if default_template is not None:
        return default_template

    fallback = db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.project_type_id == project_type_id,
            ProjectTemplate.customer_id.is_(None),
            ProjectTemplate.is_active.is_(True),
        )
    )
    if fallback is not None:
        return fallback

    raise ProTrackValidationError(
        "No active project template is configured for the selected project type"
    )


def resolve_template_for_import(
    db: Session,
    *,
    customer: Customer,
    project_type_name: str = "Mold Design",
) -> ProjectTemplate:
    project_type = db.scalar(
        select(ProjectType).where(ProjectType.name == project_type_name)
    )
    if project_type is None:
        raise ValueError(
            f"Project type '{project_type_name}' is not configured in the system."
        )
    return resolve_template(
        db,
        project_type_id=project_type.id,
        customer_id=customer.id,
    )


def create_milestones_from_template(
    db: Session,
    *,
    project: Project,
    template: ProjectTemplate,
    anchor_date: date | None = None,
) -> None:
    anchor = anchor_date or date.today()
    template_milestones = db.scalars(
        select(ProjectTemplateMilestone)
        .where(ProjectTemplateMilestone.project_template_id == template.id)
        .order_by(ProjectTemplateMilestone.sort_order)
    ).all()

    if not template_milestones:
        raise ProTrackValidationError(
            f"Project template '{template.name}' has no milestones configured"
        )

    for template_milestone in template_milestones:
        due_date = None
        if template_milestone.default_due_offset_days is not None:
            due_date = anchor + timedelta(days=template_milestone.default_due_offset_days)
        db.add(
            Milestone(
                project_id=project.id,
                name=template_milestone.milestone_name,
                description=template_milestone.description,
                status=MilestoneStatus.not_started,
                sort_order=template_milestone.sort_order,
                due_date=due_date,
            )
        )


def template_is_in_use(db: Session, template_id: UUID) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(Project)
        .where(Project.project_template_id == template_id)
    )
    return bool(count)


def clear_default_for_type(
    db: Session,
    *,
    project_type_id: UUID,
    exclude_template_id: UUID | None = None,
) -> None:
    query = select(ProjectTemplate).where(
        ProjectTemplate.project_type_id == project_type_id,
        ProjectTemplate.customer_id.is_(None),
        ProjectTemplate.is_default.is_(True),
    )
    if exclude_template_id is not None:
        query = query.where(ProjectTemplate.id != exclude_template_id)
    for template in db.scalars(query).all():
        template.is_default = False
        db.add(template)
