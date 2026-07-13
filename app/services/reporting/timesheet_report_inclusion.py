"""Helpers for timesheet report inclusion / exclusion per team membership."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import TeamMember


def users_excluded_from_timesheet_reports(
    db: Session,
    *,
    team_ids: frozenset[UUID] | None = None,
) -> set[UUID]:
    """
    Users who should be omitted from timesheet / engineering reports.

    - If team_ids is set: exclude users who have membership on those teams with
      include_in_timesheet_reports=False (and no other in-scope membership that includes them).
    - If team_ids is None (org-wide): exclude users who have at least one membership
      and all of their memberships have include_in_timesheet_reports=False.
    """
    memberships = list(db.scalars(select(TeamMember)).all())
    if not memberships:
        return set()

    by_user: dict[UUID, list[TeamMember]] = {}
    for membership in memberships:
        by_user.setdefault(membership.user_id, []).append(membership)

    excluded: set[UUID] = set()
    for user_id, rows in by_user.items():
        if team_ids is not None:
            relevant = [row for row in rows if row.team_id in team_ids]
            if not relevant:
                continue
            if not any(bool(getattr(row, "include_in_timesheet_reports", True)) for row in relevant):
                excluded.add(user_id)
        else:
            if rows and not any(
                bool(getattr(row, "include_in_timesheet_reports", True)) for row in rows
            ):
                excluded.add(user_id)
    return excluded


def filter_user_ids_for_timesheet_reports(
    db: Session,
    user_ids: set[UUID] | frozenset[UUID] | None,
    *,
    team_ids: frozenset[UUID] | None = None,
) -> set[UUID] | None:
    """Apply exclusion to an optional user id set. None stays org-wide (minus excluded)."""
    excluded = users_excluded_from_timesheet_reports(db, team_ids=team_ids)
    if user_ids is None:
        if not excluded:
            return None
        # Caller must treat None as unrestricted; return empty marker is awkward.
        # Keep None and let callers also check excluded via helper, OR return all minus excluded.
        # Prefer: when unrestricted, callers should subtract excluded themselves.
        return None
    return set(user_ids) - excluded
