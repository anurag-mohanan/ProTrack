"""Prediction runs: generate, persist and supersede. Writes only to the prediction tables."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import cached_property
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import Project
from app.models.prediction import (
    INSUFFICIENT,
    MODEL_CANDIDATE,
    OUTCOME_NOT_EVALUABLE,
    OUTCOME_PENDING,
    PREDICTED,
    RUN_FAILED,
    RUN_RUNNING,
    RUN_SUCCEEDED,
    Prediction,
    PredictionModelVersion,
    PredictionRun,
)
from app.services.predictive import delivery, finance, hours, milestone, registry, resources
from app.services.predictive.evaluation import evaluate_outcomes
from app.services.predictive.inputs import ProjectFacts, completed_projects, load_facts, open_projects
from app.services.predictive.types import Outcome

logger = logging.getLogger(__name__)

RUN_ABANDON_AFTER = timedelta(minutes=30)


class PredictionRunInProgress(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str)


class RunContext:
    """Inputs shared by all predictors in one run, loaded once and only when needed."""

    def __init__(self, db: Session, as_of: date):
        self.db = db
        self.as_of = as_of
        # Results of the active version per type, for predictors that build on another type.
        self.active: dict[str, list[Outcome]] = {}

    @cached_property
    def open_projects(self) -> list[Project]:
        return open_projects(self.db)

    @cached_property
    def open_facts(self) -> dict[UUID, ProjectFacts]:
        return load_facts(self.db, self.open_projects, self.as_of)

    @cached_property
    def history_facts(self) -> list[ProjectFacts]:
        return list(load_facts(self.db, completed_projects(self.db, self.as_of), self.as_of).values())

    @cached_property
    def hours_samples(self) -> list[hours.HoursSample]:
        return hours.hours_samples(self.history_facts)

    @cached_property
    def duration_samples(self) -> list[delivery.DurationSample]:
        return delivery.duration_samples(self.history_facts)

    @cached_property
    def open_milestones(self) -> dict[UUID, list[milestone.MilestoneFacts]]:
        return milestone.load_milestones(self.db, self.open_projects)

    @cached_property
    def milestone_samples(self) -> dict[str, list[milestone.MilestoneSample]]:
        history = milestone.load_milestones(self.db, completed_projects(self.db, self.as_of))
        return milestone.milestone_samples({**history, **self.open_milestones}, self.as_of)

    @cached_property
    def ledgers(self) -> list[finance.Ledger]:
        return finance.load_ledgers(self.db)

    @cached_property
    def finance_forecast(self):
        from app.services.forecasting.finance import build_finance_forecast

        return build_finance_forecast(self.db, as_of=self.as_of, granularity="month", periods=finance.PERIODS)

    @cached_property
    def supply(self) -> dict[UUID, resources.PersonSupply]:
        return resources.load_supply(self.db, self.as_of, self.as_of + timedelta(days=SUPPLY_DAYS))

    def active_by_project(self, prediction_type: str) -> dict[UUID, Outcome]:
        return {o.project_id: o for o in self.active.get(prediction_type, []) if o.project_id}


Generator = Callable[[RunContext], list[Outcome]]
SUPPLY_DAYS = 730


def _final_hours(ctx: RunContext) -> list[Outcome]:
    return [hours.predict_final_hours(f, ctx.hours_samples, ctx.as_of) for f in ctx.open_facts.values()]


def capacity_checks(facts: list[ProjectFacts], base: dict[UUID, Outcome], final_hours: dict[UUID, Outcome],
                    supply: dict[UUID, resources.PersonSupply], as_of: date) -> dict[UUID, delivery.CapacityCheck]:
    """Earliest finish of each project's remaining hours on its designer, after their other project work."""
    demands, _ = resources.project_demands(facts, final_hours, base, as_of, supply)
    load = resources.person_load(demands)
    checks = {}
    for d in demands:
        person = supply.get(d.owner_id) if d.owner_id else None
        if person is None:
            continue
        mine = d.daily
        other = {day: value - mine.get(day, Decimal(0)) for day, value in load.get(d.owner_id, {}).items()}
        finish = resources.capacity_finish(person, other, d.remaining, as_of)
        share = (f"less {person.non_project_share * 100:.0f}% historical non-project time"
                 if person.non_project_share is not None else "with no deduction for non-project time (too little timesheet history)")
        note = (f"{person.name} can cover the remaining {d.remaining.quantize(Decimal('0.1'))} h ({d.remaining_basis}) by "
                f"{finish} using allocatable capacity {share}, after their other assigned project work."
                if finish else
                f"{person.name} cannot cover the remaining {d.remaining.quantize(Decimal('0.1'))} h within "
                f"{resources.FINISH_SEARCH_DAYS} days at current capacity.")
        checks[d.facts.project_id] = delivery.CapacityCheck(finish, d.remaining, note)
    return checks


def _delivery(ctx: RunContext) -> list[Outcome]:
    facts = list(ctx.open_facts.values())
    base = {f.project_id: delivery.predict_delivery(f, ctx.duration_samples, ctx.as_of) for f in facts}
    checks = capacity_checks(facts, base, ctx.active_by_project(hours.TYPE), ctx.supply, ctx.as_of)
    return [
        delivery.predict_delivery(f, ctx.duration_samples, ctx.as_of, capacity=checks[f.project_id])
        if base[f.project_id].predicted and f.project_id in checks else base[f.project_id]
        for f in facts
    ]


def _milestones(ctx: RunContext) -> list[Outcome]:
    out: list[Outcome] = []
    for rows in ctx.open_milestones.values():
        out.extend(milestone.predict_project_milestones(rows, ctx.milestone_samples, ctx.as_of))
    return out


def _resource_demand(ctx: RunContext) -> list[Outcome]:
    from app.services.skills.gaps import requirement_coverage

    demands, unknown = resources.project_demands(
        list(ctx.open_facts.values()), ctx.active_by_project(hours.TYPE), ctx.active_by_project(delivery.TYPE),
        ctx.as_of, ctx.supply,
    )
    coverage = requirement_coverage(ctx.db, ctx.open_projects, ctx.as_of)
    return resources.build_outcomes(ctx.db, ctx.as_of, demands, unknown, ctx.supply, coverage)


def _billing(ctx: RunContext) -> list[Outcome]:
    completions = finance.completions_for(ctx.ledgers, ctx.active_by_project(delivery.TYPE))
    customers = {ledger.quote.id: ledger.quote.customer_id for ledger in ctx.ledgers}
    return finance.predict_billing(ctx.finance_forecast, finance.invoice_lags(ctx.ledgers, ctx.as_of), ctx.as_of,
                                   completions, customers)


def _collections(ctx: RunContext) -> list[Outcome]:
    return finance.predict_collections(ctx.finance_forecast, finance.payment_delays(ctx.ledgers, ctx.as_of), ctx.as_of)


# Order matters: a type may read the active results of a type listed before it.
GENERATORS: dict[tuple[str, str], Generator] = {
    (hours.TYPE, hours.VERSION): _final_hours,
    (delivery.TYPE, delivery.VERSION): _delivery,
    (milestone.TYPE, milestone.VERSION): _milestones,
    (resources.TYPE, resources.VERSION): _resource_demand,
    (finance.BILLING, finance.BILLING_VERSION): _billing,
    (finance.COLLECTIONS, finance.COLLECTIONS_VERSION): _collections,
}


def register_generator(prediction_type: str, version: str, generator: Generator) -> None:
    GENERATORS[(prediction_type, version)] = generator


def unregister_generator(prediction_type: str, version: str) -> None:
    GENERATORS.pop((prediction_type, version), None)


def type_order() -> list[str]:
    order: list[str] = []
    for key, _version in GENERATORS:
        if key not in order:
            order.append(key)
    return [*order, *(k for k in registry.TYPES if k not in order)]


def _start_run(db: Session, *, trigger: str, user_id: UUID | None, as_of: date) -> PredictionRun:
    now = _now()
    for running in db.scalars(select(PredictionRun).where(PredictionRun.status == RUN_RUNNING)).all():
        if now - running.started_at < RUN_ABANDON_AFTER:
            raise PredictionRunInProgress("A prediction run is already in progress.")
        running.status = RUN_FAILED
        running.finished_at = now
        running.error = "Abandoned: the run did not finish within 30 minutes."
    run = PredictionRun(trigger=trigger, triggered_by_id=user_id, as_of=as_of, status=RUN_RUNNING, started_at=now)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _row(outcome: Outcome, *, run_id: UUID, version: str, shadow: bool, as_of: date) -> Prediction:
    return Prediction(
        run_id=run_id,
        prediction_type=outcome.prediction_type,
        model_version=version,
        is_shadow=shadow,
        subject_type=outcome.subject_type,
        subject_key=outcome.subject_key,
        subject_label=outcome.subject_label[:300],
        project_id=outcome.project_id,
        milestone_id=outcome.milestone_id,
        team_id=outcome.team_id,
        customer_id=outcome.customer_id,
        currency=outcome.currency,
        as_of=as_of,
        horizon_start=outcome.horizon_start,
        horizon_end=outcome.horizon_end,
        status=outcome.status,
        reason=outcome.reason,
        unit=outcome.unit,
        predicted_value=outcome.predicted_value,
        predicted_date=outcome.predicted_date,
        lower_value=outcome.lower_value,
        upper_value=outcome.upper_value,
        lower_date=outcome.lower_date,
        upper_date=outcome.upper_date,
        range_basis=outcome.range_basis,
        observed_frequency=outcome.observed_frequency,
        baseline_label=outcome.baseline_label,
        baseline_value=outcome.baseline_value,
        baseline_date=outcome.baseline_date,
        variance_value=outcome.variance_value,
        sample_size=outcome.sample_size,
        comparison_group=outcome.comparison_group,
        factors_json=_json(outcome.factors),
        data_used_json=_json(outcome.data_used),
        warnings_json=_json(outcome.warnings),
        is_latest=True,
        counts_for_accuracy=outcome.status == PREDICTED,
        outcome_status=OUTCOME_PENDING if outcome.status == PREDICTED else OUTCOME_NOT_EVALUABLE,
        outcome_note=None if outcome.status == PREDICTED else "No prediction was made.",
    )


def _persist(db: Session, outcomes: list[Outcome], *, prediction_type: str, version: str, shadow: bool,
             run_id: UUID, as_of: date, now: datetime) -> dict[str, int]:
    previous = {
        p.subject_key: p
        for p in db.scalars(
            select(Prediction).where(
                Prediction.prediction_type == prediction_type,
                Prediction.model_version == version,
                Prediction.is_shadow.is_(shadow),
                Prediction.is_latest.is_(True),
            )
        )
    }
    counts = {PREDICTED: 0, INSUFFICIENT: 0, "superseded": 0}
    for outcome in outcomes:
        old = previous.pop(outcome.subject_key, None)
        if old is not None:
            old.is_latest = False
            old.superseded_at = now
            counts["superseded"] += 1
            if old.as_of == as_of and old.outcome_status == OUTCOME_PENDING:
                # Only the last prediction made on a given day is scored.
                old.counts_for_accuracy = False
                old.outcome_status = OUTCOME_NOT_EVALUABLE
                old.outcome_note = "Replaced by a later run on the same date."
        db.add(_row(outcome, run_id=run_id, version=version, shadow=shadow, as_of=as_of))
        counts[outcome.status] += 1
    # Subjects no longer predicted (project closed, period passed) keep their history but are not current.
    for old in previous.values():
        old.is_latest = False
        old.superseded_at = now
    return counts


def run_predictions(db: Session, *, as_of: date | None = None, trigger: str = "manual",
                    user_id: UUID | None = None) -> PredictionRun:
    """Run every enabled prediction type: the active version, plus candidate versions in shadow.

    On failure nothing from the run is kept except the run record marked ``failed``.
    """
    as_of = as_of or date.today()
    registry.sync(db)
    db.commit()
    run = _start_run(db, trigger=trigger, user_id=user_id, as_of=as_of)
    run_id = run.id
    try:
        settings = registry.sync(db)
        candidates = {
            (v.prediction_type, v.version)
            for v in db.scalars(select(PredictionModelVersion).where(PredictionModelVersion.status == MODEL_CANDIDATE))
        }
        ctx = RunContext(db, as_of)
        now = _now()
        counts: dict[str, dict] = {"outcomes": evaluate_outcomes(db, as_of)}
        for prediction_type in type_order():
            setting = settings[prediction_type]
            if not setting.is_enabled:
                counts[prediction_type] = {"disabled": True}
                continue
            active = GENERATORS.get((prediction_type, setting.active_version or ""))
            if active is None:
                counts[prediction_type] = {"not_implemented": True}
                continue
            outcomes = active(ctx)
            ctx.active[prediction_type] = outcomes
            counts[prediction_type] = _persist(db, outcomes, prediction_type=prediction_type,
                                               version=setting.active_version, shadow=False,
                                               run_id=run_id, as_of=as_of, now=now)
            for (ptype, version), generator in GENERATORS.items():
                if ptype != prediction_type or (ptype, version) not in candidates:
                    continue
                shadow = _persist(db, generator(ctx), prediction_type=ptype, version=version, shadow=True,
                                  run_id=run_id, as_of=as_of, now=now)
                counts[prediction_type].setdefault("shadow", {})[version] = shadow[PREDICTED]
        db.flush()
        run = db.get(PredictionRun, run_id)
        run.status = RUN_SUCCEEDED
        run.finished_at = _now()
        run.counts_json = _json(counts)
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        db.rollback()
        logger.exception("Prediction run %s failed", run_id)
        failed = db.get(PredictionRun, run_id)
        if failed is not None:
            failed.status = RUN_FAILED
            failed.finished_at = _now()
            failed.error = f"{type(exc).__name__}: {exc}"[:2000]
            db.commit()
        raise
