from typing import Any
from uuid import UUID

from app.api.deps import HTTPException, status
from app.crud.base import CRUDBase, Session, select
from app.crud.project_metrics import build_project_read
from app.models.enums import MilestoneStatus
from app.models.models import Contact, Milestone, Project, Role, User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

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
) -> User:
    user = _lookup_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{field_name} must reference an active user "
                f"(no user found with id {user_id})"
            ),
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must reference an active user",
        )

    if expected_role:
        role = db.get(Role, user.role_id)
        if role is None or role.name != expected_role:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{field_name} must reference a user with the "
                    f"{expected_role} role"
                ),
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="customer_contact_id must belong to the selected customer_id",
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
            expected_role="Designer",
        )

    if surfacer_id is not None:
        _ = _get_active_user(
            db,
            surfacer_id,
            field_name="surfacer_id",
            expected_role="Surfacer",
        )


class CRUDProject(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    def create(self, db: Session, *, obj_in: ProjectCreate) -> Project:
        data = obj_in.model_dump()
        _validate_project_references(
            db,
            customer_id=data["customer_id"],
            customer_contact_id=data["customer_contact_id"],
            design_leader_id=data["design_leader_id"],
            designer_id=data.get("designer_id"),
            surfacer_id=data.get("surfacer_id"),
        )

        db_obj = Project(**data)
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
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: Project,
        obj_in: ProjectUpdate | dict[str, Any],
    ) -> Project:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        _validate_project_references(
            db,
            customer_id=update_data.get("customer_id", db_obj.customer_id),
            customer_contact_id=update_data.get(
                "customer_contact_id", db_obj.customer_contact_id
            ),
            design_leader_id=update_data.get(
                "design_leader_id", db_obj.design_leader_id
            ),
            designer_id=update_data.get("designer_id", db_obj.designer_id),
            surfacer_id=update_data.get("surfacer_id", db_obj.surfacer_id),
        )

        return super().update(db, db_obj=db_obj, obj_in=update_data)

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
        filters: dict[str, Any] | None = None,
    ) -> list[ProjectRead]:
        projects = self.get_multi(db, skip=skip, limit=limit, filters=filters)
        return [build_project_read(db, row) for row in projects]


project = CRUDProject(Project)
