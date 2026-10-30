from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import ExecutionStatus, MilestoneStatus, ProjectStage
from app.models.models import (
    Customer,
    Milestone,
    Project,
    ProjectTemplate,
    ProjectTemplateMilestone,
    ProjectType,
)


def active_version_of(db: Session, template: ProjectTemplate | None) -> ProjectTemplate | None:
    """Return the active version in ``template``'s family (itself when active)."""
    if template is None:
        return None
    if template.is_active:
        return template
    family_id = template.template_family_id or template.id
    return db.scalar(
        select(ProjectTemplate)
        .where(
            (ProjectTemplate.template_family_id == family_id) | (ProjectTemplate.id == family_id),
            ProjectTemplate.is_active.is_(True),
        )
        .order_by(ProjectTemplate.version.desc())
        .limit(1)
    )


def _template_has_milestones(db: Session, template_id: UUID) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(ProjectTemplateMilestone)
        .where(ProjectTemplateMilestone.project_template_id == template_id)
    )
    return int(count or 0) > 0


def _load_ordered_template_milestones(
    db: Session, template_id: UUID
) -> list[ProjectTemplateMilestone]:
    return list(
        db.scalars(
            select(ProjectTemplateMilestone)
            .where(ProjectTemplateMilestone.project_template_id == template_id)
            .order_by(ProjectTemplateMilestone.sort_order)
        ).all()
    )


def _fallback_template_with_milestones(
    db: Session,
    *,
    project_type_id: UUID,
    exclude_template_id: UUID | None = None,
) -> ProjectTemplate | None:
    candidates = list(
        db.scalars(
            select(ProjectTemplate)
            .where(
                ProjectTemplate.project_type_id == project_type_id,
                ProjectTemplate.is_active.is_(True),
                ProjectTemplate.customer_id.is_(None),
            )
            .order_by(
                ProjectTemplate.is_default.desc(),
                ProjectTemplate.name.asc(),
            )
        ).all()
    )
    for candidate in candidates:
        if exclude_template_id is not None and candidate.id == exclude_template_id:
            continue
        if _template_has_milestones(db, candidate.id):
            return candidate
    return None


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
    Templates without milestones are sorted last within each group.
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

    def _sort_key(template: ProjectTemplate) -> tuple[int, int, int, str]:
        if template.customer_id == customer_id:
            group = 0
        elif template.customer_id is None:
            group = 1
        else:
            group = 2
        has_milestones = 0 if template.milestones else 1
        return (
            group,
            has_milestones,
            0 if template.is_default else 1,
            template.name.lower(),
        )

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
        template = active_version_of(db, db.get(ProjectTemplate, template_id))
        if template is None:
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
        default_template = active_version_of(
            db, db.get(ProjectTemplate, customer.default_project_template_id)
        )
        if (
            default_template is not None
            and default_template.is_active
            and default_template.project_type_id == project_type_id
            and _template_has_milestones(db, default_template.id)
        ):
            return default_template

    customer_templates = list(
        db.scalars(
            select(ProjectTemplate).where(
                ProjectTemplate.project_type_id == project_type_id,
                ProjectTemplate.customer_id == customer_id,
                ProjectTemplate.is_active.is_(True),
            )
        ).all()
    )
    for customer_template in customer_templates:
        if _template_has_milestones(db, customer_template.id):
            return customer_template

    default_template = db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.project_type_id == project_type_id,
            ProjectTemplate.customer_id.is_(None),
            ProjectTemplate.is_default.is_(True),
            ProjectTemplate.is_active.is_(True),
        )
    )
    if default_template is not None and _template_has_milestones(db, default_template.id):
        return default_template

    fallback = _fallback_template_with_milestones(db, project_type_id=project_type_id)
    if fallback is not None:
        return fallback

    any_active = db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.project_type_id == project_type_id,
            ProjectTemplate.is_active.is_(True),
        )
    )
    if any_active is not None:
        return any_active

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


def create_milestones_from_template(
    db: Session,
    *,
    project: Project,
    template: ProjectTemplate,
    anchor_date: date | None = None,
    stage_hours: dict[ProjectStage, Decimal] | None = None,
) -> list[str]:
    """Generate the project's own milestone records from the template version.

    Returns warnings about stage hours that could not be placed on milestones.
    """
    from app.services.scheduling_service import distribute_stage_hours, dump_id_list, parse_id_list

    anchor = anchor_date or project.start_date or date.today()
    template_milestones = _load_ordered_template_milestones(db, template.id)

    if not template_milestones:
        fallback = _fallback_template_with_milestones(
            db,
            project_type_id=template.project_type_id,
            exclude_template_id=template.id,
        )
        if fallback is not None:
            template_milestones = _load_ordered_template_milestones(db, fallback.id)

    if not template_milestones:
        raise ProTrackValidationError(
            f"Project template '{template.name}' has no milestones configured. "
            "Add milestones in Admin → Project Templates before using it."
        )

    estimates, warnings = distribute_stage_hours(template_milestones, stage_hours or {})
    created: dict[str, Milestone] = {}
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
        estimate = estimates.get(template_milestone.id)
        hours = estimate.hours if estimate else Decimal(str(template_milestone.estimated_hours or 0))
        milestone = Milestone(
            project_id=project.id,
            name=template_milestone.milestone_name,
            description=template_milestone.description,
            status=MilestoneStatus.not_started,
            sort_order=template_milestone.sort_order,
            due_date=due_date,
            planned_hours=hours,
            original_planned_hours=hours,
            estimate_basis=estimate.basis if estimate else None,
            assigned_user_id=assigned_user_id,
            assignment_manual=template_milestone.default_assigned_user_id is not None,
            is_required=bool(template_milestone.is_required),
            project_stage=template_milestone.project_stage,
            template_milestone_id=template_milestone.id,
        )
        db.add(milestone)
        created[str(template_milestone.id)] = milestone
    db.flush()
    for template_milestone in template_milestones:
        milestone = created.get(str(template_milestone.id))
        if milestone is None:
            continue
        deps = [
            str(created[dep].id)
            for dep in parse_id_list(template_milestone.depends_on_ids)
            if dep in created
        ]
        milestone.depends_on_ids = dump_id_list(deps)
        db.add(milestone)
    from app.services.milestone_workspace_service import recalculate_project_planned_hours
    from app.services.milestone_assignment_service import sync_milestone_assignments

    recalculate_project_planned_hours(db, project.id)
    sync_milestone_assignments(db, project.id)
    return warnings


def template_change_blocked_reason(project: Project) -> str | None:
    """Why the template cannot be changed at all. Milestone progress, hours and
    comments never block a change: existing work is reconciled, not replaced."""
    if project.is_deleted or project.is_archived:
        return "Archived or deleted projects cannot change template"
    if project.execution_status == ExecutionStatus.cancelled:
        return "Cancelled projects are not re-planned"
    return None


def can_change_project_template(project: Project) -> tuple[bool, str | None]:
    reason = template_change_blocked_reason(project)
    return reason is None, reason


def project_has_milestones(db: Session, project_id: UUID) -> bool:
    count = db.scalar(
        select(func.count()).select_from(Milestone).where(Milestone.project_id == project_id)
    )
    return int(count or 0) > 0


def apply_template_to_project(
    db: Session,
    *,
    project: Project,
    template: ProjectTemplate,
    anchor_date: date | None = None,
) -> None:
    """First template on a project with no milestones yet.

    Projects that already have milestones change template through the
    reconciliation preview (``template_reconciliation``), which never deletes
    or overwrites existing milestones.
    """
    reason = template_change_blocked_reason(project)
    if reason:
        raise ProTrackValidationError(reason)
    if project_has_milestones(db, project.id):
        raise ProTrackValidationError(
            "This project already has milestones. Use Change Template to preview how the "
            "new template will be reconciled with the existing milestones.",
            status_code=409,
        )

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
