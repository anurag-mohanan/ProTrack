from typing import override
from uuid import UUID

from app.core.exceptions import ProTrackValidationError
from app.core.permissions import PROJECT_STAFF_ROLES
from app.crud.base import CRUDBase, Session, select
from app.crud.project_metrics import build_project_read
from app.models.enums import MilestoneStatus
from app.models.models import Contact, Milestone, Project, Role, User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_calculation_service import recalculate_project

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

        for sort_order, name in enumerate(DEFAULT_PROJECT_MILESTONES, start=1):
            db.add(
                Milestone(
                    project_id=db_obj.id,
                    name=name,
                    status=MilestoneStatus.not_started,
                    sort_order=sort_order,
                )
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

    def get_multi_read(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, object] | None = None,
    ) -> list[ProjectRead]:
        projects = self.get_multi(db, skip=skip, limit=limit, filters=filters)
        return [build_project_read(db, row) for row in projects]


project = CRUDProject(Project)
