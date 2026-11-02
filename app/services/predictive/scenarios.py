"""What-if scenarios for one open project: hypothetical inputs, the same predictors, never applied.

A scenario runs the stored-run predictors on modified copies of the project's inputs and compares the
result with a baseline computed from the same data with no assumptions. Only ``prediction_scenarios``
is written; project dates, estimates, assignments and capacity are never changed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType
from app.models.models import Project, User
from app.models.prediction import PREDICTED, PredictionScenario, PredictionSetting
from app.services.activity_service import log_activity
from app.services.predictive import delivery, hours, milestone, resources
from app.services.predictive.engine import RunContext, capacity_checks
from app.services.predictive.types import Outcome

HYPOTHETICAL_LABEL = "Hypothetical scenario: not a plan, a commitment or a change to the project."
MAX_PER_PROJECT = 20
LOAD_WEEKS = 4
SCENARIO_LIMITS = [
    "Scenarios use the same comparable history and models as the stored predictions; they do not make an "
    "uncertain forecast more certain.",
    "A different designer only changes the capacity check: comparable history is not specific to a designer.",
    "Added support hours are assumed to be fully available for this project on the designer's working days.",
]


class ScenarioError(ValueError):
    pass


@dataclass(frozen=True)
class Assumptions:
    scope_change_percent: Decimal = Decimal(0)
    extra_delay_days: int = 0
    target_shift_days: int = 0
    milestone_delays: dict[str, int] = field(default_factory=dict)
    designer_id: UUID | None = None
    added_hours_per_week: Decimal = Decimal(0)
    start_date: date | None = None

    @property
    def scope_factor(self) -> float:
        return float(1 + self.scope_change_percent / 100)

    def to_json(self) -> dict:
        data = asdict(self)
        return {k: (str(v) if isinstance(v, (Decimal, UUID, date)) else v) for k, v in data.items()}

    @classmethod
    def from_json(cls, data: dict) -> Assumptions:
        return cls(
            scope_change_percent=Decimal(str(data.get("scope_change_percent") or 0)),
            extra_delay_days=int(data.get("extra_delay_days") or 0),
            target_shift_days=int(data.get("target_shift_days") or 0),
            milestone_delays={str(k): int(v) for k, v in (data.get("milestone_delays") or {}).items()},
            designer_id=UUID(data["designer_id"]) if data.get("designer_id") else None,
            added_hours_per_week=Decimal(str(data.get("added_hours_per_week") or 0)),
            start_date=date.fromisoformat(data["start_date"]) if data.get("start_date") else None,
        )

    def is_empty(self) -> bool:
        return self == Assumptions()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _outcome(o: Outcome | None) -> dict | None:
    if o is None:
        return None
    return json.loads(json.dumps({
        "status": o.status, "reason": o.reason, "unit": o.unit, "label": o.subject_label,
        "predicted_value": o.predicted_value, "predicted_date": o.predicted_date,
        "lower_value": o.lower_value, "upper_value": o.upper_value, "lower_date": o.lower_date, "upper_date": o.upper_date,
        "range_basis": o.range_basis, "observed_frequency": o.observed_frequency,
        "baseline_label": o.baseline_label, "baseline_value": o.baseline_value, "baseline_date": o.baseline_date,
        "variance_value": o.variance_value, "sample_size": o.sample_size, "comparison_group": o.comparison_group,
        "factors": o.factors, "warnings": o.warnings,
    }, default=str))


def _with_support(supply: dict[UUID, resources.PersonSupply], person_id: UUID | None,
                  per_week: Decimal) -> dict[UUID, resources.PersonSupply]:
    if not per_week or person_id not in supply:
        return supply
    person = supply[person_id]
    extra = per_week / 5
    daily = {d: v + extra if d in person.working_days else v for d, v in person.daily.items()}
    return {**supply, person_id: replace(person, daily=daily)}


def _enabled(db: Session) -> set[str]:
    return set(db.scalars(select(PredictionSetting.prediction_type).where(PredictionSetting.is_enabled.is_(True))))


def _evaluate(ctx: RunContext, project_id: UUID, a: Assumptions, enabled: set[str], include_load: bool) -> dict:
    as_of = ctx.as_of
    facts = ctx.open_facts[project_id]
    changes = {}
    if a.designer_id:
        changes["designer_id"] = a.designer_id
    if a.start_date and facts.start_date is None:
        changes.update(start_date=a.start_date, start_source="scenario start date")
    if a.target_shift_days and facts.current_target is not None:
        changes["current_target"] = facts.current_target + timedelta(days=a.target_shift_days)
    target = facts.with_changes(**changes) if changes else facts
    supply = _with_support(ctx.supply, target.designer_id, a.added_hours_per_week)

    others = [f for pid, f in ctx.open_facts.items() if pid != project_id]
    all_facts = [*others, target]
    finals = {f.project_id: hours.predict_final_hours(f, ctx.hours_samples, as_of) for f in others}
    final = hours.predict_final_hours(target, ctx.hours_samples, as_of, scope_factor=a.scope_factor)
    finals[project_id] = final
    bases = {f.project_id: delivery.predict_delivery(f, ctx.duration_samples, as_of) for f in others}
    base = delivery.predict_delivery(target, ctx.duration_samples, as_of, scope_factor=a.scope_factor,
                                     extra_delay_days=a.extra_delay_days)
    bases[project_id] = base
    done = base
    if base.predicted:
        check = capacity_checks(all_facts, bases, finals, supply, as_of).get(project_id)
        if check is not None:
            done = delivery.predict_delivery(target, ctx.duration_samples, as_of, scope_factor=a.scope_factor,
                                             extra_delay_days=a.extra_delay_days, capacity=check)
    delays = {}
    for key, days in a.milestone_delays.items():
        try:
            delays[UUID(key)] = days
        except ValueError:
            continue
    milestones = milestone.predict_project_milestones(ctx.open_milestones.get(project_id, []), ctx.milestone_samples,
                                                      as_of, extra_delay=delays)
    result = {
        "final_hours": _outcome(final) if hours.TYPE in enabled else None,
        "delivery": _outcome(done) if delivery.TYPE in enabled else None,
        "milestones": [_outcome(m) for m in milestones] if milestone.TYPE in enabled else [],
        "designer_load": None,
    }
    if include_load and resources.TYPE in enabled and target.designer_id in supply:
        bases[project_id] = done
        demands, unknown = resources.project_demands(all_facts, finals, bases, as_of, supply)
        person = supply[target.designer_id]
        start, end = as_of + timedelta(days=1), as_of + timedelta(days=7 * LOAD_WEEKS)
        load = resources.person_load(demands).get(person.user_id, {})
        demand = sum((v for d, v in load.items() if start <= d <= end), Decimal(0))
        capacity = sum((v for d, v in person.daily.items() if start <= d <= end), Decimal(0))
        gaps = sum(1 for f in unknown if f.designer_id == person.user_id)
        result["designer_load"] = {
            "designer_id": str(person.user_id), "designer_name": person.name, "weeks": LOAD_WEEKS,
            "demand_hours": str(demand.quantize(Decimal("0.01"))),
            "capacity_hours": str(capacity.quantize(Decimal("0.01"))),
            "utilisation_percent": str((demand / capacity * 100).quantize(Decimal("0.1"))) if capacity > 0 else None,
            "projects_without_estimate": gaps,
        }
    return result


def _fmt(row: dict | None) -> str:
    if row is None:
        return "Disabled"
    if row["status"] != PREDICTED:
        return "Cannot be predicted"
    if row.get("predicted_date"):
        return row["predicted_date"]
    return f"{row['predicted_value']} h"


def _difference(base: dict | None, alt: dict | None) -> str | None:
    if not base or not alt or base["status"] != PREDICTED or alt["status"] != PREDICTED:
        return None
    if base.get("predicted_date") and alt.get("predicted_date"):
        days = (date.fromisoformat(alt["predicted_date"]) - date.fromisoformat(base["predicted_date"])).days
        return f"{days:+d} days"
    return f"{Decimal(alt['predicted_value']) - Decimal(base['predicted_value']):+} h"


def compare(baseline: dict, scenario: dict) -> list[dict]:
    rows = [
        {"measure": "Predicted final hours", "baseline": _fmt(baseline["final_hours"]),
         "scenario": _fmt(scenario["final_hours"]), "difference": _difference(baseline["final_hours"], scenario["final_hours"])},
        {"measure": "Predicted completion", "baseline": _fmt(baseline["delivery"]),
         "scenario": _fmt(scenario["delivery"]), "difference": _difference(baseline["delivery"], scenario["delivery"])},
    ]
    targets = [(row or {}).get("baseline_date") for row in (baseline["delivery"], scenario["delivery"])]
    if targets[0] != targets[1]:
        rows.append({"measure": "Target date compared against", "baseline": targets[0] or "None",
                     "scenario": targets[1] or "None", "difference": None})
    by_label = {m["label"]: m for m in baseline["milestones"]}
    for alt in scenario["milestones"]:
        base = by_label.get(alt["label"])
        rows.append({"measure": f"Milestone: {alt['label']}", "baseline": _fmt(base), "scenario": _fmt(alt),
                     "difference": _difference(base, alt)})
    if baseline.get("designer_load") or scenario.get("designer_load"):
        def load(row):
            if not row:
                return "Not available"
            pct = row["utilisation_percent"]
            return f"{row['designer_name']}: {pct}% of capacity" if pct is not None else f"{row['designer_name']}: no capacity"
        rows.append({"measure": f"Designer load, next {LOAD_WEEKS} weeks", "baseline": load(baseline.get("designer_load")),
                     "scenario": load(scenario.get("designer_load")), "difference": None})
    return rows


def evaluate_scenario(db: Session, project: Project, assumptions: Assumptions, *, as_of: date | None = None,
                      include_load: bool = True) -> dict:
    """Baseline (no assumptions) and scenario results for one open project. Writes nothing."""
    as_of = as_of or date.today()
    ctx = RunContext(db, as_of)
    if project.id not in ctx.open_facts:
        raise ScenarioError("Scenarios are only available for open projects.")
    if assumptions.designer_id and assumptions.designer_id not in ctx.supply:
        raise ScenarioError("The chosen designer is not a capacity-planning user, so their capacity is unknown.")
    known = {str(m.milestone_id) for m in ctx.open_milestones.get(project.id, [])}
    unknown = [k for k in assumptions.milestone_delays if k not in known]
    if unknown:
        raise ScenarioError("Milestone delays may only refer to this project's open milestones.")
    enabled = _enabled(db)
    baseline = _evaluate(ctx, project.id, Assumptions(), enabled, include_load)
    scenario = _evaluate(ctx, project.id, assumptions, enabled, include_load)
    warnings = list(SCENARIO_LIMITS)
    if assumptions.start_date and ctx.open_facts[project.id].start_date is not None:
        warnings.append("The project already has a recorded start date, so the hypothetical start date was not used.")
    if assumptions.target_shift_days and ctx.open_facts[project.id].current_target is None:
        warnings.append("The project has no current target date, so the target shift was not applied.")
    disabled = sorted({hours.TYPE, delivery.TYPE, milestone.TYPE, resources.TYPE} - enabled)
    if disabled:
        warnings.append(f"Disabled by an administrator and not shown: {', '.join(disabled)}.")
    return {
        "label": HYPOTHETICAL_LABEL,
        "as_of": as_of.isoformat(),
        "project": {"id": str(project.id), "label": ctx.open_facts[project.id].label},
        "assumptions": assumptions.to_json(),
        "model_versions": {hours.TYPE: hours.VERSION, delivery.TYPE: delivery.VERSION,
                           milestone.TYPE: milestone.VERSION, resources.TYPE: resources.VERSION},
        "baseline": baseline,
        "scenario": scenario,
        "comparison": compare(baseline, scenario),
        "warnings": warnings,
    }


def _log(db: Session, user: User, scenario: PredictionScenario, action: ActivityAction, detail: dict) -> None:
    log_activity(db, user=user, entity_type=EntityType.prediction_scenario, entity_id=scenario.id, action=action,
                 new_value=json.dumps({"name": scenario.name, "project_id": str(scenario.project_id), **detail}, default=str),
                 outcome="success", module="predictive", commit=False)


def save_scenario(db: Session, project: Project, *, name: str, assumptions: Assumptions, user: User,
                  include_load: bool = True, scenario: PredictionScenario | None = None) -> PredictionScenario:
    """Create a scenario, or recalculate an existing one with new name or assumptions."""
    name = name.strip()
    if not name:
        raise ScenarioError("Give the scenario a name.")
    if assumptions.is_empty():
        raise ScenarioError("A scenario needs at least one assumption; with none it equals the baseline.")
    if scenario is None:
        count = db.scalar(select(func.count(PredictionScenario.id)).where(
            PredictionScenario.project_id == project.id, PredictionScenario.is_deleted.is_(False)))
        if (count or 0) >= MAX_PER_PROJECT:
            raise ScenarioError(f"A project can have at most {MAX_PER_PROJECT} saved scenarios; delete one first.")
    result = evaluate_scenario(db, project, assumptions, include_load=include_load)
    if scenario is None:
        scenario = PredictionScenario(project_id=project.id, created_by_id=user.id)
        db.add(scenario)
    else:
        scenario.updated_by_id = user.id
    scenario.name = name[:200]
    scenario.as_of = date.fromisoformat(result["as_of"])
    scenario.assumptions_json = json.dumps(assumptions.to_json())
    scenario.result_json = json.dumps(result, default=str)
    scenario.model_versions_json = json.dumps(result["model_versions"])
    db.flush()
    _log(db, user, scenario, ActivityAction.prediction_scenario_saved, {"assumptions": assumptions.to_json()})
    db.commit()
    db.refresh(scenario)
    return scenario


def delete_scenario(db: Session, scenario: PredictionScenario, *, user: User) -> None:
    scenario.is_deleted = True
    scenario.deleted_at = _now()
    scenario.updated_by_id = user.id
    _log(db, user, scenario, ActivityAction.prediction_scenario_deleted, {})
    db.commit()


def project_scenarios(db: Session, project_id: UUID) -> list[PredictionScenario]:
    return list(db.scalars(select(PredictionScenario).where(
        PredictionScenario.project_id == project_id, PredictionScenario.is_deleted.is_(False),
    ).order_by(PredictionScenario.created_at)))
