"""Record actual outcomes against stored predictions. Only outcome columns are ever written."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, MilestoneStatus, TimesheetStatus
from app.models.models import Milestone, Project, Timesheet, TimesheetEntry, User
from app.models.prediction import (
    OUTCOME_EVALUATED,
    OUTCOME_NOT_EVALUABLE,
    OUTCOME_PENDING,
    Prediction,
)
from app.services.delivery_variance_service import is_milestone_skipped, milestone_completion_date
from app.services.milestone_lifecycle import is_active
from app.services.predictive import delivery, finance, hours, milestone, resources
from app.services.predictive.inputs import ProjectFacts, load_facts

# Late timesheets keep arriving after completion; final hours are scored once this has passed.
HOURS_SETTLE_DAYS = 14


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _close(p: Prediction, now: datetime, note: str) -> None:
    p.outcome_status = OUTCOME_NOT_EVALUABLE
    p.outcome_note = note[:500]
    p.evaluated_at = now


def _score(p: Prediction, *, error: Decimal, actual_scale: Decimal | None, naive: Decimal | None, now: datetime,
           horizon_days: int) -> None:
    p.error_value = error
    p.abs_error = abs(error)
    p.pct_error = (abs(error) / actual_scale * 100).quantize(Decimal("0.01")) if actual_scale else None
    p.naive_abs_error = naive
    p.horizon_days = max(0, horizon_days)
    p.outcome_status = OUTCOME_EVALUATED
    p.evaluated_at = now


def _evaluate_hours(p: Prediction, facts: ProjectFacts, as_of: date, now: datetime) -> None:
    if as_of < facts.completed_on + timedelta(days=HOURS_SETTLE_DAYS):
        return
    if facts.actual_status != "recorded" or not facts.actual_hours:
        _close(p, now, "The project completed without recorded actual hours.")
        return
    actual = Decimal(facts.actual_hours)
    p.actual_value = actual
    naive = abs(p.baseline_value - actual) if p.baseline_value is not None else None
    if p.baseline_value is not None:
        p.event_occurred = actual > p.baseline_value
    _score(p, error=Decimal(p.predicted_value) - actual, actual_scale=actual, naive=naive, now=now,
           horizon_days=(facts.completed_on - p.as_of).days)
    p.outcome_note = "Actual hours include draft, submitted and rejected time (current project rule)."


def _evaluate_delivery(p: Prediction, facts: ProjectFacts, as_of: date, now: datetime) -> None:
    actual = facts.completed_on
    p.actual_date = actual
    naive = Decimal(abs((p.baseline_date - actual).days)) if p.baseline_date is not None else None
    if p.baseline_date is not None:
        p.event_occurred = actual > p.baseline_date
    duration = (actual - facts.start_date).days if facts.start_date else None
    _score(p, error=Decimal((p.predicted_date - actual).days), actual_scale=Decimal(duration) if duration else None,
           naive=naive, now=now, horizon_days=(actual - p.as_of).days)


PROJECT_EVALUATORS: dict[str, Callable[[Prediction, ProjectFacts, date, datetime], None]] = {
    hours.TYPE: _evaluate_hours,
    delivery.TYPE: _evaluate_delivery,
}


def _tally(counts: dict[str, int], prediction: Prediction) -> None:
    if prediction.outcome_status == OUTCOME_EVALUATED:
        counts["evaluated"] += 1
    elif prediction.outcome_status == OUTCOME_NOT_EVALUABLE:
        counts["not_evaluable"] += 1
    else:
        counts["pending"] += 1


def _evaluate_milestones(db: Session, as_of: date, now: datetime, counts: dict[str, int]) -> None:
    pending = list(db.scalars(select(Prediction).where(
        Prediction.outcome_status == OUTCOME_PENDING, Prediction.prediction_type == milestone.TYPE,
    )))
    ids = {p.milestone_id for p in pending if p.milestone_id}
    rows = {m.id: m for m in db.scalars(select(Milestone).where(Milestone.id.in_(ids)))} if ids else {}
    for p in pending:
        m = rows.get(p.milestone_id)
        if m is None:
            _close(p, now, "The milestone was deleted.")
        elif not is_active(m) or is_milestone_skipped(m):
            _close(p, now, "The milestone was cancelled, marked not applicable, merged or archived.")
        elif m.status == MilestoneStatus.completed:
            actual = milestone_completion_date(m)
            if actual is None:
                _close(p, now, "The milestone was completed without a completion date.")
            elif actual < p.as_of:
                _close(p, now, "The recorded completion is earlier than the prediction date.")
            elif actual <= as_of:
                p.actual_date = actual
                naive = Decimal(abs((p.baseline_date - actual).days)) if p.baseline_date else None
                p.event_occurred = actual > p.baseline_date if p.baseline_date else None
                _score(p, error=Decimal((p.predicted_date - actual).days), actual_scale=None, naive=naive, now=now,
                       horizon_days=(actual - p.as_of).days)
        _tally(counts, p)


def _booked_project_hours(db: Session, user_ids: list[UUID], start: date, end: date) -> Decimal:
    if not user_ids:
        return Decimal("0")
    total = db.scalar(
        select(func.sum(TimesheetEntry.hours))
        .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
        .where(
            Timesheet.user_id.in_(user_ids),
            Timesheet.status != TimesheetStatus.rejected,
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.project_id.is_not(None),
            TimesheetEntry.entry_date >= start,
            TimesheetEntry.entry_date <= end,
        )
    )
    return Decimal(total or 0)


def _evaluate_demand(db: Session, as_of: date, now: datetime, counts: dict[str, int]) -> None:
    pending = list(db.scalars(select(Prediction).where(
        Prediction.outcome_status == OUTCOME_PENDING, Prediction.prediction_type == resources.TYPE,
        Prediction.horizon_end < as_of,
    )))
    for p in pending:
        if p.subject_type == "skill":
            _close(p, now, "Hours are not recorded per skill, so skill demand cannot be checked.")
        elif p.subject_type == "person":
            user_id = UUID(p.subject_key.split(":")[1])
            _score_demand(p, _booked_project_hours(db, [user_id], p.horizon_start, p.horizon_end), now)
        elif p.subject_type == "team" and p.team_id is not None:
            members = list(db.scalars(select(User.id).where(User.team_id == p.team_id)))
            _score_demand(p, _booked_project_hours(db, members, p.horizon_start, p.horizon_end), now)
            p.outcome_note = "Compared with project hours booked by the team's current members."
        else:
            _close(p, now, "People without a team cannot be grouped for comparison.")
        _tally(counts, p)


def _score_demand(p: Prediction, actual: Decimal, now: datetime) -> None:
    p.actual_value = actual
    _score(p, error=Decimal(p.predicted_value) - actual, actual_scale=actual if actual > 0 else None, naive=None,
           now=now, horizon_days=(p.horizon_end - p.as_of).days)


def _evaluate_finance(db: Session, as_of: date, now: datetime, counts: dict[str, int]) -> None:
    pending = list(db.scalars(select(Prediction).where(
        Prediction.outcome_status == OUTCOME_PENDING,
        Prediction.prediction_type.in_((finance.BILLING, finance.COLLECTIONS)),
        Prediction.horizon_end < as_of,
    )))
    if not pending:
        return
    ledgers = finance.load_ledgers(db)
    for p in pending:
        population = set(json.loads(p.data_used_json or "{}").get("population", []))
        if p.prediction_type == finance.COLLECTIONS:
            actual = finance.collected_in(ledgers, population, p.horizon_start, p.horizon_end)
            p.outcome_note = "Payments received in the month on invoices that were outstanding at the prediction date."
        else:
            actual = finance.invoiced_in(ledgers, population, p.horizon_start, p.horizon_end)
            p.outcome_note = "Invoices issued in the month for billing milestones that were unbilled at the prediction date."
        p.actual_value = actual
        naive = abs(p.baseline_value - actual) if p.baseline_value is not None else None
        _score(p, error=Decimal(p.predicted_value) - actual, actual_scale=actual if actual > 0 else None, naive=naive,
               now=now, horizon_days=(p.horizon_end - p.as_of).days)
        _tally(counts, p)


def evaluate_outcomes(db: Session, as_of: date | None = None) -> dict[str, int]:
    """Score pending predictions whose actual outcome is known on ``as_of``."""
    as_of = as_of or date.today()
    now = _now()
    counts = {"evaluated": 0, "not_evaluable": 0, "pending": 0}
    _evaluate_milestones(db, as_of, now, counts)
    _evaluate_demand(db, as_of, now, counts)
    _evaluate_finance(db, as_of, now, counts)
    _evaluate_projects(db, as_of, now, counts)
    db.flush()
    return counts


def _evaluate_projects(db: Session, as_of: date, now: datetime, counts: dict[str, int]) -> None:
    pending = list(
        db.scalars(
            select(Prediction).where(
                Prediction.outcome_status == OUTCOME_PENDING,
                Prediction.prediction_type.in_(PROJECT_EVALUATORS),
                Prediction.project_id.is_not(None),
            )
        )
    )
    if not pending:
        return
    projects = {p.id: p for p in db.scalars(select(Project).where(Project.id.in_({p.project_id for p in pending})))}
    completed = [
        p for p in projects.values()
        if not p.is_deleted and p.execution_status == ExecutionStatus.completed
        and p.completed_at is not None and p.completed_at.date() <= as_of
    ]
    facts = load_facts(db, completed, as_of)
    for prediction in pending:
        project = projects.get(prediction.project_id)
        if project is None or project.is_deleted:
            _close(prediction, now, "The project was deleted.")
        elif project.execution_status == ExecutionStatus.cancelled:
            _close(prediction, now, "The project was cancelled.")
        elif prediction.project_id in facts and facts[prediction.project_id].completed_on >= prediction.as_of:
            PROJECT_EVALUATORS[prediction.prediction_type](prediction, facts[prediction.project_id], as_of, now)
        elif prediction.project_id in facts:
            _close(prediction, now, "The recorded completion is earlier than the prediction date.")
        _tally(counts, prediction)
