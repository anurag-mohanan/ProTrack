"""Engineering workload against capacity (demand-1). Never assigns or reassigns anyone.

Demand is the remaining work of open projects, spread evenly over the assigned designer's working
days until the project's predicted (else target) end. That spreading is a stated assumption of
this model: ProTrack has no allocation plan, so the result is a forecast of load, not a schedule.
Capacity is the Phase 3 allocatable hours per person-day less the share of booked time the
person historically spent away from projects.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Team, Timesheet, TimesheetEntry, User
from app.models.prediction import PREDICTED
from app.services.actual_hours import official_entry_clause
from app.services.forecasting.capacity import day_capacity
from app.services.holiday_service import load_holiday_dates
from app.services.kpi_participation import capacity_planning_users
from app.services.predictive.inputs import ProjectFacts
from app.services.predictive.types import CALCULATION, Outcome, factor, hours
from app.services.resource_shift_service import shift_hours_for_range

TYPE = "resource_demand"
VERSION = "demand-1"
HORIZONS = (2, 4, 8, 12)
LOOKBACK_DAYS = 84
MIN_HISTORY_WEEKS = 4
BACKLOG_DAYS = 10
UNDERUTILIZED_BELOW = Decimal("0.5")
CONCENTRATION_SHARE = Decimal("0.6")
FINISH_SEARCH_DAYS = 365
ZERO = Decimal("0")

COMMON_LIMITS = [
    "Planned leave is not recorded in ProTrack, so future leave is not deducted beyond the historical non-project share.",
    "Only open projects are included; work not yet won or not yet entered is not.",
    "Remaining work is spread evenly over the designer's working days to the end date; ProTrack has no allocation plan.",
    "Demand is attributed to each project's designer only; work as surfacer, leader or support is not included.",
]


def _name(user: User) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or str(user.id))


@dataclass
class PersonSupply:
    user_id: UUID
    name: str
    team_id: UUID | None
    daily: dict[date, Decimal]
    working_days: set[date]
    non_project_share: Decimal | None
    history_weeks: int


@dataclass
class ProjectDemand:
    facts: ProjectFacts
    remaining: Decimal
    remaining_basis: str
    end: date | None
    end_basis: str | None
    owner_id: UUID | None
    team_id: UUID | None
    daily: dict[date, Decimal] = field(default_factory=dict)
    note: str | None = None


def non_project_shares(db: Session, user_ids: list[UUID], as_of: date) -> dict[UUID, tuple[Decimal | None, int]]:
    """Share of approved booked hours not on a project, over the previous 12 weeks."""
    start = as_of - timedelta(days=LOOKBACK_DAYS)
    totals: dict[UUID, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    weeks: dict[UUID, set[date]] = defaultdict(set)
    if user_ids:
        rows = db.execute(
            select(Timesheet.user_id, Timesheet.week_start, TimesheetEntry.project_id.is_not(None), func.sum(TimesheetEntry.hours))
            .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
            .where(
                Timesheet.user_id.in_(user_ids),
                official_entry_clause(),
                TimesheetEntry.entry_date > start,
                TimesheetEntry.entry_date <= as_of,
            )
            .group_by(Timesheet.user_id, Timesheet.week_start, TimesheetEntry.project_id.is_not(None))
        ).all()
        for user_id, week, on_project, total in rows:
            totals[user_id][0] += Decimal(total or 0)
            if on_project:
                totals[user_id][1] += Decimal(total or 0)
            weeks[user_id].add(week)
    out = {}
    for user_id in user_ids:
        total, project = totals[user_id]
        n_weeks = len(weeks[user_id])
        if n_weeks >= MIN_HISTORY_WEEKS and total > 0:
            out[user_id] = ((total - project) / total).quantize(Decimal("0.0001")), n_weeks
        else:
            out[user_id] = None, n_weeks
    return out


def load_supply(db: Session, as_of: date, until: date) -> dict[UUID, PersonSupply]:
    users = capacity_planning_users(db)
    start = as_of + timedelta(days=1)
    holidays = load_holiday_dates(db, start, until)
    shifts = shift_hours_for_range(db, [u.id for u in users], start, until)
    shares = non_project_shares(db, [u.id for u in users], as_of)
    out = {}
    for user in users:
        share, n_weeks = shares[user.id]
        keep = Decimal(1) - (share or ZERO)
        daily, working = {}, set()
        day = start
        while day <= until:
            values, source = day_capacity(user, day, holidays, shifts)
            if source and values["available_hours"] > 0:
                working.add(day)
            daily[day] = values["allocatable_hours"] * keep
            day += timedelta(days=1)
        out[user.id] = PersonSupply(user.id, _name(user), user.team_id, daily, working, share, n_weeks)
    return out


def project_demands(facts: list[ProjectFacts], final_hours: dict[UUID, Outcome], delivery: dict[UUID, Outcome],
                    as_of: date, supply: dict[UUID, PersonSupply]) -> tuple[list[ProjectDemand], list[ProjectFacts]]:
    """(demands, projects without any basis for remaining hours)."""
    demands, unknown = [], []
    for f in facts:
        predicted = final_hours.get(f.project_id)
        actual = f.actual_hours or ZERO
        if predicted is not None and predicted.status == PREDICTED:
            remaining, basis = max(predicted.predicted_value - actual, ZERO), "predicted final hours less hours recorded"
        elif f.estimate_approved and f.current_estimate is not None:
            remaining, basis = max(f.current_estimate - actual, ZERO), "approved estimate less hours recorded"
        else:
            unknown.append(f)
            continue
        if remaining <= 0:
            continue
        done = delivery.get(f.project_id)
        if done is not None and done.status == PREDICTED:
            end, end_basis = done.predicted_date, "predicted completion"
        elif f.current_target is not None:
            end, end_basis = f.current_target, "current target date"
        else:
            end, end_basis = None, None
        owner = f.designer_id
        team = f.team_id or (supply[owner].team_id if owner in supply else None)
        demands.append(ProjectDemand(f, remaining, basis, end, end_basis, owner, team))
    for demand in demands:
        _phase(demand, as_of, supply)
    return demands, unknown


def _phase(demand: ProjectDemand, as_of: date, supply: dict[UUID, PersonSupply]) -> None:
    person = supply.get(demand.owner_id) if demand.owner_id else None
    if demand.end is None:
        demand.note = "No predicted completion or target date, so this work cannot be placed in time."
        return

    def workday(day: date) -> bool:
        return day in person.working_days if person else day.weekday() < 5

    horizon = sorted(person.daily) if person else [as_of + timedelta(days=i) for i in range(1, FINISH_SEARCH_DAYS + 1)]
    if demand.end <= as_of:
        days = [d for d in horizon if workday(d)][:BACKLOG_DAYS]
        demand.note = (f"The end date ({demand.end}) has passed; the remaining work is assumed to be needed over the "
                       f"next {BACKLOG_DAYS} working days.")
    else:
        days = [d for d in horizon if d <= demand.end and workday(d)] or [d for d in horizon if workday(d)][:1]
    if not days:
        demand.note = "The assigned person has no working days in the horizon, so this work cannot be placed."
        return
    share = demand.remaining / len(days)
    demand.daily = {d: share for d in days}
    if person is None:
        demand.note = (demand.note + " " if demand.note else "") + (
            "No capacity-planning designer is assigned; the work is spread over weekdays and counted at team level only."
        )


def person_load(demands: list[ProjectDemand]) -> dict[UUID, dict[date, Decimal]]:
    load: dict[UUID, dict[date, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for demand in demands:
        if demand.owner_id is None:
            continue
        for day, value in demand.daily.items():
            load[demand.owner_id][day] += value
    return load


def capacity_finish(person: PersonSupply, other_load: dict[date, Decimal], remaining: Decimal, as_of: date) -> date | None:
    """First day the person's free capacity, after their other project work, covers ``remaining``."""
    covered = ZERO
    for day in sorted(person.daily):
        if day <= as_of or (day - as_of).days > FINISH_SEARCH_DAYS:
            continue
        covered += max(person.daily[day] - other_load.get(day, ZERO), ZERO)
        if covered >= remaining:
            return day
    return None


def _window(as_of: date, weeks: int) -> tuple[date, date]:
    return as_of + timedelta(days=1), as_of + timedelta(days=7 * weeks)


def _sum(daily: dict[date, Decimal], start: date, end: date) -> Decimal:
    return sum((v for d, v in daily.items() if start <= d <= end), ZERO)


def _overloaded_weeks(capacity: dict[date, Decimal], load: dict[date, Decimal], start: date, end: date) -> list[str]:
    weekly_cap: dict[date, Decimal] = defaultdict(lambda: ZERO)
    weekly_load: dict[date, Decimal] = defaultdict(lambda: ZERO)
    day = start
    while day <= end:
        monday = day - timedelta(days=day.weekday())
        weekly_cap[monday] += capacity.get(day, ZERO)
        weekly_load[monday] += load.get(day, ZERO)
        day += timedelta(days=1)
    return [w.isoformat() for w in sorted(weekly_load) if weekly_load[w] > weekly_cap[w] + Decimal("0.01")]


def _outcome(subject_type: str, key: str, label: str, weeks: int, start: date, end: date, **extra) -> Outcome:
    return Outcome(
        prediction_type=TYPE,
        subject_type=subject_type,
        subject_key=f"{key}:{weeks}w",
        subject_label=f"{label} — next {weeks} weeks",
        unit="hours",
        horizon_start=start,
        horizon_end=end,
        baseline_label="Allocatable capacity less historical non-project share",
        **extra,
    )


def build_outcomes(db: Session, as_of: date, demands: list[ProjectDemand], unknown: list[ProjectFacts],
                   supply: dict[UUID, PersonSupply], coverage: dict[UUID, list[dict]]) -> list[Outcome]:
    team_names = {t.id: t.name for t in db.scalars(select(Team)).all()}
    load = person_load(demands)
    outcomes: list[Outcome] = []
    unplaced = [d for d in demands if not d.daily]
    unknown_by_person: dict[UUID, int] = defaultdict(int)
    unknown_by_team: dict[UUID | None, int] = defaultdict(int)
    known_by_person = {d.owner_id for d in demands if d.owner_id}
    known_by_team = {d.team_id for d in demands}
    for f in unknown:
        if f.designer_id:
            unknown_by_person[f.designer_id] += 1
        unknown_by_team[f.team_id or (supply[f.designer_id].team_id if f.designer_id in supply else None)] += 1

    def missing(n: int) -> str:
        return (f"{n} open project(s) have no approved estimate or predicted final hours; their remaining work is not "
                "included, so demand is understated.")
    for weeks in HORIZONS:
        start, end = _window(as_of, weeks)
        team_rows: dict[UUID | None, dict] = defaultdict(lambda: {"capacity": ZERO, "demand": ZERO, "people": {}, "unassigned": ZERO})
        for person in supply.values():
            capacity = _sum(person.daily, start, end)
            demand = _sum(load.get(person.user_id, {}), start, end)
            row = team_rows[person.team_id]
            row["capacity"] += capacity
            row["demand"] += demand
            row["people"][person.user_id] = demand
            projects = [d for d in demands if d.owner_id == person.user_id and _sum(d.daily, start, end) > 0]
            out = _outcome("person", f"person:{person.user_id}", person.name, weeks, start, end, team_id=person.team_id)
            out.data_used = {
                "projects": [{"project_id": str(d.facts.project_id), "label": d.facts.label,
                              "hours_in_window": str(hours(_sum(d.daily, start, end))), "remaining_basis": d.remaining_basis,
                              "end": d.end.isoformat() if d.end else None, "end_basis": d.end_basis, "note": d.note}
                             for d in projects],
                "non_project_share": str(person.non_project_share) if person.non_project_share is not None else None,
                "history_weeks": person.history_weeks,
            }
            out.warnings = list(COMMON_LIMITS)
            if person.non_project_share is None:
                out.warnings.append(
                    f"Only {person.history_weeks} week(s) of recent timesheets, so non-project time is not deducted and "
                    "capacity is overstated."
                )
            gaps = unknown_by_person.get(person.user_id, 0)
            if gaps and person.user_id not in known_by_person:
                outcomes.append(out.insufficient(
                    f"None of this person's {gaps} open project(s) has an approved estimate or predicted final hours."))
                continue
            if capacity <= 0:
                outcomes.append(out.insufficient("No allocatable capacity in this window (not working, unavailable or outside employment)."))
                continue
            _fill(out, demand, capacity)
            out.data_used["overloaded_weeks"] = _overloaded_weeks(person.daily, load.get(person.user_id, {}), start, end)
            out.data_used["demand_complete"] = not gaps
            out.data_used["assigned_open_projects"] = person.user_id in known_by_person
            out.data_used["underutilized"] = (
                weeks == 4 and not gaps and person.user_id in known_by_person and demand < capacity * UNDERUTILIZED_BELOW
            )
            if gaps:
                out.warnings.append(missing(gaps))
            out.sample_size = len(projects)
            outcomes.append(out)
        for demand in demands:
            if demand.owner_id not in supply:
                team_rows[demand.team_id]["unassigned"] += _sum(demand.daily, start, end)
        for team_id, row in team_rows.items():
            label = team_names.get(team_id, "No team") if team_id else "No team"
            out = _outcome("team", f"team:{team_id or 'none'}", label, weeks, start, end, team_id=team_id)
            total_demand = row["demand"] + row["unassigned"]
            out.data_used = {
                "people": len(row["people"]),
                "assigned_demand": str(hours(row["demand"])),
                "demand_without_capacity_planning_designer": str(hours(row["unassigned"])),
            }
            out.warnings = list(COMMON_LIMITS)
            gaps = unknown_by_team.get(team_id, 0)
            if unplaced:
                out.warnings.append(f"{len(unplaced)} project(s) with remaining work have no end date and are not placed in time.")
            if gaps and team_id not in known_by_team:
                outcomes.append(out.insufficient(
                    f"None of this team's {gaps} open project(s) has an approved estimate or predicted final hours."))
                continue
            if row["capacity"] <= 0:
                outcomes.append(out.insufficient("No capacity-planning people with allocatable capacity in this team."))
                continue
            _fill(out, total_demand, row["capacity"])
            out.data_used["demand_complete"] = not gaps
            if gaps:
                out.warnings.append(missing(gaps))
            if len(row["people"]) >= 2 and total_demand > 0:
                top_id, top = max(row["people"].items(), key=lambda kv: kv[1])
                share = top / total_demand
                out.data_used["largest_individual_share"] = str(share.quantize(Decimal("0.01")))
                out.data_used["single_person_dependency"] = share >= CONCENTRATION_SHARE
                if share >= CONCENTRATION_SHARE:
                    out.factors.append(factor("Single-person dependency", f"{supply[top_id].name}: {share * 100:.0f}% of team demand",
                                              detail="One person carries most of this team's forecast work."))
            out.sample_size = len(row["people"])
            outcomes.append(out)
        outcomes.extend(_skill_outcomes(weeks, start, end, demands, supply, coverage))
    return outcomes


def _fill(out: Outcome, demand: Decimal, capacity: Decimal) -> None:
    out.status = PREDICTED
    out.predicted_value = hours(demand)
    out.baseline_value = hours(capacity)
    out.variance_value = hours(demand - capacity)
    out.data_used["utilisation_percent"] = str((demand / capacity * 100).quantize(Decimal("0.1")))
    out.data_used["shortage"] = demand > capacity
    out.factors.insert(0, factor("Forecast project demand", str(hours(demand)), role=CALCULATION))
    out.factors.insert(1, factor("Capacity", str(hours(capacity)), role=CALCULATION))


def _skill_outcomes(weeks: int, start: date, end: date, demands: list[ProjectDemand],
                    supply: dict[UUID, PersonSupply], coverage: dict[UUID, list[dict]]) -> list[Outcome]:
    by_skill: dict[UUID, dict] = {}
    for demand in demands:
        in_window = _sum(demand.daily, start, end)
        for req in coverage.get(demand.facts.project_id, []):
            if not req["is_mandatory"]:
                continue
            row = by_skill.setdefault(req["skill_id"], {"name": req["skill_name"], "demand": ZERO, "holders": set(), "projects": []})
            row["demand"] += in_window
            row["holders"] |= set(req["verified_holder_ids"])
            if in_window > 0:
                row["projects"].append({"label": demand.facts.label, "hours_in_window": str(hours(in_window)),
                                        "designer_is_verified": demand.owner_id in req["verified_holder_ids"]})
    outcomes = []
    for skill_id, row in by_skill.items():
        if row["demand"] <= 0:
            continue
        out = _outcome("skill", f"skill:{skill_id}", row["name"], weeks, start, end)
        out.baseline_label = "Capacity of verified holders"
        holders = [supply[h] for h in row["holders"] if h in supply]
        capacity = sum((_sum(h.daily, start, end) for h in holders), ZERO)
        out.data_used = {"verified_holders": len(row["holders"]), "holders_with_capacity_data": len(holders),
                         "projects": row["projects"]}
        out.warnings = [
            "All forecast work on a project that requires this skill is counted against it; the share of the work that "
            "needs the skill is not recorded.",
            "Holder capacity is not reduced by their own other project work.",
        ]
        if not holders:
            outcomes.append(out.insufficient("No verified holder of this skill has capacity data."))
            continue
        _fill(out, row["demand"], capacity)
        out.data_used["single_person_dependency"] = len(row["holders"]) == 1
        out.sample_size = len(row["projects"])
        outcomes.append(out)
    return outcomes
