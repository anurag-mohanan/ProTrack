from typing import Any, override
from uuid import UUID

from sqlalchemy import Select

from app.core.exceptions import ProTrackValidationError
from app.core.permissions import PROJECT_STAFF_ROLES
from app.crud.base import CRUDBase, Session, select
from app.crud.project_metrics import build_project_read, build_project_reads
from app.models.enums import MilestoneStatus, ProjectLifecycleFilter
from app.models.models import Contact, Customer, Milestone, Project, ProjectType, Role, User
from app.schemas.project import ArchivedProjectListItem, ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_calculation_service import recalculate_project
from app.services.project_lifecycle_service import apply_lifecycle_filter, apply_lifecycle_sort
from app.services.project_template_service import (
    create_milestones_from_template,
    resolve_template,
)

DEFAULT_PROJECT_MILESTONES = (
    "Feasibility",
    "Blockout",
    "Roughing",
    "Intermediate Review",
    "Final Review",
    "File Release",
    "BOM Release",
)


def _lookup_user(db: Session, user_id: UUID) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def _get_active_user(
    db: Session,
    user_id: UUID,
    *,
    field_name: str,
    expected_role: str | None = None,
    expected_roles: frozenset[str] | tuple[str, ...] | None = None,
) -> User:
    user = _lookup_user(db, user_id)
    if user is None:
        raise ProTrackValidationError(
            f"{field_name} must reference an active user (no user found with id {user_id})"
        )

    if not user.is_active:
        raise ProTrackValidationError(
            f"{field_name} must reference an active user"
        )

    if user.is_archived or user.is_deleted:
        raise ProTrackValidationError(
            f"{field_name} must reference an active user"
        )

    if expected_roles:
        role = db.get(Role, user.role_id)
        allowed = ", ".join(sorted(expected_roles))
        if role is None or role.name not in expected_roles:
            raise ProTrackValidationError(
                f"{field_name} must reference a user with one of these roles: {allowed}"
            )
    elif expected_role:
        role = db.get(Role, user.role_id)
        if role is None or role.name != expected_role:
            raise ProTrackValidationError(
                f"{field_name} must reference a user with the {expected_role} role"
            )

    return user


def _validate_project_references(
    db: Session,
    *,
    customer_id: UUID,
    customer_contact_id: UUID,
    design_leader_id: UUID,
    designer_id: UUID | None = None,
    surfacer_id: UUID | None = None,
) -> None:
    contact = db.scalar(select(Contact).where(Contact.id == customer_contact_id))
    if contact is None or contact.customer_id != customer_id:
        raise ProTrackValidationError(
            "customer_contact_id must belong to the selected customer_id"
        )

    _ = _get_active_user(
        db,
        design_leader_id,
        field_name="design_leader_id",
        expected_role="Design Leader",
    )

    if designer_id is not None:
        _ = _get_active_user(
            db,
            designer_id,
            field_name="designer_id",
            expected_roles=PROJECT_STAFF_ROLES,
        )

    if surfacer_id is not None:
        _ = _get_active_user(
            db,
            surfacer_id,
            field_name="surfacer_id",
            expected_roles=PROJECT_STAFF_ROLES,
        )


def _reference_ids_for_update(
    db_obj: Project,
    update_data: dict[str, object],
) -> tuple[UUID, UUID, UUID, UUID | None, UUID | None]:
    def pick_uuid(key: str, current: UUID) -> UUID:
        if key not in update_data:
            return current
        value = update_data[key]
        if not isinstance(value, UUID):
            raise ProTrackValidationError(f"{key} must be a UUID")
        return value

    def pick_optional_uuid(key: str, current: UUID | None) -> UUID | None:
        if key not in update_data:
            return current
        value = update_data[key]
        if value is None:
            return None
        if not isinstance(value, UUID):
            raise ProTrackValidationError(f"{key} must be a UUID")
        return value

    return (
        pick_uuid("customer_id", db_obj.customer_id),
        pick_uuid("customer_contact_id", db_obj.customer_contact_id),
        pick_uuid("design_leader_id", db_obj.design_leader_id),
        pick_optional_uuid("designer_id", db_obj.designer_id),
        pick_optional_uuid("surfacer_id", db_obj.surfacer_id),
    )


class CRUDProject(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    @override
    def create(self, db: Session, *, obj_in: ProjectCreate) -> Project:
        _validate_project_references(
            db,
            customer_id=obj_in.customer_id,
            customer_contact_id=obj_in.customer_contact_id,
            design_leader_id=obj_in.design_leader_id,
            designer_id=obj_in.designer_id,
            surfacer_id=obj_in.surfacer_id,
        )

        db_obj = Project(**obj_in.model_dump())
        db.add(db_obj)
        db.flush()

        template = resolve_template(
            db,
            project_type_id=obj_in.project_type_id,
            customer_id=obj_in.customer_id,
            template_id=obj_in.project_template_id,
        )
        db_obj.project_template_id = template.id
        create_milestones_from_template(
            db,
            project=db_obj,
            template=template,
        )

        db.commit()
        db.refresh(db_obj)
        recalculate_project(db, db_obj.id)
        return db_obj

    @override
    def update(
        self,
        db: Session,
        *,
        db_obj: Project,
        obj_in: ProjectUpdate | dict[str, object],
    ) -> Project:
        if isinstance(obj_in, dict):
            update_data: dict[str, object] = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        (
            customer_id,
            customer_contact_id,
            design_leader_id,
            designer_id,
            surfacer_id,
        ) = _reference_ids_for_update(db_obj, update_data)
        _validate_project_references(
            db,
            customer_id=customer_id,
            customer_contact_id=customer_contact_id,
            design_leader_id=design_leader_id,
            designer_id=designer_id,
            surfacer_id=surfacer_id,
        )

        updated = super().update(db, db_obj=db_obj, obj_in=update_data)
        recalculate_project(db, updated.id)
        return updated

    def get_read(self, db: Session, record_id: UUID) -> ProjectRead | None:
        db_project = self.get(db, record_id)
        if db_project is None:
            return None
        return build_project_read(db, db_project)

    def query_projects(
        self,
        db: Session,
        *,
        lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.active,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        assignment_clause=None,
    ) -> list[Project]:
        stmt: Select[tuple[Project]] = select(Project)
        stmt = apply_lifecycle_filter(stmt, lifecycle)
        if assignment_clause is not None:
            stmt = stmt.where(assignment_clause)
        if filters:
            for field, value in filters.items():
                if field == "lifecycle" or value is None:
                    continue
                stmt = stmt.where(getattr(Project, field) == value)
        stmt = apply_lifecycle_sort(stmt, lifecycle).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def get_multi_read(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, object] | None = None,
        lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.active,
        assignment_clause=None,
    ) -> list[ProjectRead]:
        active_filters = {
            key: value
            for key, value in (filters or {}).items()
            if key != "lifecycle" and value is not None
        }
        projects = self.query_projects(
            db,
            lifecycle=lifecycle,
            skip=skip,
            limit=limit,
            filters=active_filters,
            assignment_clause=assignment_clause,
        )
        return build_project_reads(db, projects)

    def get_archived_list(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        assignment_clause=None,
    ) -> list[ArchivedProjectListItem]:
        projects = self.query_projects(
            db,
            lifecycle=ProjectLifecycleFilter.archived,
            skip=skip,
            limit=limit,
            assignment_clause=assignment_clause,
        )
        items: list[ArchivedProjectListItem] = []
        for project in projects:
            read = build_project_read(db, project)
            customer = db.get(Customer, project.customer_id)
            project_type = (
                db.get(ProjectType, project.project_type_id)
                if project.project_type_id
                else None
            )
            leader = db.get(User, project.design_leader_id)
            leader_name = (
                f"{leader.first_name} {leader.last_name}" if leader else "Unknown"
            )
            items.append(
                ArchivedProjectListItem(
                    **read.model_dump(),
                    customer_name=customer.name if customer else "Unknown",
                    project_type_name=project_type.name if project_type else None,
                    design_leader_name=leader_name,
                )
            )
        return items


project = CRUDProject(Project)
