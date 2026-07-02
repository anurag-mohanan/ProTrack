"""User profile aggregation for the self-service profile page."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import get_role_name
from app.crud.preferences import get_or_create_user_preferences
from app.crud.user import build_user_read
from app.models.foundation import UserSkill
from app.models.models import Project, Timesheet, User
from app.schemas.auth import UserPreferencesSnapshot, UserProfileRead, UserProfileSkill, UserProfileSummary


def get_user_profile(db: Session, user: User) -> UserProfileRead:
    user_read = build_user_read(db, user)
    prefs = get_or_create_user_preferences(db, user)

    skills = db.scalars(
        select(UserSkill).where(UserSkill.user_id == user.id)
    ).all()
    skill_rows = [
        UserProfileSkill(
            skill_id=row.skill_id,
            skill_name=row.skill.name if row.skill else None,
            proficiency=row.proficiency.value,
        )
        for row in skills
    ]

    active_projects = db.scalar(
        select(func.count())
        .select_from(Project)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            (Project.designer_id == user.id) | (Project.design_leader_id == user.id),
        )
    ) or 0

    quoted_hours = db.scalar(
        select(func.coalesce(func.sum(Project.quoted_hours), 0))
        .select_from(Project)
        .where(
            Project.is_deleted.is_(False),
            Project.designer_id == user.id,
        )
    ) or Decimal("0")

    actual_hours = db.scalar(
        select(func.coalesce(func.sum(Project.actual_hours), 0))
        .select_from(Project)
        .where(
            Project.is_deleted.is_(False),
            Project.designer_id == user.id,
        )
    ) or Decimal("0")

    timesheet_count = db.scalar(
        select(func.count()).select_from(Timesheet).where(Timesheet.user_id == user.id)
    ) or 0

    utilization = Decimal("0")
    if quoted_hours > 0:
        utilization = (actual_hours / quoted_hours) * Decimal("100")

    return UserProfileRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        designation=user.designation,
        role_id=user.role_id,
        role_name=get_role_name(db, user),
        team_id=user.team_id,
        team_name=user_read.team_name,
        department_id=user.department_id,
        department_name=user_read.department_name,
        manager_id=user.manager_id,
        manager_name=user_read.manager_name,
        is_active=user.is_active,
        employment_type=user.employment_type.value if user.employment_type else None,
        working_hours_per_day=user.working_hours_per_day,
        working_days=user.working_days,
        availability_status=user.availability_status.value,
        skills=skill_rows,
        summary=UserProfileSummary(
            active_projects=int(active_projects),
            quoted_hours_assigned=quoted_hours,
            actual_hours_logged=actual_hours,
            utilization_percent=utilization.quantize(Decimal("0.01")),
            timesheet_count=int(timesheet_count),
        ),
        preferences=UserPreferencesSnapshot(
            theme_mode=prefs.theme_mode,
            sidebar_expanded=prefs.sidebar_expanded,
            sidebar_auto_collapse=prefs.sidebar_auto_collapse,
            dashboard_layout=prefs.dashboard_layout,
            table_density=prefs.table_density,
            font_size=prefs.font_size,
            animations_enabled=prefs.animations_enabled,
            reduced_motion=prefs.reduced_motion,
            default_landing_page=prefs.default_landing_page,
        ),
    )
