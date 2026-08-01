"""Past employees (leaving_date set) for HR roster views."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.models import ExitInterview, Team, TeamMembershipPeriod, User


def list_past_employees(
    db: Session,
    *,
    search: str | None = None,
) -> list[dict]:
    """Users with a last working day recorded (soft-offboard history retained)."""
    stmt = (
        select(User)
        .where(
            User.leaving_date.is_not(None),
            User.is_deleted.is_(False),
        )
        .order_by(User.leaving_date.desc(), User.last_name, User.first_name)
    )
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
                User.designation.ilike(term),
            )
        )
    users = list(db.scalars(stmt).all())
    if not users:
        return []

    user_ids = [u.id for u in users]
    periods = db.scalars(
        select(TeamMembershipPeriod)
        .where(TeamMembershipPeriod.user_id.in_(user_ids))
        .order_by(TeamMembershipPeriod.effective_from.desc())
    ).all()
    team_ids = {p.team_id for p in periods}
    teams = {
        t.id: t.name
        for t in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
    } if team_ids else {}

    periods_by_user: dict[UUID, list[TeamMembershipPeriod]] = {}
    for period in periods:
        periods_by_user.setdefault(period.user_id, []).append(period)

    interviews = db.scalars(
        select(ExitInterview)
        .where(
            ExitInterview.employee_user_id.in_(user_ids),
            ExitInterview.status == "completed",
        )
        .order_by(ExitInterview.completed_at.desc())
    ).all()
    interview_by_user: dict[UUID, ExitInterview] = {}
    for row in interviews:
        if row.employee_user_id and row.employee_user_id not in interview_by_user:
            interview_by_user[row.employee_user_id] = row

    today = date.today()
    out: list[dict] = []
    for user in users:
        user_periods = periods_by_user.get(user.id, [])
        team_names: list[str] = []
        seen: set[str] = set()
        for period in user_periods:
            name = teams.get(period.team_id)
            if name and name not in seen:
                seen.add(name)
                team_names.append(name)
        interview = interview_by_user.get(user.id)
        leaving = user.leaving_date
        out.append(
            {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "designation": user.designation,
                "joining_date": user.joining_date,
                "leaving_date": leaving,
                "is_archived": bool(user.is_archived),
                "is_active": bool(user.is_active),
                "offboard_applied_at": getattr(user, "offboard_applied_at", None),
                "has_left": bool(leaving and leaving <= today),
                "team_names": team_names,
                "exit_interview_id": interview.id if interview else None,
                "attitude_was_good": (
                    interview.attitude_was_good if interview is not None else None
                ),
                "skillset_rating": (
                    interview.skillset_rating if interview is not None else None
                ),
                "eligible_for_rehire": (
                    interview.eligible_for_rehire if interview is not None else None
                ),
            }
        )
    return out
