"""Capacity supply forecast. Read-only; same daily-capacity rules as the Resource Planning grid."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserAvailabilityStatus
from app.models.models import Project, Team, User
from app.schemas.forecasting import (
    CapacityBreakdown,
    CapacityForecastResponse,
    DemandSummary,
    DesignerDemand,
    PersonCapacity,
    TeamCapacity,
)
from app.services.engineering_metrics_service import build_engineering_metrics_batch
from app.services.forecasting.definitions import (
    CAPACITY_METHOD_VERSION,
    build_periods,
    metadata,
)
from app.services.forecasting.effort import open_projects
from app.services.holiday_service import is_holiday_cached, load_holiday_dates
from app.services.kpi_participation import capacity_planning_users
from app.services.reporting.quote_to_delivery import APPROVED_ESTIMATE_SOURCES
from app.services.resource_planning_service import (
    _designer_user_ids_for_team,
    _user_works_on,
)
from app.services.resource_shift_service import shift_hours_for_range

_HOURS = Decimal("0.01")
_UNAVAILABLE_STATUSES = (UserAvailabilityStatus.on_leave, UserAvailabilityStatus.unavailable)
_FIELDS = (
    "scheduled_hours",
    "holiday_hours",
    "outside_employment_hours",
    "status_unavailable_hours",
    "available_hours",
    "allocatable_hours",
)

GAP_REASON = (
    "Not calculated: demand cannot be placed in periods. There is no allocation model, the Resource "
    "Planning grid's demand is a heuristic (floors, fixed role shares, even spreading), and no "
    "completion forecast exists."
)
SKILL_REASON = (
    "Not calculated: no user has a verified skill record and projects do not record required "
    "skills or software. Skills are not inferred from history."
)
PHASING_REASON = (
    "Approved remaining hours are shown as an unphased total; they are not spread over periods "
    "because no allocation or validated schedule exists."
)


@dataclass
class _Acc:
    values: dict[str, Decimal] = field(default_factory=lambda: {f: Decimal("0") for f in _FIELDS})

    def add(self, other: dict[str, Decimal]) -> None:
        for key in _FIELDS:
            self.values[key] += other[key]

    def read(self, period_key: str) -> CapacityBreakdown:
        return CapacityBreakdown(
            period_key=period_key, **{k: v.quantize(_HOURS) for k, v in self.values.items()}
        )


def day_capacity(
    user: User,
    day: date,
    holidays: set[date],
    shift_hours: dict[UUID, dict[date, Decimal]],
) -> tuple[dict[str, Decimal], str | None]:
    """One person-day split into the capacity components; also the hours source used."""
    out = {f: Decimal("0") for f in _FIELDS}
    if not _user_works_on(user, day):
        return out, None
    shift = shift_hours.get(user.id, {}).get(day)
    if shift is not None and shift > 0:
        hours, source = Decimal(str(shift)), "shift"
    else:
        hours, source = Decimal(str(user.working_hours_per_day or 8)), "baseline"
    out["scheduled_hours"] = hours
    if (user.joining_date and day < user.joining_date) or (user.leaving_date and day > user.leaving_date):
        out["outside_employment_hours"] = hours
    elif is_holiday_cached(holidays, day):
        out["holiday_hours"] = hours
    elif user.availability_status in _UNAVAILABLE_STATUSES:
        out["status_unavailable_hours"] = hours
    else:
        out["available_hours"] = hours
        out["allocatable_hours"] = hours * Decimal(user.max_allocation_percent or 0) / Decimal("100")
    return out, source


def _name(user: User) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or str(user.id))


def build_capacity_forecast(
    db: Session,
    *,
    start: date | None = None,
    granularity: str = "week",
    periods: int = 8,
    team_ids: set[UUID] | None = None,
    project_visibility_clause=None,
    as_of: date | None = None,
) -> CapacityForecastResponse:
    as_of = as_of or date.today()
    start = start or as_of
    period_rows = build_periods(start, granularity, periods)
    window_start, window_end = start, period_rows[-1].end_date

    users = capacity_planning_users(db)
    scoped = _designer_user_ids_for_team(db, team_ids=list(team_ids)) if team_ids is not None else None
    if scoped is not None:
        users = [u for u in users if u.id in scoped]
    users.sort(key=_name)
    holidays = load_holiday_dates(db, window_start, window_end)
    shift_hours = shift_hours_for_range(db, [u.id for u in users], window_start, window_end)
    team_names = {t.id: t.name for t in db.scalars(select(Team)).all()}

    people: list[PersonCapacity] = []
    totals = {p.key: _Acc() for p in period_rows}
    grand = _Acc()
    team_acc: dict[UUID | None, dict[str, _Acc]] = defaultdict(lambda: {p.key: _Acc() for p in period_rows})
    team_total: dict[UUID | None, _Acc] = defaultdict(_Acc)
    team_heads: dict[UUID | None, int] = defaultdict(int)

    for user in users:
        sources: set[str] = set()
        person_total = _Acc()
        cells: list[CapacityBreakdown] = []
        for period in period_rows:
            acc = _Acc()
            day = max(period.start_date, window_start)
            while day <= period.end_date:
                values, source = day_capacity(user, day, holidays, shift_hours)
                if source:
                    sources.add(source)
                acc.add(values)
                day += timedelta(days=1)
            cells.append(acc.read(period.key))
            person_total.add(acc.values)
            totals[period.key].add(acc.values)
            team_acc[user.team_id][period.key].add(acc.values)
            team_total[user.team_id].add(acc.values)
            grand.add(acc.values)
        team_heads[user.team_id] += 1
        people.append(
            PersonCapacity(
                user_id=user.id,
                name=_name(user),
                team_id=user.team_id,
                team_name=team_names.get(user.team_id) if user.team_id else None,
                hours_source=("mixed" if len(sources) > 1 else next(iter(sources)) if sources else "none"),  # type: ignore[arg-type]
                availability_status=user.availability_status.value if user.availability_status else "available",
                max_allocation_percent=user.max_allocation_percent or 0,
                joining_date=user.joining_date,
                leaving_date=user.leaving_date,
                periods=cells,
                total=person_total.read("total"),
            )
        )

    teams = [
        TeamCapacity(
            team_id=team_id,
            team_name=team_names.get(team_id, "No primary team") if team_id else "No primary team",
            headcount=team_heads[team_id],
            periods=[team_acc[team_id][p.key].read(p.key) for p in period_rows],
            total=team_total[team_id].read("total"),
        )
        for team_id in sorted(team_heads, key=lambda t: (t is None, team_names.get(t, "") if t else ""))
    ]

    demand = _approved_demand(
        db,
        as_of=as_of,
        users=users,
        visibility_clause=project_visibility_clause,
        team_ids=frozenset(team_ids) if team_ids is not None else None,
    )
    shifted = sum(1 for p in people if p.hours_source in ("shift", "mixed"))
    flagged = sum(1 for u in users if u.availability_status in _UNAVAILABLE_STATUSES)
    limitations = [
        "Planned leave is not recorded anywhere in ProTrack, so it is not deducted. Capacity is overstated by any future leave.",
        "Non-project commitments (overheads, training, support) are not recorded and are not deducted.",
        "An on-leave or unavailable status has no end date; it is applied to the whole horizon, as in the Resource Planning grid.",
        GAP_REASON,
        SKILL_REASON,
    ]
    if not holidays:
        limitations.insert(0, "No holidays are recorded in this window, so none are deducted.")
    if shifted == 0 and people:
        limitations.insert(0, "No shift assignments apply in this window; every person uses working hours per day.")
    return CapacityForecastResponse(
        metadata=metadata(
            forecast_type="capacity_supply",
            method_version=CAPACITY_METHOD_VERSION,
            as_of=as_of,
            status="preliminary" if people else "unavailable",
            status_reason=(
                "Preliminary: planned leave and non-project commitments are not recorded."
                if people
                else "No capacity-planning users in scope."
            ),
            period_start=window_start,
            period_end=window_end,
            sources=[
                "Users flagged for capacity planning (active employees; virtual and non-capacity roles excluded)",
                "Resource shift assignments (paid shift hours), else user working hours per day",
                "User working days, joining and leaving dates, availability status, max allocation %",
                "Holiday calendar",
                "Shared engineering metrics for approved remaining hours (demand, unphased)",
            ],
            assumptions=[
                "Scheduled hours are counted only on the person's working days.",
                f"Days before {window_start} are excluded, so the first period may be partial.",
                "Allocatable hours = available hours × max allocation %.",
                f"{flagged} person(s) currently have an on-leave or unavailable status.",
            ],
            limitations=limitations,
        ),
        granularity=granularity,  # type: ignore[arg-type]
        periods=period_rows,
        totals=[totals[p.key].read(p.key) for p in period_rows],
        grand_total=grand.read("total"),
        teams=teams,
        people=people,
        demand=demand,
        gap_analysis_reason=GAP_REASON,
        skill_demand_reason=SKILL_REASON,
    )


def _approved_demand(
    db: Session,
    *,
    as_of: date,
    users: list[User],
    visibility_clause,
    team_ids: frozenset[UUID] | None,
) -> DemandSummary:
    projects: list[Project] = open_projects(db, visibility_clause=visibility_clause, team_ids=team_ids)
    metrics = build_engineering_metrics_batch(db, projects, finance_details_visible=False, today=as_of)
    names = {u.id: _name(u) for u in users}
    by_designer: dict[UUID, list[Decimal]] = defaultdict(list)
    total = Decimal("0")
    approved = without = no_designer = 0
    for project in projects:
        m = metrics[project.id]
        if m.estimate.estimate_source not in APPROVED_ESTIMATE_SOURCES or m.remaining_hours.value is None:
            without += 1
            continue
        approved += 1
        remaining = max(m.remaining_hours.value, Decimal("0"))
        total += remaining
        if project.designer_id is None:
            no_designer += 1
        else:
            by_designer[project.designer_id].append(remaining)
    extra = {
        u.id: _name(u)
        for u in db.scalars(select(User).where(User.id.in_([d for d in by_designer if d not in names]))).all()
    } if any(d not in names for d in by_designer) else {}
    return DemandSummary(
        approved_remaining_hours=total.quantize(_HOURS),
        projects_with_approved_estimate=approved,
        projects_without_approved_estimate=without,
        projects_without_designer=no_designer,
        by_designer=sorted(
            (
                DesignerDemand(
                    user_id=uid,
                    name=names.get(uid) or extra.get(uid, str(uid)),
                    approved_remaining_hours=sum(values, Decimal("0")).quantize(_HOURS),
                    projects=len(values),
                )
                for uid, values in by_designer.items()
            ),
            key=lambda d: -d.approved_remaining_hours,
        ),
        phasing_reason=PHASING_REASON,
    )
