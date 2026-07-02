from typing import Any
from uuid import UUID
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access_control import (
    parse_access_list,
    resolve_user_modules,
    resolve_user_special_permissions,
    serialize_module_access,
    serialize_special_permissions,
)
from app.core.permissions import get_role_name, project_assignment_filter
from app.core.security import hash_password
from app.crud.base import CRUDBase
from app.crud.team import sync_user_team_membership
from app.models.models import Project, Team, User
from app.models.foundation import Department
from app.schemas.identity import UserCreate, UserRead, UserUpdate


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
            "department_name": department_name,
            "manager_name": manager_name,
            "active_projects_count": count_user_active_projects(db, user),
            "module_access": parse_access_list(user.module_access),
            "special_permissions": parse_access_list(user.special_permissions),
            "resolved_modules": resolve_user_modules(user, role_name),
            "resolved_special_permissions": resolve_user_special_permissions(user, role_name),
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


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        data = _apply_access_payload(obj_in.model_dump(exclude={"password"}))
        team_id = data.pop("team_id", None)
        db_obj = User(
            **data,
            team_id=team_id,
            password_hash=hash_password(obj_in.password),
        )
        db.add(db_obj)
        db.flush()
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
        update_data = _apply_access_payload(update_data)
        updated = super().update(db, db_obj=db_obj, obj_in=update_data)
        if team_id_provided:
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
