"""Layer 2 data-scope authorization (team-aware record visibility).

Layer 1 — module access — lives in ``access_control`` / ``module_actions``
(can the user open Projects, Timesheets, Reports, …?).

Layer 2 — data scope — lives here (which *records* inside those modules?).

Scopes
------
``own``              Own assignments / own timesheets only
``own_team``         Single accessible team (+ own assignments)
``multiple_teams``   Several accessible teams
``department``       Teams linked to the user's org department (future-ready)
``company``          Entire company / tenant (executives, unscoped EM, …)
``administrator``    Unrestricted (Admin)

All entity visibility helpers should prefer this module so future multi-company,
tenant portals, and vendor portals extend one place — not ad-hoc filters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import EXECUTIVE_ROLES
from app.core.permissions import (
    ENGINEERING_MANAGER,
    PLANNING_BOARD,
    get_role_name,
    is_admin,
    normalize_role_name,
)
from app.models.models import Customer, Project, TeamMember, User


class DataScopeLevel(str, Enum):
    own = "own"
    own_team = "own_team"
    multiple_teams = "multiple_teams"
    department = "department"
    company = "company"
    administrator = "administrator"


@dataclass(frozen=True)
class DataScopeContext:
    """Resolved visibility envelope for the current actor."""

    level: DataScopeLevel
    # None = unrestricted (all teams in tenant)
    team_ids: frozenset[UUID] | None
    # Convenience: True when team_ids is None
    unrestricted: bool = False
    # Optional department id when level is department (future multi-company hooks)
    department_id: UUID | None = None
    # Tenant id for future multi-tenant / portal isolation (None = default tenant)
    tenant_id: UUID | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def allows_team(self, team_id: UUID | None) -> bool:
        if self.unrestricted:
            return True
        if team_id is None:
            return False
        if self.team_ids is None:
            return True
        return team_id in self.team_ids


def _department_linked_team_ids(db: Session, user: User) -> set[UUID]:
    """Teams touched by users in the same org department (best-effort)."""
    dept_id = getattr(user, "org_department_id", None)
    if dept_id is None:
        return set()
    dept_user_ids = set(
        db.scalars(select(User.id).where(User.org_department_id == dept_id)).all()
    )
    if not dept_user_ids:
        return set()
    team_ids = set(
        db.scalars(
            select(TeamMember.team_id).where(TeamMember.user_id.in_(dept_user_ids))
        ).all()
    )
    team_ids.update(
        db.scalars(
            select(User.team_id).where(
                User.id.in_(dept_user_ids),
                User.team_id.is_not(None),
            )
        ).all()
    )
    return {tid for tid in team_ids if tid is not None}


def resolve_data_scope(db: Session, user: User) -> DataScopeContext:
    """Resolve Layer-2 data scope for ``user`` (single source of truth)."""
    from app.core.team_access import get_accessible_team_ids, get_led_team_ids

    role_name = normalize_role_name(get_role_name(db, user))
    tenant_id = getattr(user, "tenant_id", None)

    if is_admin(db, user):
        return DataScopeContext(
            level=DataScopeLevel.administrator,
            team_ids=None,
            unrestricted=True,
            tenant_id=tenant_id,
            notes=("admin_unrestricted",),
        )

    if role_name == PLANNING_BOARD or role_name in EXECUTIVE_ROLES:
        return DataScopeContext(
            level=DataScopeLevel.company,
            team_ids=None,
            unrestricted=True,
            tenant_id=tenant_id,
            notes=("executive_or_planning_board",),
        )

    # HR / Office Admin: company-wide *timesheet* chase is handled in
    # timesheet_overview_service — project/customer/team data stays team-scoped.
    accessible = get_accessible_team_ids(db, user)
    if accessible is None:
        return DataScopeContext(
            level=DataScopeLevel.company,
            team_ids=None,
            unrestricted=True,
            tenant_id=tenant_id,
            notes=("unscoped_engineering_manager",),
        )

    led = get_led_team_ids(db, user)
    dept_id = getattr(user, "org_department_id", None)
    if not accessible and dept_id is not None and role_name == ENGINEERING_MANAGER:
        dept_teams = _department_linked_team_ids(db, user)
        if dept_teams:
            return DataScopeContext(
                level=DataScopeLevel.department,
                team_ids=frozenset(dept_teams),
                unrestricted=False,
                department_id=dept_id,
                tenant_id=tenant_id,
                notes=("department_fallback",),
            )

    if not accessible:
        return DataScopeContext(
            level=DataScopeLevel.own,
            team_ids=frozenset(),
            unrestricted=False,
            tenant_id=tenant_id,
            notes=("personal_assignment_only",),
        )

    frozen = frozenset(accessible)
    if len(frozen) == 1:
        level = DataScopeLevel.own_team
        notes = ("single_team",)
    else:
        level = DataScopeLevel.multiple_teams
        notes = ("multi_team",)
    if led:
        notes = notes + ("team_leader",)
    return DataScopeContext(
        level=level,
        team_ids=frozen,
        unrestricted=False,
        department_id=dept_id,
        tenant_id=tenant_id,
        notes=notes,
    )


def data_scope_to_dict(ctx: DataScopeContext) -> dict:
    return {
        "level": ctx.level.value,
        "unrestricted": ctx.unrestricted,
        "team_ids": [str(tid) for tid in sorted(ctx.team_ids, key=str)]
        if ctx.team_ids is not None
        else None,
        "department_id": str(ctx.department_id) if ctx.department_id else None,
        "tenant_id": str(ctx.tenant_id) if ctx.tenant_id else None,
        "notes": list(ctx.notes),
    }


# ---------------------------------------------------------------------------
# Entity helpers — reuse project_visibility / team APIs; do not fork filters
# ---------------------------------------------------------------------------


def project_visibility_for_user(db: Session, user: User):
    """SQLAlchemy clause for project list queries (None = unrestricted)."""
    from app.core.team_access import project_visibility_clause

    return project_visibility_clause(db, user)


def can_access_project(db: Session, user: User, project: Project) -> bool:
    from app.core.permissions import can_read_project

    return can_read_project(db, user, project)


def scoped_user_ids_for_actor(
    db: Session, user: User, *, include_self: bool = True
) -> set[UUID] | None:
    """User IDs the actor may see in people/timesheet lists.

    Returns None when unrestricted.
    """
    from app.core.team_access import get_accessible_team_ids, team_member_user_ids
    from app.services.timesheet_overview_service import get_timesheet_visible_user_ids

    # Prefer timesheet visibility (handles compliance / leader windows).
    visible = get_timesheet_visible_user_ids(db, user)
    if visible is not None:
        if include_self:
            visible = set(visible) | {user.id}
        return visible

    accessible = get_accessible_team_ids(db, user)
    if accessible is None:
        return None
    if not accessible:
        return {user.id} if include_self else set()
    ids = team_member_user_ids(db, list(accessible))
    if include_self:
        ids.add(user.id)
    return ids


def scoped_customer_ids(db: Session, user: User) -> set[UUID] | None:
    """Customer IDs visible via in-scope projects. None = all customers."""
    from app.core.team_access import project_visibility_clause

    clause = project_visibility_clause(db, user)
    if clause is None:
        return None
    stmt = select(Project.customer_id).where(
        Project.is_deleted.is_(False),
        clause,
    )
    return set(db.scalars(stmt).all())


def filter_customers_for_user(
    db: Session, user: User, customers: list[Customer]
) -> list[Customer]:
    allowed = scoped_customer_ids(db, user)
    if allowed is None:
        return customers
    if not allowed:
        return []
    return [c for c in customers if c.id in allowed]


def can_access_document_entity(
    db: Session, user: User, *, entity_type: str, entity_id: UUID
) -> bool:
    """Gate document list/download/upload by linked entity visibility."""
    kind = (entity_type or "").strip().lower()
    if kind in {"project", "projects"}:
        project = db.get(Project, entity_id)
        if project is None:
            return False
        return can_access_project(db, user, project)
    if kind in {"user", "users"}:
        visible = scoped_user_ids_for_actor(db, user)
        if visible is None:
            return True
        return entity_id in visible
    if kind in {"team", "teams"}:
        ctx = resolve_data_scope(db, user)
        return ctx.allows_team(entity_id)
    # Unknown entity types: only unrestricted actors (admin / company scope).
    ctx = resolve_data_scope(db, user)
    return ctx.unrestricted
