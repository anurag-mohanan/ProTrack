"""Human Resources module shell — read-focused views."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import MODULE_HUMAN_RESOURCES
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name
from app.core.team_access import get_accessible_team_ids, team_member_user_ids
from app.models.enums import TimesheetStatus
from app.models.models import Team, Timesheet, User
from app.services.user_team_service import get_user_team_ids

router = APIRouter(prefix="/hr", tags=["human-resources"])


def _require_hr_view(db: Session, user: User) -> None:
    role_name = get_role_name(db, user)
    if not user_has_module_action(user, role_name, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human Resources access required",
        )


@router.get("/dashboard")
def hr_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_view(db, current_user)
    accessible = get_accessible_team_ids(db, current_user)
    if accessible is None:
        team_ids = list(db.scalars(select(Team.id).where(Team.is_active.is_(True))).all())
    else:
        team_ids = list(accessible)

    member_ids = team_member_user_ids(db, team_ids) if team_ids else set()
    member_ids.add(current_user.id)

    pending_timesheets = int(
        db.scalar(
            select(func.count())
            .select_from(Timesheet)
            .where(
                Timesheet.user_id.in_(member_ids),
                Timesheet.status.in_((TimesheetStatus.draft, TimesheetStatus.submitted)),
            )
        )
        or 0
    )
    teams = db.scalars(select(Team).where(Team.id.in_(team_ids))).all() if team_ids else []
    users = (
        db.scalars(
            select(User).where(
                User.id.in_(member_ids),
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        ).all()
        if member_ids
        else []
    )

    return {
        "teams_managed": len(teams),
        "team_members": len(users),
        "pending_timesheets": pending_timesheets,
        "leave_placeholder": "Attendance and leave modules coming soon",
        "onboarding_placeholder": "Onboarding module coming soon",
        "teams": [{"id": str(team.id), "name": team.name} for team in teams],
        "users": [
            {
                "id": str(user.id),
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "team_ids": [str(tid) for tid in get_user_team_ids(db, user.id)],
            }
            for user in users
        ],
    }


@router.get("/teams")
def hr_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_view(db, current_user)
    accessible = get_accessible_team_ids(db, current_user)
    query = select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    if accessible is not None:
        if not accessible:
            return []
        query = query.where(Team.id.in_(accessible))
    return [
        {"id": str(team.id), "name": team.name, "colour": team.colour}
        for team in db.scalars(query).all()
    ]
