"""Team membership date windows for timesheet report scoping."""

from __future__ import annotations

import json
from datetime import date, timedelta
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


def _member_effective_from(member: TeamMember) -> date | None:
    """Explicit membership start only — never ``joined_at`` (row-created / rewritten)."""
    return member.effective_from


def _transfer_start_floors(
    db: Session,
    team_ids: frozenset[UUID] | set[UUID],
    *,
    range_end: date,
) -> dict[tuple[UUID, UUID], date]:
    """Latest recorded transfer onto each (user, team)."""
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


def _prior_home_ended_day_before(
    db: Session,
    *,
    user_ids: set[UUID],
) -> set[tuple[UUID, date]]:
    """Pairs (user_id, day_after_prior_end) where a primary stint ended the day before.

    Used to confirm ``TeamMember.effective_from`` is a real transfer onto a new
    home rather than a stale joined_at-style backfill that must not clip hours.
    """
    if not user_ids:
        return set()
    rows = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id.in_(tuple(user_ids)),
            TeamMembershipPeriod.is_primary.is_(True),
            TeamMembershipPeriod.effective_to.is_not(None),
        )
    ).all()
    return {(row.user_id, row.effective_to + timedelta(days=1)) for row in rows}


def _stint_floors_for_members(
    db: Session,
    members: list[TeamMember],
    *,
    team_ids: frozenset[UUID] | set[UUID],
    range_end: date,
) -> dict[tuple[UUID, UUID], date]:
    """Floors that may raise open stints / exclude future roster rows.

    Sources:
    - ``UserJobEvent`` transfers onto the team
    - ``TeamMember.effective_from`` only when a prior primary home ended the day
      before (dated transfer via Teams UI without a job event)
    """
    floors = _transfer_start_floors(db, team_ids, range_end=range_end)
    user_ids = {member.user_id for member in members}
    prior_starts = _prior_home_ended_day_before(db, user_ids=user_ids)
    for member in members:
        effective = _member_effective_from(member)
        if effective is None:
            continue
        key = (member.user_id, member.team_id)
        if key in floors:
            if effective > floors[key]:
                floors[key] = effective
            continue
        if (member.user_id, effective) in prior_starts:
            floors[key] = effective
    return floors


def _clip_period(
    *,
    period_start: date,
    period_to: date | None,
    floor: date | None,
    range_start: date,
    range_end: date,
) -> tuple[date, date] | None:
    """Clip one membership period into the report range.

    - Open stints are raised to ``floor`` (transfer onto this team).
    - Closed periods ending the day before ``floor`` are destination backfill
      artifacts and are skipped.
    - Other closed history is kept so prior stints (and non-transfer teams)
      are not rewritten by a live ``effective_from``.
    """
    is_open = period_to is None
    p_end = range_end if is_open else period_to
    assert p_end is not None
    start = period_start

    if floor is not None:
        if not is_open and period_to == floor - timedelta(days=1):
            return None
        if is_open or p_end >= floor:
            if start < floor:
                start = floor

    if p_end < range_start or start > range_end:
        return None
    clipped_start = max(start, range_start)
    clipped_end = min(p_end, range_end)
    if clipped_start > clipped_end:
        return None
    return clipped_start, clipped_end


def _open_period_start_for_report(
    *,
    period_start: date,
    floor: date | None,
    joining_date: date | None,
    range_start: date,
    notes: str | None,
) -> date:
    """Resolve the open-stint start used for timesheet hour attribution.

    Phase-36 backfill / reconcile often copied ``TeamMember.joined_at`` into
    ``effective_from``, which then raised the open period start mid-month and
    hid early-month entries for people who never transferred. Without a
    verified transfer floor, only trust a mid-range start when joining_date or
    period notes show an intentional dated assign/transfer.
    """
    if floor is not None:
        return period_start
    if period_start <= range_start:
        return period_start
    notes_l = (notes or "").lower()
    if "transfer" in notes_l or "primary assign" in notes_l:
        return period_start
    if joining_date is not None and joining_date > range_start:
        return max(period_start, joining_date)
    return range_start


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

    Open / current stints may be floored to a verified transfer-onto date so a
    mid-month move never attributes earlier hours to the destination team —
    even when a backfilled period still starts at hire date.

    ``User.team_id`` alone never invents full-range coverage for a month the
    person had not yet joined (that duplicated July hours onto Eng 3 after an
    August transfer).

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
    stint_floors = _stint_floors_for_members(
        db, members, team_ids=team_ids, range_end=range_end
    )
    live_starts = {
        (member.user_id, member.team_id): member.effective_from
        for member in members
        if member.effective_from is not None
    }

    period_stmt = select(TeamMembershipPeriod).where(
        TeamMembershipPeriod.team_id.in_(team_tuple),
        TeamMembershipPeriod.effective_from <= range_end,
    )
    if primary_only:
        period_stmt = period_stmt.where(TeamMembershipPeriod.is_primary.is_(True))
    periods = db.scalars(period_stmt).all()
    period_user_ids = {period.user_id for period in periods} | {
        member.user_id for member in members
    }
    joining_by_user: dict[UUID, date | None] = {}
    if period_user_ids:
        for person in db.scalars(select(User).where(User.id.in_(tuple(period_user_ids)))).all():
            joining_by_user[person.id] = person.joining_date

    users_with_period_on_team: set[tuple[UUID, UUID]] = set()
    for period in periods:
        live_start = live_starts.get((period.user_id, period.team_id))
        # Open stint on a team the person only joins after this report window
        # (e.g. Aug 1 transfer while viewing July) must not cover the month —
        # including hire-date backfills that never got floored.
        if (
            period.effective_to is None
            and live_start is not None
            and live_start > range_end
        ):
            continue
        floor = stint_floors.get((period.user_id, period.team_id))
        period_start = period.effective_from
        if period.effective_to is None:
            period_start = _open_period_start_for_report(
                period_start=period.effective_from,
                floor=floor,
                joining_date=joining_by_user.get(period.user_id),
                range_start=range_start,
                notes=period.notes,
            )
        clipped = _clip_period(
            period_start=period_start,
            period_to=period.effective_to,
            floor=floor,
            range_start=range_start,
            range_end=range_end,
        )
        if clipped is None:
            continue
        start, end = clipped
        users_with_period_on_team.add((period.user_id, period.team_id))
        windows.setdefault(period.user_id, []).append((start, end))

    # Fallback: live TeamMember rows without a covering period (legacy gaps).
    for member in members:
        if (member.user_id, member.team_id) in users_with_period_on_team:
            continue
        floor = stint_floors.get((member.user_id, member.team_id))
        if floor is not None and floor > range_end:
            # Transfer onto this team is after the report window.
            continue
        # Without a verified transfer floor, cover the full report range.
        # Do not use raw effective_from alone — backfills often copied joined_at.
        start = max(floor or range_start, range_start)
        end = range_end
        if start > end:
            continue
        windows.setdefault(member.user_id, []).append((start, end))

    # Do not invent windows from User.team_id. Current home after a later
    # transfer must not receive full historical months with no overlapping stint.

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
    team_ids_for_floors = {member.team_id for member in members}
    stint_floors = _stint_floors_for_members(
        db, members, team_ids=team_ids_for_floors, range_end=range_end
    )
    live_starts = {
        (member.user_id, member.team_id): member.effective_from
        for member in members
        if member.effective_from is not None
    }

    periods = db.scalars(
        select(TeamMembershipPeriod).where(
            TeamMembershipPeriod.user_id.in_(user_tuple),
            TeamMembershipPeriod.is_primary.is_(True),
            TeamMembershipPeriod.effective_from <= range_end,
        )
    ).all()
    joining_by_user: dict[UUID, date | None] = {
        person.id: person.joining_date
        for person in db.scalars(select(User).where(User.id.in_(user_tuple))).all()
    }

    timelines: dict[UUID, list[tuple[date, date, UUID]]] = {}
    users_with_period: set[UUID] = set()
    for period in periods:
        live_start = live_starts.get((period.user_id, period.team_id))
        if (
            period.effective_to is None
            and live_start is not None
            and live_start > range_end
        ):
            continue
        floor = stint_floors.get((period.user_id, period.team_id))
        period_start = period.effective_from
        if period.effective_to is None:
            period_start = _open_period_start_for_report(
                period_start=period.effective_from,
                floor=floor,
                joining_date=joining_by_user.get(period.user_id),
                range_start=range_start,
                notes=period.notes,
            )
        clipped = _clip_period(
            period_start=period_start,
            period_to=period.effective_to,
            floor=floor,
            range_start=range_start,
            range_end=range_end,
        )
        if clipped is None:
            continue
        start, end = clipped
        users_with_period.add(period.user_id)
        timelines.setdefault(period.user_id, []).append(
            (start, end, period.team_id)
        )

    for member in members:
        if member.user_id in users_with_period:
            continue
        floor = stint_floors.get((member.user_id, member.team_id))
        if floor is not None and floor > range_end:
            continue
        start = max(floor or range_start, range_start)
        end = range_end
        if start > end:
            continue
        timelines.setdefault(member.user_id, []).append(
            (start, end, member.team_id)
        )
        users_with_period.add(member.user_id)

    # Fallback: current User.team_id only when no membership history exists at all.
    missing = [uid for uid in user_ids if uid not in users_with_period]
    if missing:
        period_users = set(
            db.scalars(
                select(TeamMembershipPeriod.user_id).where(
                    TeamMembershipPeriod.user_id.in_(tuple(missing))
                )
            ).all()
        )
        for person in db.scalars(select(User).where(User.id.in_(tuple(missing)))).all():
            if person.id in period_users:
                # Has history elsewhere / outside range — do not invent coverage.
                continue
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
