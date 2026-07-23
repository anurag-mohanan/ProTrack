"""Team membership date windows for timesheet report scoping."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.models.models import TeamMember, TeamMembershipPeriod, Timesheet, TimesheetEntry, User


def membership_windows_for_teams(
    db: Session,
    team_ids: frozenset[UUID] | set[UUID],
    *,
    range_start: date,
    range_end: date,
) -> dict[UUID, list[tuple[date, date]]]:
    """
    Map user_id → inclusive date intervals overlapping [range_start, range_end]
    when the person was on one of the given teams.

    Future-dated transfers (effective_from after range_end) produce no window.
    """
    if not team_ids or range_start > range_end:
        return {}

    team_tuple = tuple(team_ids)
    windows: dict[UUID, list[tuple[date, date]]] = {}

    periods = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.team_id.in_(team_tuple),
            TeamMembershipPeriod.effective_from <= range_end,
        )
    ).all()

    users_with_period_on_team: set[tuple[UUID, UUID]] = set()
    for period in periods:
        p_end = period.effective_to or range_end
        if p_end < range_start:
            continue
        if period.effective_from > range_end:
            continue
        start = max(period.effective_from, range_start)
        end = min(p_end, range_end)
        if start > end:
            continue
        users_with_period_on_team.add((period.user_id, period.team_id))
        windows.setdefault(period.user_id, []).append((start, end))

    # Fallback: live TeamMember rows without a covering period (legacy / backfill gaps).
    members = db.scalars(
        select(TeamMember).where(TeamMember.team_id.in_(team_tuple))
    ).all()
    for member in members:
        if (member.user_id, member.team_id) in users_with_period_on_team:
            continue
        start_raw = member.effective_from
        if start_raw is not None and start_raw > range_end:
            # Future transfer onto this team — not yet in roster.
            continue
        start = max(start_raw or range_start, range_start)
        end = range_end
        if start > end:
            continue
        windows.setdefault(member.user_id, []).append((start, end))

    # Primary User.team_id with no membership row (rare) — treat as open membership.
    primary_users = db.scalars(select(User).where(User.team_id.in_(team_tuple))).all()
    for person in primary_users:
        if person.id in windows:
            continue
        windows[person.id] = [(range_start, range_end)]

    return {uid: _merge_intervals(intervals) for uid, intervals in windows.items()}


def users_on_teams_during(
    db: Session,
    team_ids: frozenset[UUID] | set[UUID],
    *,
    range_start: date,
    range_end: date,
) -> set[UUID]:
    return set(
        membership_windows_for_teams(
            db, team_ids, range_start=range_start, range_end=range_end
        ).keys()
    )


def entry_date_in_windows(entry_date: date, windows: list[tuple[date, date]] | None) -> bool:
    if not windows:
        return False
    return any(start <= entry_date <= end for start, end in windows)


def membership_entry_sql_clause(
    windows: dict[UUID, list[tuple[date, date]]],
) -> ColumnElement[bool]:
    """SQL filter: timesheet entry belongs to a user on a team membership day."""
    if not windows:
        return Timesheet.user_id.in_(())
    parts: list[ColumnElement[bool]] = []
    for user_id, intervals in windows.items():
        for start, end in intervals:
            parts.append(
                and_(
                    Timesheet.user_id == user_id,
                    TimesheetEntry.entry_date >= start,
                    TimesheetEntry.entry_date <= end,
                )
            )
    if not parts:
        return Timesheet.user_id.in_(())
    return or_(*parts)


def _merge_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda row: (row[0], row[1]))
    merged: list[tuple[date, date]] = [ordered[0]]
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end or (start - prev_end).days == 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged
