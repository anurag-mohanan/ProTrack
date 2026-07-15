from typing import Any
from uuid import UUID
import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.access_control import (
    parse_access_list,
    resolve_user_modules,
    resolve_user_special_permissions,
    serialize_module_access,
    serialize_special_permissions,
)
from app.core.permissions import get_role_name, project_assignment_filter
from app.core.timesheet_eligibility import default_requires_timesheet_for_role
from app.core.salary_eligibility import default_requires_salary_for_role
from app.core.pagination import PaginatedResponse, apply_sort
from app.core.security import hash_password
from app.crud.base import CRUDBase
from app.crud.team import sync_user_team_membership  # noqa: F401 — re-exported
from app.models.enums import TeamRelationshipType
from app.models.models import Project, Role, Team, TeamMember, User
from app.models.foundation import Department
from app.schemas.identity import (
    UserCreate,
    UserKpiConfiguration,
    UserRead,
    UserUpdate,
    UserTeamAssignmentRead,
)
from app.services.kpi_participation import apply_defaults_for_user, get_user_dashboard_profile
from app.services.user_team_service import (
    UserTeamAssignmentInput,
    list_user_team_assignments,
    sync_user_team_assignments,
)


def count_user_active_projects(db: Session, user: User) -> int:
    role_name = get_role_name(db, user)
    assignment_filter = project_assignment_filter(user, role_name)
    base_filters = (
        Project.is_deleted.is_(False),
        Project.is_archived.is_(False),
    )
    if assignment_filter is not None:
        condition = assignment_filter
    else:
        condition = (Project.designer_id == user.id) | (Project.design_leader_id == user.id)
    return int(
        db.scalar(
            select(func.count()).select_from(Project).where(condition, *base_filters)
        )
        or 0
    )


def build_user_read(db: Session, user: User) -> UserRead:
    role_name = get_role_name(db, user)
    team_name = None
    if user.team_id is not None:
        team = db.get(Team, user.team_id)
        team_name = team.name if team else None
    team_assignments: list[UserTeamAssignmentRead] = []
    team_names: list[str] = []
    for membership in list_user_team_assignments(db, user.id):
        team = db.get(Team, membership.team_id)
        if team is None:
            continue
        team_names.append(team.name)
        team_assignments.append(
            UserTeamAssignmentRead(
                id=membership.id,
                team_id=membership.team_id,
                team_name=team.name,
                relationship_type=membership.relationship_type,
                is_primary=membership.is_primary,
                include_in_timesheet_reports=bool(
                    getattr(membership, "include_in_timesheet_reports", True)
                ),
                created_at=membership.created_at,
            )
        )
    department_name = None
    if user.department_id is not None:
        department = db.get(Department, user.department_id)
        department_name = department.name if department else None
    manager_name = None
    if user.manager_id is not None:
        manager = db.get(User, user.manager_id)
        if manager is not None:
            manager_name = f"{manager.first_name} {manager.last_name}"
    return UserRead.model_validate(user, from_attributes=True).model_copy(
        update={
            "team_name": team_name,
            "team_names": team_names,
            "team_assignments": team_assignments,
            "department_name": department_name,
            "manager_name": manager_name,
            "active_projects_count": count_user_active_projects(db, user),
            "module_access": parse_access_list(user.module_access),
            "special_permissions": parse_access_list(user.special_permissions),
            "resolved_modules": resolve_user_modules(user, role_name),
            "resolved_special_permissions": resolve_user_special_permissions(user, role_name),
            "kpi_configuration": UserKpiConfiguration(
                operational_role_type_id=user.operational_role_type_id,
                operational_role_name=user.operational_role_type.name if user.operational_role_type else None,
                dashboard_profile=get_user_dashboard_profile(user),
                kpi_engineering_productivity=user.kpi_engineering_productivity,
                kpi_capacity_planning=user.kpi_capacity_planning,
                kpi_utilization=user.kpi_utilization,
                kpi_workload_planning=user.kpi_workload_planning,
                kpi_dashboard_productivity=user.kpi_dashboard_productivity,
            ),
        }
    )


def _apply_access_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    if "module_access" in payload:
        payload["module_access"] = serialize_module_access(payload.pop("module_access"))
    if "special_permissions" in payload:
        payload["special_permissions"] = serialize_special_permissions(
            payload.pop("special_permissions")
        )
    return payload


def _parse_team_assignments(raw: object) -> list[UserTeamAssignmentInput] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    parsed: list[UserTeamAssignmentInput] = []
    for row in raw:
        if isinstance(row, UserTeamAssignmentInput):
            parsed.append(row)
            continue
        if hasattr(row, "team_id"):
            relationship = getattr(row, "relationship_type", TeamRelationshipType.member)
            if isinstance(relationship, str):
                relationship = TeamRelationshipType(relationship)
            parsed.append(
                UserTeamAssignmentInput(
                    team_id=row.team_id,
                    relationship_type=relationship,
                    is_primary=bool(getattr(row, "is_primary", False)),
                    include_in_timesheet_reports=bool(
                        getattr(row, "include_in_timesheet_reports", True)
                    ),
                )
            )
            continue
        if isinstance(row, dict):
            relationship = row.get("relationship_type", TeamRelationshipType.member)
            if isinstance(relationship, str):
                relationship = TeamRelationshipType(relationship)
            parsed.append(
                UserTeamAssignmentInput(
                    team_id=row["team_id"],  # type: ignore[arg-type]
                    relationship_type=relationship,  # type: ignore[arg-type]
                    is_primary=bool(row.get("is_primary", False)),
                    include_in_timesheet_reports=bool(
                        row.get("include_in_timesheet_reports", True)
                    ),
                )
            )
    return parsed


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def _user_list_stmt(
        self,
        *,
        role_id: UUID | None = None,
        is_active: bool | None = None,
        include_archived: bool = False,
        include_deleted: bool = False,
        deleted_only: bool = False,
        search: str | None = None,
        team_id: UUID | None = None,
        employment_type: str | None = None,
    ):
        stmt = select(User)
        if deleted_only:
            stmt = stmt.where(User.is_deleted.is_(True))
        elif not include_deleted:
            stmt = stmt.where(User.is_deleted.is_(False))
        if not include_archived and not deleted_only:
            stmt = stmt.where(User.is_archived.is_(False))
        if role_id is not None:
            stmt = stmt.where(User.role_id == role_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if employment_type is not None:
            stmt = stmt.where(User.employment_type == employment_type)
        if team_id is not None:
            assigned_user_ids = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
            stmt = stmt.where(or_(User.team_id == team_id, User.id.in_(assigned_user_ids)))
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                    User.email.ilike(term),
                )
            )
        return stmt

    def query_users(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 25,
        role_id: UUID | None = None,
        is_active: bool | None = None,
        include_archived: bool = False,
        include_deleted: bool = False,
        deleted_only: bool = False,
        sort: str | None = None,
        search: str | None = None,
        team_id: UUID | None = None,
        employment_type: str | None = None,
    ) -> list[User]:
        stmt = self._user_list_stmt(
            role_id=role_id,
            is_active=is_active,
            include_archived=include_archived,
            include_deleted=include_deleted,
            deleted_only=deleted_only,
            search=search,
            team_id=team_id,
            employment_type=employment_type,
        )
        stmt = apply_sort(stmt, User, sort or "-created_at")
        return list(db.scalars(stmt.offset(skip).limit(limit)).all())

    def count_users(
        self,
        db: Session,
        *,
        role_id: UUID | None = None,
        is_active: bool | None = None,
        include_archived: bool = False,
        include_deleted: bool = False,
        deleted_only: bool = False,
        search: str | None = None,
        team_id: UUID | None = None,
        employment_type: str | None = None,
    ) -> int:
        stmt = self._user_list_stmt(
            role_id=role_id,
            is_active=is_active,
            include_archived=include_archived,
            include_deleted=include_deleted,
            deleted_only=deleted_only,
            search=search,
            team_id=team_id,
            employment_type=employment_type,
        )
        return int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    def query_users_paginated(
        self,
        db: Session,
        *,
        page: int = 1,
        page_size: int = 25,
        skip: int | None = None,
        limit: int | None = None,
        role_id: UUID | None = None,
        is_active: bool | None = None,
        include_archived: bool = False,
        include_deleted: bool = False,
        sort: str | None = None,
        search: str | None = None,
        team_id: UUID | None = None,
        employment_type: str | None = None,
    ) -> PaginatedResponse[Any]:
        resolved_skip = skip if skip is not None else (page - 1) * page_size
        resolved_limit = limit if limit is not None else page_size
        resolved_page = (resolved_skip // resolved_limit) + 1 if resolved_limit else page
        filter_kwargs = {
            "role_id": role_id,
            "is_active": is_active,
            "include_archived": include_archived,
            "include_deleted": include_deleted,
            "search": search,
            "team_id": team_id,
            "employment_type": employment_type,
        }
        total = self.count_users(db, **filter_kwargs)
        items = self.query_users(
            db,
            skip=resolved_skip,
            limit=resolved_limit,
            sort=sort,
            **filter_kwargs,
        )
        return PaginatedResponse.build(
            items=items,
            total=total,
            page=resolved_page,
            page_size=resolved_limit,
        )

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        data = _apply_access_payload(obj_in.model_dump(exclude={"password"}))
        team_assignments = data.pop("team_assignments", None)
        team_id = data.pop("team_id", None)
        role = db.get(Role, data["role_id"])
        role_name = role.name if role is not None else ""
        if data.get("requires_timesheet") is None:
            data["requires_timesheet"] = default_requires_timesheet_for_role(role_name)
        if data.get("requires_salary") is None:
            data["requires_salary"] = default_requires_salary_for_role(role_name)
        db_obj = User(
            **data,
            team_id=None,
            password_hash=hash_password(obj_in.password),
        )
        db.add(db_obj)
        db.flush()
        apply_defaults_for_user(
            db,
            db_obj,
            operational_role_type_id=data.get("operational_role_type_id"),
            reset_kpi_flags=not any(
                data.get(flag) is not None
                for flag in (
                    "kpi_engineering_productivity",
                    "kpi_capacity_planning",
                    "kpi_utilization",
                    "kpi_workload_planning",
                    "kpi_dashboard_productivity",
                )
            ),
        )
        if team_assignments is not None:
            sync_user_team_assignments(
                db,
                db_obj.id,
                assignments=_parse_team_assignments(team_assignments),
            )
        else:
            sync_user_team_membership(db, db_obj.id, team_id)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: User,
        obj_in: UserUpdate | dict[str, Any],
    ) -> User:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        password = update_data.pop("password", None)
        if password is not None:
            update_data["password_hash"] = hash_password(password)
            update_data["must_change_password"] = True
        team_id_provided = "team_id" in update_data
        team_id = update_data.pop("team_id", None) if team_id_provided else None
        team_assignments_provided = "team_assignments" in update_data
        team_assignments = update_data.pop("team_assignments", None)
        reset_kpi_defaults = update_data.pop("reset_kpi_defaults", False)
        role_changed = "role_id" in update_data
        requires_explicit = "requires_timesheet" in update_data
        salary_explicit = "requires_salary" in update_data
        if role_changed and not requires_explicit:
            new_role = db.get(Role, update_data["role_id"])
            if new_role is not None:
                update_data["requires_timesheet"] = default_requires_timesheet_for_role(
                    new_role.name
                )
        if role_changed and not salary_explicit:
            new_role = db.get(Role, update_data["role_id"])
            if new_role is not None:
                update_data["requires_salary"] = default_requires_salary_for_role(
                    new_role.name
                )
        update_data = _apply_access_payload(update_data)
        updated = super().update(db, db_obj=db_obj, obj_in=update_data)
        if reset_kpi_defaults or "operational_role_type_id" in update_data or role_changed:
            apply_defaults_for_user(
                db,
                updated,
                operational_role_type_id=updated.operational_role_type_id,
                reset_kpi_flags=reset_kpi_defaults,
            )
        if team_assignments_provided:
            sync_user_team_assignments(
                db,
                updated.id,
                assignments=_parse_team_assignments(team_assignments),
            )
            db.commit()
            db.refresh(updated)
        elif team_id_provided:
            sync_user_team_membership(db, updated.id, team_id)
            db.commit()
            db.refresh(updated)
        return updated

    def get_read(self, db: Session, record_id: UUID) -> UserRead | None:
        user = self.get(db, record_id)
        if user is None:
            return None
        return build_user_read(db, user)


user = CRUDUser(User)
