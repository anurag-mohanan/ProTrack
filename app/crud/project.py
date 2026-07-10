from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, override
from uuid import UUID

from sqlalchemy import Select, func
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ProTrackValidationError
from app.core.pagination import PaginatedResponse
from app.crud.base import CRUDBase, Session, select
from app.crud.project_metrics import build_project_read, build_project_reads
from app.models.enums import (
    EntityType,
    ExecutionStatus,
    NotificationType,
    ProjectHealth,
    ProjectLifecycleFilter,
)
from app.models.models import Contact, Customer, Project, Role, User
from app.schemas.project import ArchivedProjectListItem, ProjectCreate, ProjectRead, ProjectUpdate
from app.services.notification_service import create_notification
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


def _project_label(project: Project) -> str:
    return project.code or project.tool_number


def _normalize_optional_code(value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _integrity_error_message(exc: IntegrityError) -> str:
    raw = str(exc.orig).lower() if exc.orig is not None else str(exc).lower()
    if "tool_number" in raw:
        return "A project with this tool number already exists."
    if "code" in raw and "unique" in raw:
        return "A project with this project code already exists."
    return "Operation violates a database constraint."


def _safe_commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ProTrackValidationError(_integrity_error_message(exc)) from exc


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


def _validate_tool_number_unique(
    db: Session,
    tool_number: str,
    *,
    exclude_id: UUID | None = None,
) -> None:
    normalized = tool_number.strip()
    if not normalized:
        raise ProTrackValidationError("tool_number is required")

    existing = db.scalar(
        select(Project).where(
            func.lower(Project.tool_number) == normalized.lower(),
            Project.is_deleted.is_(False),
        )
    )
    if existing is not None and (exclude_id is None or existing.id != exclude_id):
        raise ProTrackValidationError(
            f"A project with tool number '{normalized}' already exists."
        )


def _validate_code_unique(
    db: Session,
    code: str | None,
    *,
    exclude_id: UUID | None = None,
) -> None:
    if code is None:
        return

    existing = db.scalar(
        select(Project).where(
            func.lower(Project.code) == code.lower(),
            Project.is_deleted.is_(False),
        )
    )
    if existing is not None and (exclude_id is None or existing.id != exclude_id):
        raise ProTrackValidationError(
            f"A project with project code '{code}' already exists."
        )


def _prepare_project_create(db: Session, obj_in: ProjectCreate) -> ProjectCreate:
    customer = db.get(Customer, obj_in.customer_id)
    if customer is None:
        raise ProTrackValidationError(
            "customer_id must reference an existing customer"
        )

    data = obj_in.model_dump()
    if data.get("team_id") is None and customer.default_team_id is not None:
        data["team_id"] = customer.default_team_id
    if (
        data.get("project_type_id") is None
        and customer.default_project_type_id is not None
    ):
        data["project_type_id"] = customer.default_project_type_id
    if (
        data.get("project_type_id") is not None
        and data.get("project_template_id") is None
        and customer.default_project_template_id is not None
    ):
        data["project_template_id"] = customer.default_project_template_id

    if data.get("working_model_id") is None and customer.default_working_model_id is not None:
        data["working_model_id"] = customer.default_working_model_id

    data["code"] = _normalize_optional_code(data.get("code"))

    if data.get("quoted_hours") is None:
        data["quoted_hours"] = Decimal("0")
    if data.get("execution_status") is None:
        data["execution_status"] = ExecutionStatus.planning

    return ProjectCreate(**data)


def _notify_project_assignments(
    db: Session,
    project: Project,
    *,
    previous_designer_id: UUID | None = None,
    previous_leader_id: UUID | None = None,
    previous_surfacer_id: UUID | None = None,
) -> None:
    label = _project_label(project)
    customer_name = project.customer.name if project.customer else ""
    email_context = {
        "ToolNumber": project.tool_number,
        "Customer": customer_name,
        "DueDate": str(project.due_date) if project.due_date else "",
        "PartDescription": project.part_description,
    }

    changes: list[tuple[UUID, str]] = []
    if project.designer_id is not None and project.designer_id != previous_designer_id:
        changes.append((project.designer_id, "designer"))
    if project.surfacer_id is not None and project.surfacer_id != previous_surfacer_id:
        changes.append((project.surfacer_id, "surfacer"))
    if project.design_leader_id is not None and project.design_leader_id != previous_leader_id:
        changes.append((project.design_leader_id, "design leader"))

    for user_id, role in changes:
        create_notification(
            db,
            user_id=user_id,
            notification_type=NotificationType.project_assigned,
            title="New project assignment",
            message=f"You were assigned to project {label} as {role}",
            entity_type=EntityType.project,
            entity_id=project.id,
            email_context=email_context,
        )


def _validate_project_references(
    db: Session,
    *,
    customer_id: UUID,
    customer_contact_id: UUID | None = None,
    design_leader_id: UUID | None = None,
    designer_id: UUID | None = None,
    surfacer_id: UUID | None = None,
) -> None:
    if customer_contact_id is not None:
        contact = db.scalar(select(Contact).where(Contact.id == customer_contact_id))
        if contact is None or contact.customer_id != customer_id:
            raise ProTrackValidationError(
                "customer_contact_id must belong to the selected customer_id"
            )

    if design_leader_id is not None:
        _ = _get_active_user(
            db,
            design_leader_id,
            field_name="design_leader_id",
        )

    if designer_id is not None:
        _ = _get_active_user(
            db,
            designer_id,
            field_name="designer_id",
        )

    if surfacer_id is not None:
        _ = _get_active_user(
            db,
            surfacer_id,
            field_name="surfacer_id",
        )


def _reference_ids_for_update(
    db_obj: Project,
    update_data: dict[str, object],
) -> tuple[UUID, UUID | None, UUID | None, UUID | None, UUID | None]:
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
        pick_optional_uuid("customer_contact_id", db_obj.customer_contact_id),
        pick_optional_uuid("design_leader_id", db_obj.design_leader_id),
        pick_optional_uuid("designer_id", db_obj.designer_id),
        pick_optional_uuid("surfacer_id", db_obj.surfacer_id),
    )


def _validate_changed_project_references(
    db: Session,
    db_obj: Project,
    update_data: dict[str, object],
) -> None:
    """Validate only the references whose value actually changes in an update."""
    (
        customer_id,
        customer_contact_id,
        design_leader_id,
        designer_id,
        surfacer_id,
    ) = _reference_ids_for_update(db_obj, update_data)

    customer_changed = (
        "customer_id" in update_data and customer_id != db_obj.customer_id
    )
    contact_changed = (
        "customer_contact_id" in update_data
        and customer_contact_id != db_obj.customer_contact_id
    )
    if customer_changed or contact_changed:
        if customer_contact_id is not None:
            contact = db.scalar(select(Contact).where(Contact.id == customer_contact_id))
            if contact is None or contact.customer_id != customer_id:
                raise ProTrackValidationError(
                    "customer_contact_id must belong to the selected customer_id"
                )

    if (
        "design_leader_id" in update_data
        and design_leader_id != db_obj.design_leader_id
        and design_leader_id is not None
    ):
        _ = _get_active_user(
            db,
            design_leader_id,
            field_name="design_leader_id",
        )

    if (
        "designer_id" in update_data
        and designer_id != db_obj.designer_id
        and designer_id is not None
    ):
        _ = _get_active_user(
            db,
            designer_id,
            field_name="designer_id",
        )

    if (
        "surfacer_id" in update_data
        and surfacer_id != db_obj.surfacer_id
        and surfacer_id is not None
    ):
        _ = _get_active_user(
            db,
            surfacer_id,
            field_name="surfacer_id",
        )


class CRUDProject(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    @override
    def create(self, db: Session, *, obj_in: ProjectCreate) -> Project:
        prepared = _prepare_project_create(db, obj_in)
        _validate_tool_number_unique(db, prepared.tool_number)
        _validate_code_unique(db, prepared.code)
        _validate_project_references(
            db,
            customer_id=prepared.customer_id,
            customer_contact_id=prepared.customer_contact_id,
            design_leader_id=prepared.design_leader_id,
            designer_id=prepared.designer_id,
            surfacer_id=prepared.surfacer_id,
        )

        db_obj = Project(**prepared.model_dump())
        db.add(db_obj)
        db.flush()

        if prepared.project_type_id is not None:
            template = resolve_template(
                db,
                project_type_id=prepared.project_type_id,
                customer_id=prepared.customer_id,
                template_id=prepared.project_template_id,
            )
            db_obj.project_template_id = template.id
            if db_obj.team_id is None and template.default_team_id is not None:
                db_obj.team_id = template.default_team_id
            create_milestones_from_template(
                db,
                project=db_obj,
                template=template,
            )
        else:
            db_obj.project_template_id = None

        _safe_commit(db)
        db.refresh(db_obj)
        recalculate_project(db, db_obj.id)
        _notify_project_assignments(db, db_obj)
        from app.services.email.engine import EmailService

        if db_obj.design_leader_id:
            leader = db.get(User, db_obj.design_leader_id)
            context = {
                "ToolNumber": db_obj.tool_number,
                "Customer": db_obj.customer.name if db_obj.customer else "",
                "DueDate": str(db_obj.due_date) if db_obj.due_date else "",
            }
            if leader and leader.email:
                EmailService(db).send_templated_email(
                    template_slug="project_created",
                    to_addresses=[leader.email],
                    context=context,
                    project_id=db_obj.id,
                    timeline_label="Project Created",
                )
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

        if "code" in update_data:
            update_data["code"] = _normalize_optional_code(update_data.get("code"))

        _validate_changed_project_references(db, db_obj, update_data)

        if "tool_number" in update_data and isinstance(update_data["tool_number"], str):
            _validate_tool_number_unique(
                db,
                update_data["tool_number"],
                exclude_id=db_obj.id,
            )

        next_code = (
            update_data["code"]
            if "code" in update_data
            else db_obj.code
        )
        if isinstance(next_code, str) or next_code is None:
            _validate_code_unique(db, next_code, exclude_id=db_obj.id)

        if "execution_status" in update_data:
            new_status = update_data["execution_status"]
            if new_status == ExecutionStatus.completed and db_obj.completed_at is None:
                update_data["completed_at"] = datetime.now(timezone.utc).replace(
                    tzinfo=None
                )
            elif new_status != ExecutionStatus.completed:
                update_data["completed_at"] = None

        previous_designer_id = db_obj.designer_id
        previous_leader_id = db_obj.design_leader_id
        previous_surfacer_id = db_obj.surfacer_id
        manual_health = update_data.get("health") if "health" in update_data else None

        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        _safe_commit(db)
        db.refresh(db_obj)
        recalculate_project(db, db_obj.id)
        if manual_health is not None:
            db_obj.health = manual_health
            db.add(db_obj)
            _safe_commit(db)
            db.refresh(db_obj)
        if "designer_id" in update_data or "design_leader_id" in update_data or "surfacer_id" in update_data:
            _notify_project_assignments(
                db,
                db_obj,
                previous_designer_id=previous_designer_id,
                previous_leader_id=previous_leader_id,
                previous_surfacer_id=previous_surfacer_id,
            )
        if "designer_id" in update_data or "surfacer_id" in update_data:
            from app.services.milestone_assignment_service import sync_milestone_assignments

            sync_milestone_assignments(db, db_obj.id)
        return db_obj

    def get_read(self, db: Session, record_id: UUID) -> ProjectRead | None:
        db_project = self.get(db, record_id)
        if db_project is None:
            return None
        return build_project_read(db, db_project)

    def _build_project_query(
        self,
        *,
        lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.all,
        filters: dict[str, Any] | None = None,
        assignment_clause=None,
    ) -> Select[tuple[Project]]:
        stmt: Select[tuple[Project]] = select(Project)
        stmt = apply_lifecycle_filter(stmt, lifecycle)
        if assignment_clause is not None:
            stmt = stmt.where(assignment_clause)
        if filters:
            multi_map = {
                "customer_ids": Project.customer_id,
                "team_ids": Project.team_id,
            }
            for field, value in filters.items():
                if field == "lifecycle" or value is None:
                    continue
                if field in multi_map and isinstance(value, list) and value:
                    stmt = stmt.where(multi_map[field].in_(value))
                    continue
                if field.endswith("_ids"):
                    continue
                if not hasattr(Project, field):
                    continue
                stmt = stmt.where(getattr(Project, field) == value)
        return stmt

    def count_projects(
        self,
        db: Session,
        *,
        lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.all,
        filters: dict[str, Any] | None = None,
        assignment_clause=None,
    ) -> int:
        stmt = self._build_project_query(
            lifecycle=lifecycle,
            filters=filters,
            assignment_clause=assignment_clause,
        )
        return int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    def query_projects(
        self,
        db: Session,
        *,
        lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.all,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        assignment_clause=None,
    ) -> list[Project]:
        stmt = self._build_project_query(
            lifecycle=lifecycle,
            filters=filters,
            assignment_clause=assignment_clause,
        )
        stmt = apply_lifecycle_sort(stmt, lifecycle).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def get_multi_read(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, object] | None = None,
        lifecycle: ProjectLifecycleFilter = ProjectLifecycleFilter.all,
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
        reads = build_project_reads(db, projects)
        for read in reads:
            payload = read.model_dump()
            payload["customer_name"] = read.customer_name or "Unknown"
            payload["design_leader_name"] = read.design_leader_name
            items.append(ArchivedProjectListItem(**payload))
        return items


project = CRUDProject(Project)
