"""Resolve customer/team/user scope for engineering & timesheet report filters."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import User
from app.services.reporting.report_authorization import (
    ReportSubjectMode,
    actor_membership_team_ids,
    resolve_report_authority,
)
from app.services.reporting.team_membership_windows import (
    membership_windows_for_teams,
    users_on_teams_during,
)


@dataclass(frozen=True)
class ReportScope:
    """None team/user sets mean unrestricted (org-wide). Empty set means deny-all.

    ``subject_mode``:
      - unrestricted — no people/team clip
      - teams — roster is members of ``team_ids`` (refined by membership windows)
      - own — always ``user_ids == {actor_user_id}`` (never expand via refine)
    """

    customer_id: UUID | None = None
    team_ids: frozenset[UUID] | None = None
    user_ids: frozenset[UUID] | None = None
    # When team-scoped reports are built for a period: entry dates must fall in these windows.
    membership_windows: dict[UUID, list[tuple[date, date]]] | None = None
    stream_id: UUID | None = None
    subject_mode: ReportSubjectMode = ReportSubjectMode.teams
    actor_user_id: UUID | None = None


class ReportScopeForbidden(Exception):
    """Requested team/user is outside the caller's report authority."""


def resolve_report_scope(
    db: Session,
    user: User,
    *,
    customer_id: UUID | None = None,
    team_id: UUID | None = None,
    stream_id: UUID | None = None,
    range_start: date | None = None,
    range_end: date | None = None,
) -> ReportScope:
    auth = resolve_report_authority(db, user)

    if auth.own_only:
        if team_id is not None:
            membership = actor_membership_team_ids(db, user)
            if team_id not in membership:
                raise ReportScopeForbidden("Team is outside your accessible scope")
        return ReportScope(
            customer_id=customer_id,
            # None when no team filter so project clauses are not deny-all;
            # people are always clipped via user_ids.
            team_ids=frozenset({team_id}) if team_id is not None else None,
            user_ids=frozenset({user.id}),
            membership_windows=None,
            stream_id=stream_id,
            subject_mode=ReportSubjectMode.own,
            actor_user_id=user.id,
        )

    if auth.unrestricted:
        team_ids: frozenset[UUID] | None = frozenset({team_id}) if team_id is not None else None
    else:
        accessible = auth.team_ids or frozenset()
        if team_id is not None and team_id not in accessible:
            raise ReportScopeForbidden("Team is outside your accessible scope")
        team_ids = frozenset({team_id}) if team_id else frozenset(accessible)

    user_ids: frozenset[UUID] | None = None
    membership_windows: dict[UUID, list[tuple[date, date]]] | None = None
    if team_ids is not None:
        if range_start is not None and range_end is not None:
            membership_windows = membership_windows_for_teams(
                db, team_ids, range_start=range_start, range_end=range_end, primary_only=True
            )
            user_ids = frozenset(membership_windows.keys())
        else:
            # Period unknown yet — provisional roster (refined later with period dates).
            user_ids = frozenset(_users_on_teams(db, team_ids))

    return ReportScope(
        customer_id=customer_id,
        team_ids=team_ids,
        user_ids=user_ids,
        membership_windows=membership_windows,
        stream_id=stream_id,
        subject_mode=(
            ReportSubjectMode.unrestricted
            if auth.unrestricted and team_id is None
            else ReportSubjectMode.teams
        ),
        actor_user_id=user.id,
    )


def refine_scope_for_period(
    db: Session,
    scope: ReportScope,
    *,
    range_start: date,
    range_end: date,
) -> ReportScope:
    """Clip team roster + entry windows to membership dates overlapping the report period."""
    if scope.subject_mode == ReportSubjectMode.own:
        actor_id = scope.actor_user_id
        if actor_id is None:
            return scope
        return replace(scope, user_ids=frozenset({actor_id}))

    if scope.team_ids is None:
        return scope
    windows = membership_windows_for_teams(
        db, scope.team_ids, range_start=range_start, range_end=range_end, primary_only=True
    )
    return replace(
        scope,
        user_ids=frozenset(windows.keys()),
        membership_windows=windows,
    )


def _users_on_teams(db: Session, team_ids: frozenset[UUID]) -> set[UUID]:
    """Provisional roster without a date range (includes future-dated membership rows)."""
    if not team_ids:
        return set()
    # Prefer "today" so future transfers are excluded even before period refine.
    today = date.today()
    return users_on_teams_during(db, team_ids, range_start=today, range_end=today)


def user_matches_scope(db: Session, user: User, scope: ReportScope) -> bool:
    if scope.user_ids is None:
        return True
    # user_ids is the dated roster (membership windows) when team-scoped — do not
    # re-include people who only have a future-dated TeamMember row on the team.
    return user.id in scope.user_ids
