from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
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
    TimesheetEntry,
)


def list_matching_templates(
    db: Session,
    *,
    project_type_id: UUID,
    customer_id: UUID,
) -> list[ProjectTemplate]:
    """Return all active templates for the project type.

    Customer-specific templates remain available for any project of that type so
    quote-created and manually created projects see the same catalog. Templates
    for the selected customer are sorted first, then global defaults, then others.
    """
    templates = list(
        db.scalars(
            select(ProjectTemplate)
            .options(
                selectinload(ProjectTemplate.milestones),
                selectinload(ProjectTemplate.customer),
            )
            .where(
                ProjectTemplate.project_type_id == project_type_id,
                ProjectTemplate.is_active.is_(True),
            )
        ).all()
    )

    def _sort_key(template: ProjectTemplate) -> tuple[int, int, str]:
        if template.customer_id == customer_id:
            group = 0
        elif template.customer_id is None:
            group = 1
        else:
            group = 2
        return (group, 0 if template.is_default else 1, template.name.lower())

    templates.sort(key=_sort_key)
    return templates


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
        return template

    customer = db.get(Customer, customer_id)
    if customer is not None and customer.default_project_template_id is not None:
        default_template = db.get(ProjectTemplate, customer.default_project_template_id)
        if (
            default_template is not None
            and default_template.is_active
            and default_template.project_type_id == project_type_id
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


from app.services.milestone_assignment_service import resolve_auto_assigned_user_id


def resolve_template_assigned_user(
    project: Project,
    *,
    assigned_role: str | None,
    default_assigned_user_id: UUID | None,
) -> UUID | None:
    if default_assigned_user_id is not None:
        return default_assigned_user_id
    if not assigned_role:
        return resolve_auto_assigned_user_id(project, "")
    normalized = assigned_role.strip().lower()
    if normalized in {"designer", "senior designer", "junior designer"}:
        return project.designer_id
    if normalized == "surfacer":
        return project.surfacer_id
    if normalized in {"design leader", "team leader", "engineering manager"}:
        return project.design_leader_id
    if "feasibility" in normalized:
        return project.surfacer_id
    return resolve_auto_assigned_user_id(project, assigned_role)


def create_milestones_from_template(    db: Session,
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
        if template_milestone.is_visible is False:
            continue
        due_date = None
        if template_milestone.default_due_offset_days is not None:
            due_date = anchor + timedelta(days=template_milestone.default_due_offset_days)
        assigned_user_id = resolve_template_assigned_user(
            project,
            assigned_role=template_milestone.assigned_role,
            default_assigned_user_id=template_milestone.default_assigned_user_id,
        )
        if assigned_user_id is None and template_milestone.assigned_role:
            assigned_user_id = resolve_auto_assigned_user_id(
                project,
                template_milestone.milestone_name,
            )
        db.add(
            Milestone(
                project_id=project.id,
                name=template_milestone.milestone_name,
                description=template_milestone.description,
                status=MilestoneStatus.not_started,
                sort_order=template_milestone.sort_order,
                due_date=due_date,
                planned_hours=template_milestone.estimated_hours or Decimal("0"),
                assigned_user_id=assigned_user_id,
                assignment_manual=template_milestone.default_assigned_user_id is not None,
            )
        )
    from app.services.milestone_workspace_service import recalculate_project_planned_hours
    from app.services.milestone_assignment_service import sync_milestone_assignments

    recalculate_project_planned_hours(db, project.id)
    sync_milestone_assignments(db, project.id)


def project_has_completed_milestones(db: Session, project_id: UUID) -> bool:
    completed = db.scalar(
        select(func.count())
        .select_from(Milestone)
        .where(
            Milestone.project_id == project_id,
            Milestone.status == MilestoneStatus.completed,
        )
    )
    return int(completed or 0) > 0


def project_has_logged_milestone_hours(db: Session, project_id: UUID) -> bool:
    milestone_ids = list(
        db.scalars(select(Milestone.id).where(Milestone.project_id == project_id)).all()
    )
    if not milestone_ids:
        return False
    logged_count = int(
        db.scalar(
            select(func.count())
            .select_from(TimesheetEntry)
            .where(
                TimesheetEntry.milestone_id.in_(milestone_ids),
                TimesheetEntry.is_deleted.is_(False),
            )
        )
        or 0
    )
    return logged_count > 0


def get_template_change_blockers(db: Session, project_id: UUID) -> list[str]:
    blockers: list[str] = []
    if project_has_completed_milestones(db, project_id):
        blockers.append(
            "At least one milestone has been marked completed"
        )
    if project_has_logged_milestone_hours(db, project_id):
        blockers.append(
            "Timesheet hours are logged against current milestones"
        )
    return blockers


def can_change_project_template(db: Session, project_id: UUID) -> tuple[bool, str | None]:
    blockers = get_template_change_blockers(db, project_id)
    if not blockers:
        return True, None
    return False, blockers[0]


def assert_can_change_project_template(db: Session, project_id: UUID) -> None:
    blockers = get_template_change_blockers(db, project_id)
    if not blockers:
        return
    if project_has_completed_milestones(db, project_id):
        raise ProTrackValidationError(
            "Cannot change the project template after a milestone has been marked completed"
        )
    if project_has_logged_milestone_hours(db, project_id):
        raise ProTrackValidationError(
            "Cannot replace milestones while timesheet hours are logged against them"
        )


def apply_template_to_project(
    db: Session,
    *,
    project: Project,
    template: ProjectTemplate,
    anchor_date: date | None = None,
) -> None:
    assert_can_change_project_template(db, project.id)

    existing_milestones = list(
        db.scalars(select(Milestone).where(Milestone.project_id == project.id)).all()
    )
    milestone_ids = [row.id for row in existing_milestones]
    if milestone_ids and project_has_logged_milestone_hours(db, project.id):
        raise ProTrackValidationError(
            "Cannot replace milestones while timesheet hours are logged against them"
        )
    for milestone in existing_milestones:
        db.delete(milestone)
    db.flush()

    project.project_template_id = template.id
    if project.team_id is None and template.default_team_id is not None:
        project.team_id = template.default_team_id
        db.add(project)
    create_milestones_from_template(
        db,
        project=project,
        template=template,
        anchor_date=anchor_date,
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
