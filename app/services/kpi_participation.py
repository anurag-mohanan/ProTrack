"""Role-aware KPI participation and scope resolution."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.phase14_kpi_schema_sync import (
    ADMINISTRATION_ROLE_NAMES,
    ENGINEERING_ROLE_NAMES,
    MANAGEMENT_ROLE_NAMES,
    apply_operational_role_defaults,
    _infer_operational_code,
)
from app.models.models import OperationalRoleType, Role, User

KPI_FLAG_COLUMNS = {
    "engineering_productivity": User.kpi_engineering_productivity,
    "capacity_planning": User.kpi_capacity_planning,
    "utilization": User.kpi_utilization,
    "workload_planning": User.kpi_workload_planning,
    "dashboard_productivity": User.kpi_dashboard_productivity,
}


def _active_user_clause():
    return (
        User.is_active.is_(True),
        User.is_archived.is_(False),
        User.is_deleted.is_(False),
    )


def users_for_kpi_flag(db: Session, flag: str) -> list[User]:
    column = KPI_FLAG_COLUMNS.get(flag)
    if column is None:
        raise ValueError(f"Unknown KPI flag: {flag}")
    return list(
        db.scalars(
            select(User)
            .where(column.is_(True), *_active_user_clause())
            .order_by(User.last_name, User.first_name)
        ).all()
    )


def engineering_productivity_users(db: Session) -> list[User]:
    return users_for_kpi_flag(db, "engineering_productivity")


def capacity_planning_users(db: Session) -> list[User]:
    return users_for_kpi_flag(db, "capacity_planning")


def utilization_users(db: Session) -> list[User]:
    return users_for_kpi_flag(db, "utilization")


def workload_planning_users(db: Session) -> list[User]:
    return users_for_kpi_flag(db, "workload_planning")


def dashboard_productivity_users(db: Session) -> list[User]:
    return users_for_kpi_flag(db, "dashboard_productivity")


def kpi_user_ids_subquery(flag: str) -> Select:
    column = KPI_FLAG_COLUMNS[flag]
    return (
        select(User.id)
        .where(column.is_(True), *_active_user_clause())
    )


def resolve_operational_role_type(
    db: Session,
    *,
    operational_role_type_id=None,
    system_role_name: str | None = None,
) -> OperationalRoleType | None:
    if operational_role_type_id is not None:
        return db.get(OperationalRoleType, operational_role_type_id)
    if system_role_name:
        code = _infer_operational_code(system_role_name)
        return db.scalar(
            select(OperationalRoleType).where(
                OperationalRoleType.code == code,
                OperationalRoleType.is_active.is_(True),
            )
        )
    return None


def apply_defaults_for_user(
    db: Session,
    user: User,
    *,
    operational_role_type_id=None,
    system_role_name: str | None = None,
    reset_kpi_flags: bool = False,
) -> None:
    role_name = system_role_name
    if role_name is None and user.role_id:
        role = db.get(Role, user.role_id)
        role_name = role.name if role else None
    op_type = resolve_operational_role_type(
        db,
        operational_role_type_id=operational_role_type_id or user.operational_role_type_id,
        system_role_name=role_name,
    )
    if op_type is None:
        return
    if reset_kpi_flags or user.operational_role_type_id != op_type.id:
        apply_operational_role_defaults(user, op_type)
    else:
        user.operational_role_type_id = op_type.id

    if role_name == "Design Leader":
        user.kpi_engineering_productivity = True
        user.kpi_capacity_planning = True
        user.kpi_utilization = True
        user.kpi_workload_planning = True
        user.kpi_dashboard_productivity = True


def get_user_dashboard_profile(user: User) -> str:
    if user.operational_role_type and user.operational_role_type.dashboard_profile:
        return user.operational_role_type.dashboard_profile.value
    return "engineering"


def is_management_user(user: User) -> bool:
    if user.operational_role_type:
        return user.operational_role_type.dashboard_profile.value == "management"
    role_name = user.role.name if user.role else ""
    return role_name in MANAGEMENT_ROLE_NAMES


def is_administration_user(user: User) -> bool:
    if user.operational_role_type:
        return user.operational_role_type.dashboard_profile.value == "administration"
    role_name = user.role.name if user.role else ""
    return role_name in ADMINISTRATION_ROLE_NAMES or role_name == "Admin"


def is_engineering_kpi_user(user: User) -> bool:
    return bool(user.kpi_engineering_productivity)


__all__ = [
    "ENGINEERING_ROLE_NAMES",
    "MANAGEMENT_ROLE_NAMES",
    "ADMINISTRATION_ROLE_NAMES",
    "apply_defaults_for_user",
    "capacity_planning_users",
    "dashboard_productivity_users",
    "engineering_productivity_users",
    "get_user_dashboard_profile",
    "is_administration_user",
    "is_engineering_kpi_user",
    "is_management_user",
    "kpi_user_ids_subquery",
    "utilization_users",
    "users_for_kpi_flag",
    "workload_planning_users",
]
