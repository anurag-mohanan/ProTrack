"""Shared authorization for report subjects (people + teams).

Timesheet reports are the first consumer. The same helpers should gate future
Project, Productivity, Financial, Capacity, and Customer report packs.

Rules (timesheet / people-scoped reports)
-----------------------------------------
- Team members          → self only
- Team leaders          → members of led teams only
- Department managers   → teams in their department envelope
- Engineering managers  → engineering portfolio (all teams when unscoped)
- Administrators        → unrestricted

Never trust frontend filters — always resolve authority server-side and clip
rosters / reject out-of-scope ``team_id`` / ``user_id`` parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.data_scope import DataScopeLevel, resolve_data_scope
from app.core.permissions import ENGINEERING_MANAGER, get_role_name, normalize_role_name
from app.core.team_access import get_accessible_team_ids, get_led_team_ids, team_member_user_ids
from app.models.enums import ActivityAction, EntityType
from app.models.models import User
from app.services.activity_service import log_activity
from app.services.user_team_service import get_user_team_ids


class ReportSubjectMode(str, Enum):
    """Who the actor may include as report subjects."""

    unrestricted = "unrestricted"
    teams = "teams"
    own = "own"


@dataclass(frozen=True)
class ReportAuthority:
    """Resolved report-subject envelope for the current actor."""

    mode: ReportSubjectMode
    # None = unrestricted; empty = no team portfolio (own-only)
    team_ids: frozenset[UUID] | None
    actor_user_id: UUID

    @property
    def unrestricted(self) -> bool:
        return self.mode == ReportSubjectMode.unrestricted

    @property
    def own_only(self) -> bool:
        return self.mode == ReportSubjectMode.own

    def allows_team(self, team_id: UUID) -> bool:
        if self.unrestricted:
            return True
        if self.own_only:
            # Own-only actors may still filter by a team they belong to.
            return False  # checked separately via membership
        if self.team_ids is None:
            return True
        return team_id in self.team_ids

    def allows_user(self, user_id: UUID, *, roster: frozenset[UUID] | None = None) -> bool:
        if user_id == self.actor_user_id:
            return True
        if self.unrestricted:
            return True
        if self.own_only:
            return False
        if roster is not None:
            return user_id in roster
        return False


def resolve_report_authority(db: Session, user: User) -> ReportAuthority:
    """Single source of truth for report people/team subject scope."""
    ctx = resolve_data_scope(db, user)
    if ctx.unrestricted:
        return ReportAuthority(
            mode=ReportSubjectMode.unrestricted,
            team_ids=None,
            actor_user_id=user.id,
        )

    role_name = normalize_role_name(get_role_name(db, user))

    # Department envelope (EM department fallback / future dept managers).
    if ctx.level == DataScopeLevel.department and ctx.team_ids:
        return ReportAuthority(
            mode=ReportSubjectMode.teams,
            team_ids=ctx.team_ids,
            actor_user_id=user.id,
        )

    # Engineering Manager: division portfolio (assigned/led) — not mere peer teams.
    if role_name == ENGINEERING_MANAGER:
        accessible = get_accessible_team_ids(db, user)
        if accessible is None:
            return ReportAuthority(
                mode=ReportSubjectMode.unrestricted,
                team_ids=None,
                actor_user_id=user.id,
            )
        return ReportAuthority(
            mode=ReportSubjectMode.teams,
            team_ids=frozenset(accessible),
            actor_user_id=user.id,
        )

    led = get_led_team_ids(db, user)
    if led:
        return ReportAuthority(
            mode=ReportSubjectMode.teams,
            team_ids=frozenset(led),
            actor_user_id=user.id,
        )

    return ReportAuthority(
        mode=ReportSubjectMode.own,
        team_ids=frozenset(),
        actor_user_id=user.id,
    )


def resolve_report_team_ids(db: Session, user: User) -> frozenset[UUID] | None:
    """Teams allowed in report filter dropdowns. None = all teams."""
    auth = resolve_report_authority(db, user)
    if auth.unrestricted:
        return None
    if auth.own_only:
        return frozenset()
    return auth.team_ids or frozenset()


def resolve_report_subject_user_ids(db: Session, user: User) -> set[UUID] | None:
    """People allowed in report employee pickers. None = unrestricted."""
    auth = resolve_report_authority(db, user)
    if auth.unrestricted:
        return None
    if auth.own_only:
        return {user.id}
    if not auth.team_ids:
        return {user.id}
    ids = team_member_user_ids(db, list(auth.team_ids))
    ids.add(user.id)
    return ids


def actor_membership_team_ids(db: Session, user: User) -> set[UUID]:
    """Teams the actor belongs to (for own-only team filter validation)."""
    ids = set(get_user_team_ids(db, user.id))
    if user.team_id is not None:
        ids.add(user.team_id)
    return ids


def assert_report_user_allowed(
    db: Session,
    user: User,
    subject_user_id: UUID | None,
    *,
    roster: frozenset[UUID] | None = None,
) -> None:
    """Raise ReportScopeForbidden when ``subject_user_id`` is out of scope."""
    from app.services.reporting.report_scope import ReportScopeForbidden

    if subject_user_id is None:
        return
    auth = resolve_report_authority(db, user)
    effective_roster = roster
    if effective_roster is None and auth.mode == ReportSubjectMode.teams and auth.team_ids:
        effective_roster = frozenset(team_member_user_ids(db, list(auth.team_ids)))
    if not auth.allows_user(subject_user_id, roster=effective_roster):
        raise ReportScopeForbidden("User is outside your report scope")


def log_report_generation(
    db: Session,
    *,
    user: User,
    report_type: str,
    filters: dict[str, Any] | None = None,
    team_id: UUID | None = None,
    filename: str | None = None,
    module: str = "reports_analytics",
) -> None:
    """Audit: who generated the report, when, filters, team, report type."""
    payload: dict[str, Any] = {
        "report_type": report_type,
        "filters": filters or {},
        "team_id": str(team_id) if team_id is not None else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if filename:
        payload["filename"] = filename
    log_activity(
        db,
        user=user,
        entity_type=EntityType.settings,
        entity_id=user.id,
        action=ActivityAction.data_exported,
        new_value=payload,
        outcome="success",
        module=module,
    )
