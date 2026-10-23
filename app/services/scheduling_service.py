"""Central project scheduling: baseline and forecast dates from effort hours.

Rules
-----
* Hours are effort, not elapsed time. A milestone with ``H`` hours occupies
  ``ceil(H / effort_hours_per_day)`` working days; zero-hour milestones are
  events that finish on the day they start.
* Working days come from Company Settings (``default_working_days``) minus
  non-working holidays (recurring holidays repeat every year).
* A milestone starts on the first working day after all of its predecessors
  finish. Sequential templates chain milestones in sort order; dependency
  templates use the explicit predecessors.
* Forecasts keep completed milestones on their actual dates, start in-progress
  milestones on their actual start, and never schedule open work before today.
  Approved overrides replace the calculated dates and are reported if they
  conflict with a predecessor.
* No allocation model exists, so every forecast is *provisional*: it assumes
  one person delivers ``effort_hours_per_day`` hours per working day on a
  milestone and does not deduct their other work. The assumption is returned
  with each schedule so the UI can label it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import (
    PLANNED_STAGES,
    ExecutionStatus,
    ForecastStatus,
    MilestoneStatus,
    ProjectStage,
    TemplateSchedulingMode,
)
from app.models.foundation import CompanySettings, Holiday
from app.models.models import (
    Milestone,
    Project,
    ProjectBaselineRevision,
    ProjectTemplateMilestone,
    TimesheetEntry,
)

_WEEKDAY_CODES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_FALLBACK_EFFORT_HOURS = Decimal("8")
_MAX_SCHEDULE_DAYS = 3660
_DONE_STATUSES = {MilestoneStatus.completed}
_SKIPPED_STATUSES = {MilestoneStatus.cancelled, MilestoneStatus.not_applicable}


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_id_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def dump_id_list(values: list[str] | list[UUID]) -> str | None:
    cleaned = [str(value) for value in values if value]
    return json.dumps(cleaned) if cleaned else None


# --------------------------------------------------------------------------- calendar


@dataclass(frozen=True)
class WorkCalendar:
    working_weekdays: frozenset[int]
    holidays: frozenset[date]
    recurring_holidays: frozenset[tuple[int, int]] = frozenset()

    def is_working(self, day: date) -> bool:
        if day.weekday() not in self.working_weekdays:
            return False
        if day in self.holidays:
            return False
        return (day.month, day.day) not in self.recurring_holidays

    def next_working(self, day: date) -> date:
        current = day
        for _ in range(_MAX_SCHEDULE_DAYS):
            if self.is_working(current):
                return current
            current += timedelta(days=1)
        raise ValueError("No working day found in the calendar")

    def add_working_days(self, start: date, days: int) -> date:
        """Return the date ``days`` working days after ``start`` (start must be working)."""
        current = start
        remaining = days
        while remaining > 0:
            current = self.next_working(current + timedelta(days=1))
            remaining -= 1
        return current

    def finish_for_effort(self, start: date, hours: Decimal, effort_per_day: Decimal) -> date:
        start = self.next_working(start)
        if hours <= 0:
            return start
        days = max(1, math.ceil(hours / effort_per_day))
        return self.add_working_days(start, days - 1)


def _parse_working_days(raw: str | None) -> frozenset[int]:
    days = {
        _WEEKDAY_CODES[token.strip().lower()[:3]]
        for token in (raw or "").split(",")
        if token.strip().lower()[:3] in _WEEKDAY_CODES
    }
    return frozenset(days or {0, 1, 2, 3, 4})


def load_calendar(db: Session) -> WorkCalendar:
    settings = db.scalar(select(CompanySettings).limit(1))
    rows = db.scalars(select(Holiday).where(Holiday.is_working_day.is_(False))).all()
    return WorkCalendar(
        working_weekdays=_parse_working_days(settings.default_working_days if settings else None),
        holidays=frozenset(row.holiday_date for row in rows if not row.is_recurring),
        recurring_holidays=frozenset(
            (row.holiday_date.month, row.holiday_date.day) for row in rows if row.is_recurring
        ),
    )


@dataclass(frozen=True)
class EffortAssumption:
    hours_per_day: Decimal
    source: str

    @property
    def note(self) -> str:
        return (
            f"Provisional forecast: assumes {self.hours_per_day:g} effort hours per working day "
            f"per milestone ({self.source}); other work of the same people is not deducted."
        )


def load_effort_assumption(db: Session) -> EffortAssumption:
    settings = db.scalar(select(CompanySettings).limit(1))
    if settings is not None and settings.scheduling_effort_hours_per_day:
        value = Decimal(str(settings.scheduling_effort_hours_per_day))
        if value > 0:
            return EffortAssumption(value, "Company Settings → scheduling effort hours")
    if settings is not None and settings.default_working_hours_per_day:
        value = Decimal(str(settings.default_working_hours_per_day))
        if value > 0:
            return EffortAssumption(value, "company default working hours")
    return EffortAssumption(_FALLBACK_EFFORT_HOURS, "system default of 8 hours")


# --------------------------------------------------------------------------- core


@dataclass
class ScheduleItem:
    key: str
    name: str
    sort_order: int
    hours: Decimal
    stage: ProjectStage | None = None
    depends_on: list[str] = field(default_factory=list)
    status: MilestoneStatus = MilestoneStatus.not_started
    actual_hours: Decimal = Decimal("0")
    actual_start: date | None = None
    actual_finish: date | None = None
    override_start: date | None = None
    override_finish: date | None = None
    start: date | None = None
    finish: date | None = None


@dataclass
class ScheduleResult:
    items: list[ScheduleItem]
    completion: date | None
    warnings: list[str]
    invalid: bool


def _predecessors(
    items: list[ScheduleItem], mode: TemplateSchedulingMode
) -> tuple[dict[str, list[str]], list[str], bool]:
    ordered = sorted(items, key=lambda item: (item.sort_order, item.name))
    keys = {item.key for item in ordered}
    warnings: list[str] = []
    if mode == TemplateSchedulingMode.sequential:
        preds = {
            item.key: ([ordered[index - 1].key] if index else [])
            for index, item in enumerate(ordered)
        }
        return preds, warnings, False
    preds: dict[str, list[str]] = {}
    for item in ordered:
        valid = [key for key in item.depends_on if key in keys and key != item.key]
        missing = [key for key in item.depends_on if key not in keys]
        if missing:
            warnings.append(f"'{item.name}' depends on a milestone that no longer exists.")
        preds[item.key] = valid
    return preds, warnings, False


def _topological_order(
    items: list[ScheduleItem], preds: dict[str, list[str]]
) -> list[ScheduleItem] | None:
    by_key = {item.key: item for item in items}
    indegree = {item.key: len(preds.get(item.key, [])) for item in items}
    successors: dict[str, list[str]] = {item.key: [] for item in items}
    for key, keys in preds.items():
        for pred in keys:
            successors[pred].append(key)
    ready = sorted(
        (key for key, degree in indegree.items() if degree == 0),
        key=lambda key: (by_key[key].sort_order, by_key[key].name),
    )
    order: list[ScheduleItem] = []
    while ready:
        key = ready.pop(0)
        order.append(by_key[key])
        for succ in successors[key]:
            indegree[succ] -= 1
            if indegree[succ] == 0:
                ready.append(succ)
                ready.sort(key=lambda k: (by_key[k].sort_order, by_key[k].name))
    return order if len(order) == len(items) else None


def find_dependency_cycle(depends_on: dict[str, list[str]]) -> bool:
    """True when the dependency map contains a cycle."""
    items = [
        ScheduleItem(key=key, name=key, sort_order=index, hours=Decimal("0"))
        for index, key in enumerate(depends_on)
    ]
    preds = {key: [p for p in values if p in depends_on] for key, values in depends_on.items()}
    return _topological_order(items, preds) is None


def compute_schedule(
    items: list[ScheduleItem],
    *,
    start_date: date,
    calendar: WorkCalendar,
    effort: EffortAssumption,
    mode: TemplateSchedulingMode = TemplateSchedulingMode.sequential,
    forecast: bool = False,
    today: date | None = None,
) -> ScheduleResult:
    """Fill ``start``/``finish`` on each item. ``forecast`` honours actuals and today."""
    if not items:
        return ScheduleResult(items=[], completion=None, warnings=[], invalid=False)
    today = today or date.today()
    preds, warnings, invalid = _predecessors(items, mode)
    order = _topological_order(items, preds)
    if order is None:
        warnings.append(
            "Milestone dependencies form a loop; the schedule follows milestone order instead."
        )
        invalid = True
        preds, _w, _i = _predecessors(items, TemplateSchedulingMode.sequential)
        order = sorted(items, key=lambda item: (item.sort_order, item.name))

    by_key = {item.key: item for item in items}
    project_start = calendar.next_working(start_date)
    for item in order:
        pred_finishes = [by_key[key].finish for key in preds.get(item.key, []) if by_key[key].finish]
        earliest = project_start
        if pred_finishes:
            gap = timedelta(days=0 if item.hours <= 0 else 1)
            earliest = max(earliest, calendar.next_working(max(pred_finishes) + gap))

        if forecast and item.status in _SKIPPED_STATUSES:
            item.start = item.finish = None
            continue

        if forecast and item.status in _DONE_STATUSES and item.actual_finish:
            item.start = item.actual_start or item.actual_finish
            item.finish = item.actual_finish
            continue

        if item.override_start:
            if pred_finishes and item.override_start < earliest:
                warnings.append(
                    f"'{item.name}' has an approved start before its predecessor finishes."
                )
                invalid = True
            start = item.override_start
        elif forecast and item.actual_start:
            start = item.actual_start
        else:
            start = earliest
            if forecast:
                start = max(start, calendar.next_working(today))

        hours = item.hours
        if forecast:
            hours = max(item.hours - item.actual_hours, Decimal("0"))
        if item.override_finish:
            finish = item.override_finish
            if finish < start:
                warnings.append(f"'{item.name}' has an approved finish before its start.")
                invalid = True
        else:
            work_from = max(start, calendar.next_working(today)) if forecast else start
            finish = calendar.finish_for_effort(work_from, hours, effort.hours_per_day)
        item.start = start
        item.finish = finish

    finishes = [item.finish for item in items if item.finish]
    return ScheduleResult(
        items=items,
        completion=max(finishes) if finishes else None,
        warnings=warnings,
        invalid=invalid,
    )


# --------------------------------------------------------------------------- estimates


@dataclass(frozen=True)
class MilestoneEstimate:
    hours: Decimal
    basis: str


def distribute_stage_hours(
    template_milestones: list[ProjectTemplateMilestone],
    stage_hours: dict[ProjectStage, Decimal],
) -> tuple[dict[UUID, MilestoneEstimate], list[str]]:
    """Split each stage's hours over its milestones.

    Template default hours act as weights when every milestone of the stage has
    one; otherwise the stage is split equally (and labelled so). Milestones
    outside the planned stages keep the template default.
    """
    result: dict[UUID, MilestoneEstimate] = {}
    warnings: list[str] = []
    visible = [row for row in template_milestones if row.is_visible is not False]
    for stage in PLANNED_STAGES:
        rows = sorted(
            (row for row in visible if row.project_stage == stage),
            key=lambda row: row.sort_order,
        )
        if stage not in stage_hours:
            for row in rows:
                result[row.id] = MilestoneEstimate(
                    _q2(Decimal(str(row.estimated_hours or 0))),
                    "template_default" if row.estimated_hours else "unestimated",
                )
            continue
        total = _q2(Decimal(str(stage_hours[stage])))
        if not rows:
            if total > 0:
                warnings.append(
                    f"{stage.value} has {total} h but the template has no milestones in that "
                    "stage; the hours stay at stage level."
                )
            continue
        weights = [Decimal(str(row.estimated_hours or 0)) for row in rows]
        if all(weight > 0 for weight in weights):
            basis = "template_weight"
        else:
            weights = [Decimal("1")] * len(rows)
            basis = "equal_split"
        weight_total = sum(weights)
        allocated = Decimal("0")
        for index, (row, weight) in enumerate(zip(rows, weights, strict=True)):
            if index == len(rows) - 1:
                hours = total - allocated
            else:
                hours = _q2(total * weight / weight_total)
                allocated += hours
            result[row.id] = MilestoneEstimate(hours, basis)
    for row in visible:
        if row.id not in result:
            result[row.id] = MilestoneEstimate(
                _q2(Decimal(str(row.estimated_hours or 0))),
                "template_default" if row.estimated_hours else "unestimated",
            )
    return result, warnings


# --------------------------------------------------------------------------- projects


def _milestone_actual_hours(db: Session, milestone_ids: list[UUID]) -> dict[UUID, Decimal]:
    if not milestone_ids:
        return {}
    rows = db.execute(
        select(TimesheetEntry.milestone_id, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .where(
            TimesheetEntry.milestone_id.in_(milestone_ids),
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(TimesheetEntry.milestone_id)
    ).all()
    return {milestone_id: Decimal(str(hours or 0)) for milestone_id, hours in rows}


def _milestone_first_entry(db: Session, milestone_ids: list[UUID]) -> dict[UUID, date]:
    if not milestone_ids:
        return {}
    rows = db.execute(
        select(TimesheetEntry.milestone_id, func.min(TimesheetEntry.entry_date))
        .where(
            TimesheetEntry.milestone_id.in_(milestone_ids),
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(TimesheetEntry.milestone_id)
    ).all()
    return {milestone_id: first for milestone_id, first in rows if first}


def project_first_timesheet_date(db: Session, project_id: UUID) -> date | None:
    return db.scalar(
        select(func.min(TimesheetEntry.entry_date)).where(
            TimesheetEntry.project_id == project_id,
            TimesheetEntry.is_deleted.is_(False),
        )
    )


def _project_mode(project: Project) -> TemplateSchedulingMode:
    template = project.project_template
    if template is not None and template.scheduling_mode is not None:
        return template.scheduling_mode
    return TemplateSchedulingMode.sequential


def _items_for_project(db: Session, project: Project, *, forecast: bool) -> list[ScheduleItem]:
    milestones = list(
        db.scalars(select(Milestone).where(Milestone.project_id == project.id)).all()
    )
    ids = [row.id for row in milestones]
    actuals = _milestone_actual_hours(db, ids) if forecast else {}
    first_entries = _milestone_first_entry(db, ids) if forecast else {}
    items: list[ScheduleItem] = []
    for row in milestones:
        actual_finish = row.completed_date or (row.completed_at.date() if row.completed_at else None)
        items.append(
            ScheduleItem(
                key=str(row.id),
                name=row.name,
                sort_order=row.sort_order,
                hours=Decimal(str(row.planned_hours or 0)),
                stage=row.project_stage,
                depends_on=parse_id_list(row.depends_on_ids),
                status=row.status,
                actual_hours=actuals.get(row.id, Decimal("0")),
                actual_start=row.actual_start_date or first_entries.get(row.id),
                actual_finish=actual_finish,
                override_start=row.override_start_date,
                override_finish=row.override_finish_date,
            )
        )
    return items


def _write_baseline(
    db: Session, project: Project, *, set_due_dates: bool
) -> ScheduleResult | None:
    start = project.start_date
    if start is None:
        return None
    items = _items_for_project(db, project, forecast=False)
    if not any(item.hours > 0 for item in items):
        return None
    result = compute_schedule(
        items,
        start_date=start,
        calendar=load_calendar(db),
        effort=load_effort_assumption(db),
        mode=_project_mode(project),
    )
    by_id = {item.key: item for item in result.items}
    for milestone in db.scalars(select(Milestone).where(Milestone.project_id == project.id)).all():
        item = by_id.get(str(milestone.id))
        if item is None:
            continue
        milestone.baseline_start_date = item.start
        milestone.baseline_finish_date = item.finish
        if set_due_dates or milestone.due_date is None:
            milestone.due_date = item.finish
        db.add(milestone)
    starts = [item.start for item in result.items if item.start]
    project.baseline_start_date = min(starts) if starts else start
    project.baseline_completion_date = result.completion
    db.add(project)
    return result


def _milestone_baseline_snapshot(db: Session, project_id: UUID) -> str:
    rows = db.scalars(
        select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.sort_order)
    ).all()
    return json.dumps(
        [
            {
                "milestone_id": str(row.id),
                "name": row.name,
                "planned_hours": str(row.planned_hours or 0),
                "baseline_start_date": row.baseline_start_date.isoformat()
                if row.baseline_start_date
                else None,
                "baseline_finish_date": row.baseline_finish_date.isoformat()
                if row.baseline_finish_date
                else None,
                "due_date": row.due_date.isoformat() if row.due_date else None,
            }
            for row in rows
        ]
    )


def apply_baseline(
    db: Session,
    project: Project,
    *,
    set_due_dates: bool = True,
    actor_id: UUID | None = None,
) -> ScheduleResult | None:
    """Write the first approved baseline for a project (no-op without start date or hours).

    ``set_due_dates=False`` keeps milestone due dates that already exist (used
    when a legacy project receives its first start date).
    """
    if (project.baseline_version or 0) > 0:
        return None
    result = _write_baseline(db, project, set_due_dates=set_due_dates)
    if result is None:
        return None
    project.baseline_version = 1
    db.add(
        ProjectBaselineRevision(
            project_id=project.id,
            revision_number=1,
            previous_start_date=None,
            previous_completion_date=None,
            new_start_date=project.baseline_start_date,
            new_completion_date=project.baseline_completion_date,
            reason="Initial baseline from project start date and stage hours",
            previous_milestones_json=None,
            revised_by_id=actor_id,
            revised_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.add(project)
    return result


def revise_baseline(
    db: Session,
    project: Project,
    *,
    reason: str,
    new_start_date: date | None,
    actor_id: UUID,
) -> ProjectBaselineRevision:
    """Approve a new baseline from current planned hours; the old one is kept in history."""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ProTrackValidationError("Give a reason for the baseline revision (at least 5 characters)")
    if project.execution_status in (ExecutionStatus.completed, ExecutionStatus.cancelled):
        raise ProTrackValidationError("Completed or cancelled projects cannot be re-baselined")
    if new_start_date is None and project.start_date is None:
        raise ProTrackValidationError("Set the Project Start Date before approving a baseline")
    previous_start = project.baseline_start_date
    previous_completion = project.baseline_completion_date
    snapshot = _milestone_baseline_snapshot(db, project.id)
    if new_start_date is not None:
        project.start_date = new_start_date
    result = _write_baseline(db, project, set_due_dates=True)
    if result is None:
        raise ProTrackValidationError(
            "A baseline needs planned hours on at least one milestone; enter stage hours first"
        )
    if result.invalid:
        raise ProTrackValidationError(
            "The schedule is invalid: " + " ".join(result.warnings or ["check dependencies and overrides"])
        )
    project.baseline_version = (project.baseline_version or 0) + 1
    revision = ProjectBaselineRevision(
        project_id=project.id,
        revision_number=project.baseline_version,
        previous_start_date=previous_start,
        previous_completion_date=previous_completion,
        new_start_date=project.baseline_start_date,
        new_completion_date=project.baseline_completion_date,
        reason=reason,
        previous_milestones_json=snapshot,
        revised_by_id=actor_id,
        revised_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(project)
    db.add(revision)
    db.flush()
    return revision


def recalculate_forecast(db: Session, project: Project, *, today: date | None = None) -> ScheduleResult | None:
    """Recalculate forecast dates; baseline and actual dates are never touched."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    effort = load_effort_assumption(db)
    if project.actual_start_date is None:
        first_entry = project_first_timesheet_date(db, project.id)
        if first_entry is not None:
            project.actual_start_date = first_entry
    if project.execution_status == ExecutionStatus.completed:
        project.forecast_status = ForecastStatus.completed.value
        project.forecast_completion_date = (
            project.completed_at.date() if project.completed_at else project.forecast_completion_date
        )
        project.forecast_note = None if project.completed_at else (
            "Completed without an actual completion date; enter it to include the project in reports."
        )
        project.forecast_calculated_at = now
        db.add(project)
        return None
    if project.execution_status == ExecutionStatus.cancelled:
        project.forecast_status = None
        project.forecast_completion_date = None
        project.forecast_note = "Cancelled projects are not forecast."
        project.forecast_calculated_at = now
        db.add(project)
        return None
    start = project.start_date or project.actual_start_date
    if start is None:
        project.forecast_status = ForecastStatus.unconfigured.value
        project.forecast_completion_date = None
        project.forecast_note = "Set the Project Start Date to calculate a forecast."
        project.forecast_calculated_at = now
        db.add(project)
        return None
    items = _items_for_project(db, project, forecast=True)
    if not any(item.hours > 0 for item in items):
        project.forecast_status = ForecastStatus.unconfigured.value
        project.forecast_completion_date = None
        project.forecast_note = "No planned hours on milestones; enter stage hours to forecast."
        project.forecast_calculated_at = now
        db.add(project)
        return None
    result = compute_schedule(
        items,
        start_date=start,
        calendar=load_calendar(db),
        effort=effort,
        mode=_project_mode(project),
        forecast=True,
        today=today,
    )
    by_id = {item.key: item for item in result.items}
    for milestone in db.scalars(select(Milestone).where(Milestone.project_id == project.id)).all():
        item = by_id.get(str(milestone.id))
        if item is None:
            continue
        milestone.forecast_start_date = item.start
        milestone.forecast_finish_date = item.finish
        if milestone.actual_start_date is None and item.actual_start and item.actual_hours > 0:
            milestone.actual_start_date = item.actual_start
        db.add(milestone)
    project.forecast_completion_date = result.completion
    project.forecast_status = (
        ForecastStatus.invalid.value if result.invalid else ForecastStatus.provisional.value
    )
    note = effort.note
    if result.warnings:
        note = f"{note} {' '.join(result.warnings)}"
    project.forecast_note = note
    project.forecast_calculated_at = now
    db.add(project)
    return result


def schedule_template_preview(
    db: Session,
    template_milestones: list[ProjectTemplateMilestone],
    *,
    start_date: date,
    stage_hours: dict[ProjectStage, Decimal],
    mode: TemplateSchedulingMode,
) -> tuple[ScheduleResult, dict[UUID, MilestoneEstimate], list[str], EffortAssumption]:
    estimates, warnings = distribute_stage_hours(template_milestones, stage_hours)
    items = [
        ScheduleItem(
            key=str(row.id),
            name=row.milestone_name,
            sort_order=row.sort_order,
            hours=estimates[row.id].hours,
            stage=row.project_stage,
            depends_on=parse_id_list(row.depends_on_ids),
        )
        for row in template_milestones
        if row.is_visible is not False
    ]
    effort = load_effort_assumption(db)
    result = compute_schedule(
        items,
        start_date=start_date,
        calendar=load_calendar(db),
        effort=effort,
        mode=mode,
    )
    return result, estimates, warnings + result.warnings, effort
