"""Team membership date windows for timesheet report scoping."""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.models.models import (
    TeamMember,
    TeamMembershipPeriod,
    Timesheet,
    TimesheetEntry,
    User,
    UserJobEvent,
)

_TRANSFER_EVENT = "transfer"


def _member_start_floor(member: TeamMember) -> date | None:
    """Earliest day this live membership row should count for the current stint."""
    if member.effective_from is not None:
        return member.effective_from
    joined = getattr(member, "joined_at", None)
    if joined is not None:
        return joined.date() if hasattr(joined, "date") else joined
    return None


def _transfer_start_floors(
    db: Session,
    team_ids: frozenset[UUID] | set[UUID],
    *,
    range_end: date,
) -> dict[tuple[UUID, UUID], date]:
    """Latest recorded transfer onto each (user, team), used to correct stale periods."""
    team_set = set(team_ids)
    if not team_set:
        return {}
    floors: dict[tuple[UUID, UUID], date] = {}
    events = db.scalars(
        select(UserJobEvent).where(
            UserJobEvent.event_type == _TRANSFER_EVENT,
            UserJobEvent.effective_date <= range_end,
        )
    ).all()
    for event in events:
        try:
            payload = json.loads(event.to_value or "{}")
        except json.JSONDecodeError:
            continue
        raw_team = payload.get("team_id")
        if raw_team is None:
            continue
        try:
            team_id = UUID(str(raw_team))
        except (TypeError, ValueError):
            continue
        if team_id not in team_set:
            continue
        key = (event.user_id, team_id)
        prev = floors.get(key)
        if prev is None or event.effective_date > prev:
            floors[key] = event.effective_date
    return floors


def membership_windows_for_teams(
    db: Session,
    team_ids: frozenset[UUID] | set[UUID],
    *,
    range_start: date,
    range_end: date,
    primary_only: bool = False,
) -> dict[UUID, list[tuple[date, date]]]:
    """
    Map user_id → inclusive date intervals overlapping [range_start, range_end]
    when the person was on one of the given teams.

    Future-dated transfers (effective_from after range_end) produce no window.

    Open / current stints are floored to ``TeamMember.effective_from`` (then
    ``joined_at``, then the latest transfer job event onto that team) so a
    mid-month move never attributes earlier hours to the destination team —
    even when a backfilled period still starts at hire date.

    When ``primary_only`` is True, only primary-home memberships / periods are
    used — required for timesheet hour attribution so secondary multi-team
    memberships do not duplicate the same hours under every team.
    """
    if not team_ids or range_start > range_end:
        return {}

    team_tuple = tuple(team_ids)
    windows: dict[UUID, list[tuple[date, date]]] = {}

    member_stmt = select(TeamMember).where(TeamMember.team_id.in_(team_tuple))
    if primary_only:
        member_stmt = member_stmt.where(TeamMember.is_primary.is_(True))
    members = list(db.scalars(member_stmt).all())
    member_floors: dict[tuple[UUID, UUID], date] = {}
    for member in members:
        floor = _member_start_floor(member)
        if floor is not None:
            member_floors[(member.user_id, member.team_id)] = floor

    transfer_floors = _transfer_start_floors(db, team_ids, range_end=range_end)
    for key, transfer_on in transfer_floors.items():
        prev = member_floors.get(key)
        if prev is None or transfer_on > prev:
            member_floors[key] = transfer_on

    period_stmt = select(TeamMembershipPeriod).where(
        TeamMembershipPeriod.team_id.in_(team_tuple),
        TeamMembershipPeriod.effective_from <= range_end,
    )
    if primary_only:
        period_stmt = period_stmt.where(TeamMembershipPeriod.is_primary.is_(True))
    periods = db.scalars(period_stmt).all()

    users_with_period_on_team: set[tuple[UUID, UUID]] = set()
    for period in periods:
        p_end = period.effective_to or range_end
        if p_end < range_start:
            continue
        period_start = period.effective_from
        # Floor every stint to the live membership / transfer-onto date.
        # Closing a hire-date backfill on the destination (effective_to =
        # day-before-transfer) used to leave a closed period that merged with
        # the real post-transfer stint and pulled pre-transfer hours onto the
        # new team — apply the floor to closed rows too and skip rows that end
        # entirely before the floor.
        floor = member_floors.get((period.user_id, period.team_id))
        if floor is not None:
            if p_end < floor:
                continue
            if floor > period_start:
                period_start = floor
        if period_start > range_end:
            continue
        start = max(period_start, range_start)
        end = min(p_end, range_end)
        if start > end:
            continue
        users_with_period_on_team.add((period.user_id, period.team_id))
        windows.setdefault(period.user_id, []).append((start, end))

    # Fallback: live TeamMember rows without a covering period (legacy / backfill gaps).
    for member in members:
        if (member.user_id, member.team_id) in users_with_period_on_team:
            continue
        start_raw = member_floors.get((member.user_id, member.team_id))
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


def home_team_id_on(
    timeline: list[tuple[date, date, UUID]] | None,
    as_of: date,
) -> UUID | None:
    """Return primary home team on ``as_of`` from a user timeline."""
    if not timeline:
        return None
    for start, end, team_id in timeline:
        if start <= as_of <= end:
            return team_id
    return None


def primary_home_team_timeline(
    db: Session,
    user_ids: set[UUID] | frozenset[UUID],
    *,
    range_start: date,
    range_end: date,
) -> dict[UUID, list[tuple[date, date, UUID]]]:
    """
    Map user_id → ordered primary-home intervals ``(start, end, team_id)`` clipped
    to ``[range_start, range_end]``.

    Uses ``TeamMembershipPeriod`` (same flooring rules as membership windows) so
    hours before a transfer stay on the previous team and hours from the transfer
    date onward attribute to the new team — even when ``User.team_id`` already
    points at the destination.
    """
    if not user_ids or range_start > range_end:
        return {}

    user_tuple = tuple(user_ids)
    members = list(
        db.scalars(
            select(TeamMember).where(
                TeamMember.user_id.in_(user_tuple),
                TeamMember.is_primary.is_(True),
            )
        ).all()
    )
    member_floors: dict[tuple[UUID, UUID], date] = {}
    team_ids_for_floors: set[UUID] = set()
    for member in members:
        team_ids_for_floors.add(member.team_id)
        floor = _member_start_floor(member)
        if floor is not None:
            member_floors[(member.user_id, member.team_id)] = floor

    transfer_floors = _transfer_start_floors(
        db, team_ids_for_floors, range_end=range_end
    )
    for key, transfer_on in transfer_floors.items():
        prev = member_floors.get(key)
        if prev is None or transfer_on > prev:
            member_floors[key] = transfer_on

    periods = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id.in_(user_tuple),
            TeamMembershipPeriod.is_primary.is_(True),
            TeamMembershipPeriod.effective_from <= range_end,
        )
    ).all()

    timelines: dict[UUID, list[tuple[date, date, UUID]]] = {}
    users_with_period: set[UUID] = set()
    for period in periods:
        p_end = period.effective_to or range_end
        if p_end < range_start:
            continue
        period_start = period.effective_from
        floor = member_floors.get((period.user_id, period.team_id))
        if floor is not None:
            if p_end < floor:
                continue
            if floor > period_start:
                period_start = floor
        if period_start > range_end:
            continue
        start = max(period_start, range_start)
        end = min(p_end, range_end)
        if start > end:
            continue
        users_with_period.add(period.user_id)
        timelines.setdefault(period.user_id, []).append(
            (start, end, period.team_id)
        )

    # Live primary membership without a covering period (legacy / backfill gaps).
    for member in members:
        if member.user_id in users_with_period:
            continue
        start_raw = member_floors.get((member.user_id, member.team_id))
        if start_raw is not None and start_raw > range_end:
            continue
        start = max(start_raw or range_start, range_start)
        end = range_end
        if start > end:
            continue
        timelines.setdefault(member.user_id, []).append(
            (start, end, member.team_id)
        )
        users_with_period.add(member.user_id)

    # Fallback: current User.team_id when no membership history exists.
    missing = [uid for uid in user_ids if uid not in users_with_period]
    if missing:
        for person in db.scalars(select(User).where(User.id.in_(tuple(missing)))).all():
            if person.team_id is None:
                continue
            timelines[person.id] = [(range_start, range_end, person.team_id)]

    return {
        uid: _merge_team_intervals(intervals)
        for uid, intervals in timelines.items()
    }


def _merge_team_intervals(
    intervals: list[tuple[date, date, UUID]],
) -> list[tuple[date, date, UUID]]:
    """Merge adjacent/overlapping intervals only when they share the same team."""
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda row: (row[0], row[1], str(row[2])))
    merged: list[tuple[date, date, UUID]] = [ordered[0]]
    for start, end, team_id in ordered[1:]:
        prev_start, prev_end, prev_team = merged[-1]
        if team_id == prev_team and (
            start <= prev_end or (start - prev_end).days == 1
        ):
            merged[-1] = (prev_start, max(prev_end, end), team_id)
        else:
            merged.append((start, end, team_id))
    return merged


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
