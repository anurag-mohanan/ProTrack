"""Human Resources module — team visibility and timesheet completion monitoring."""

from __future__ import annotations

from datetime import date, timedelta

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
from app.models.models import Team, Timesheet, TimesheetEntry, User
from app.services.timesheet_compliance_service import get_missing_timesheet_rows
from app.services.user_team_service import get_user_team_ids

router = APIRouter(prefix="/hr", tags=["human-resources"])


def _require_hr_view(db: Session, user: User) -> None:
    role_name = get_role_name(db, user)
    if not user_has_module_action(user, role_name, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human Resources access required",
        )


def _scoped_member_ids(db: Session, current_user: User) -> tuple[list, set]:
    accessible = get_accessible_team_ids(db, current_user)
    if accessible is None:
        team_ids = list(db.scalars(select(Team.id).where(Team.is_active.is_(True))).all())
    else:
        team_ids = list(accessible)
    member_ids = team_member_user_ids(db, team_ids) if team_ids else set()
    member_ids.add(current_user.id)
    return team_ids, member_ids


@router.get("/dashboard")
def hr_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_view(db, current_user)
    team_ids, member_ids = _scoped_member_ids(db, current_user)

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
            ).order_by(User.last_name, User.first_name)
        ).all()
        if member_ids
        else []
    )

    missing = [
        row
        for row in get_missing_timesheet_rows(db, min_missing_days=1, limit=200)
        if row.user_id in member_ids
    ]

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    user_status = []
    for user in users:
        latest = db.scalar(
            select(Timesheet)
            .where(Timesheet.user_id == user.id)
            .order_by(Timesheet.week_start.desc())
            .limit(1)
        )
        hours_this_week = db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id == user.id,
                TimesheetEntry.is_deleted.is_(False),
                TimesheetEntry.entry_date >= week_start,
                TimesheetEntry.entry_date <= today,
            )
        )
        missing_row = next((row for row in missing if row.user_id == user.id), None)
        user_status.append(
            {
                "id": str(user.id),
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "team_ids": [str(tid) for tid in get_user_team_ids(db, user.id)],
                "latest_timesheet_status": latest.status.value if latest else "none",
                "latest_week_start": latest.week_start.isoformat() if latest else None,
                "hours_this_week": float(hours_this_week or 0),
                "missing_days": missing_row.missing_days if missing_row else 0,
                "last_entry_date": (
                    missing_row.last_entry_date.isoformat()
                    if missing_row and missing_row.last_entry_date
                    else None
                ),
                "needs_attention": bool(
                    missing_row and missing_row.missing_days >= 3
                )
                or (latest is not None and latest.status == TimesheetStatus.draft),
            }
        )

    attention = [row for row in user_status if row["needs_attention"]]
    attention.sort(key=lambda row: (-row["missing_days"], row["name"]))

    return {
        "teams_managed": len(teams),
        "team_members": len(users),
        "pending_timesheets": pending_timesheets,
        "users_needing_attention": len(attention),
        "leave_placeholder": "Attendance and leave modules coming soon",
        "onboarding_placeholder": "Onboarding module coming soon",
        "teams": [{"id": str(team.id), "name": team.name} for team in teams],
        "users": user_status,
        "timesheet_attention": attention,
    }


@router.get("/timesheet-compliance")
def hr_timesheet_compliance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List users in accessible teams who are behind on timesheet entry."""
    _require_hr_view(db, current_user)
    _, member_ids = _scoped_member_ids(db, current_user)
    rows = [
        {
            "user_id": str(row.user_id),
            "employee_name": row.employee_name,
            "last_entry_date": row.last_entry_date.isoformat() if row.last_entry_date else None,
            "missing_days": row.missing_days,
        }
        for row in get_missing_timesheet_rows(db, min_missing_days=1, limit=200)
        if row.user_id in member_ids
    ]
    return {"items": rows, "total": len(rows)}


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
