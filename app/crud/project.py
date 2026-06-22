from app.api.deps import HTTPException, status
from app.crud.base import CRUDBase, select
from app.models.enums import MilestoneStatus
from app.models.models import Contact, Milestone, Project, Role, User
from app.schemas.project import ProjectCreate, ProjectUpdate

DEFAULT_PROJECT_MILESTONES = (
    "Feasibility",
    "Blockout",
    "Roughing",
    "Intermediate Review",
    "Final Review",
    "File Release",
    "BOM Release",
)


def _dump_all_users(db) -> None:
    all_users = db.scalars(select(User)).all()
    print("ALL USERS IN DATABASE:")
    for u in all_users:
        print(
            f"id={u.id} "
            f"type={type(u.id)} "
            f"email={u.email} "
            f"active={u.is_active}"
        )


def _lookup_user(db, user_id):
    print("LOOKUP USER")
    print(f"user_id={user_id}")
    print(f"type={type(user_id)}")

    _dump_all_users(db)

    stmt = select(User).where(User.id == user_id)
    print(f"query={stmt}")

    result = db.scalar(stmt)

    print(f"result={result}")

    if result:
        print(f"result.id={result.id}")
        print(f"type(result.id)={type(result.id)}")
        print(f"result.role_id={result.role_id}")
        print(f"type(result.role_id)={type(result.role_id)}")

    return result


def _get_active_user(
    db,
    user_id,
    *,
    field_name: str,
    expected_role: str | None = None,
) -> User:
    print("========== GET ACTIVE USER ==========")
    print(f"field_name={field_name}")
    print(f"user_id={user_id}")
    print(f"type(user_id)={type(user_id)}")
    print(f"expected_role={expected_role}")

    user = _lookup_user(db, user_id)

    if user is None:
        print(f"DECISION: FAIL — no user found for {field_name} id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{field_name} must reference an active user "
                f"(no user found with id {user_id})"
            ),
        )

    print(f"DECISION: user found email={user.email} is_active={user.is_active}")

    if not user.is_active:
        print(f"DECISION: FAIL — user inactive for {field_name}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must reference an active user",
        )

    if expected_role:
        role = db.get(Role, user.role_id)
        role_name = role.name if role else None
        print(f"role lookup role_id={user.role_id} role={role_name}")
        if role is None or role.name != expected_role:
            print(
                f"DECISION: FAIL — role mismatch for {field_name}: "
                f"expected={expected_role!r} actual={role_name!r}"
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} must reference a user with the {expected_role} role",
            )
        print(f"DECISION: PASS — role matches {expected_role!r}")

    print(f"DECISION: PASS — {field_name} validated")
    return user


def _validate_project_references(
    db,
    *,
    customer_id,
    customer_contact_id,
    design_leader_id,
    designer_id=None,
    surfacer_id=None,
) -> None:
    print("========== PROJECT VALIDATION ==========")
    print(f"customer_id={customer_id} type={type(customer_id)}")
    print(f"customer_contact_id={customer_contact_id} type={type(customer_contact_id)}")
    print(f"design_leader_id={design_leader_id} type={type(design_leader_id)}")
    print(f"designer_id={designer_id} type={type(designer_id)}")
    print(f"surfacer_id={surfacer_id} type={type(surfacer_id)}")

    contact = db.scalar(select(Contact).where(Contact.id == customer_contact_id))
    print(f"contact lookup result={contact}")
    if contact is None or contact.customer_id != customer_id:
        print("DECISION: FAIL — customer_contact_id validation")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="customer_contact_id must belong to the selected customer_id",
        )
    print("DECISION: PASS — customer_contact_id validation")

    _get_active_user(
        db,
        design_leader_id,
        field_name="design_leader_id",
        expected_role="Design Leader",
    )

    if designer_id is not None:
        _get_active_user(
            db,
            designer_id,
            field_name="designer_id",
            expected_role="Designer",
        )

    if surfacer_id is not None:
        _get_active_user(
            db,
            surfacer_id,
            field_name="surfacer_id",
            expected_role="Surfacer",
        )

    print("DECISION: PASS — all project reference validations")


class CRUDProject(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    def create(self, db, *, obj_in: ProjectCreate) -> Project:
        print("PROJECT CREATE METHOD CALLED")
        print(f"obj_in.design_leader_id={obj_in.design_leader_id}")
        print(f"type(obj_in.design_leader_id)={type(obj_in.design_leader_id)}")
        print(f"obj_in.designer_id={obj_in.designer_id}")
        print(f"obj_in.surfacer_id={obj_in.surfacer_id}")

        data = obj_in.model_dump()
        print(f"model_dump design_leader_id={data['design_leader_id']}")
        print(f"type={type(data['design_leader_id'])}")

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

    def update(self, db, *, db_obj: Project, obj_in: ProjectUpdate) -> Project:
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


project = CRUDProject(Project)
