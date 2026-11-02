"""Project completion-date prediction (delivery-1). Never changes project dates.

Duration is measured in calendar days from the project start to its completion stamp and scaled
by the approved original estimate. Milestone counts and percent complete are reported as context
only; they never stand in for elapsed time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.models.prediction import PREDICTED
from app.services.predictive.inputs import ProjectFacts, comparable_group, type_label
from app.services.predictive.stats import MIN_RANGE_SAMPLE, MIN_SAMPLE, central, quantile, share
from app.services.predictive.types import CALCULATION, Outcome, factor

TYPE = "project_delivery"
VERSION = "delivery-1"


@dataclass(frozen=True)
class DurationSample:
    facts: ProjectFacts
    days: int
    original: float

    @property
    def days_per_hour(self) -> float:
        return self.days / self.original


def duration_samples(history: list[ProjectFacts]) -> list[DurationSample]:
    """A start date, a completion after it, and an approved original estimate above zero."""
    out = []
    for f in history:
        if f.completed_on is None or f.start_date is None or f.completed_on <= f.start_date:
            continue
        if not f.estimate_approved or not f.original_estimate or f.original_estimate <= 0:
            continue
        out.append(DurationSample(f, (f.completed_on - f.start_date).days, float(f.original_estimate)))
    return out


@dataclass(frozen=True)
class CapacityCheck:
    """Earliest date the assigned designer can finish the remaining hours, after other assigned work."""
    finish: date | None
    remaining_hours: Decimal
    note: str


def predict_delivery(target: ProjectFacts, samples: list[DurationSample], as_of: date, *,
                     scope_factor: float = 1.0, extra_delay_days: int = 0,
                     capacity: CapacityCheck | None = None) -> Outcome:
    out = Outcome(
        prediction_type=TYPE,
        subject_type="project",
        subject_key=f"project:{target.project_id}",
        subject_label=target.label,
        unit="days",
        project_id=target.project_id,
        customer_id=target.customer_id,
        team_id=target.team_id,
        baseline_label="Current target date",
        baseline_date=target.current_target,
        horizon_start=as_of,
        horizon_end=target.current_target,
        data_used={
            "start_date": target.start_date.isoformat() if target.start_date else None,
            "start_source": target.start_source,
            "committed_date": target.committed_date.isoformat() if target.committed_date else None,
            "committed_source": target.committed_source,
            "current_target": target.current_target.isoformat() if target.current_target else None,
            "approved_original_estimate": str(target.original_estimate) if target.original_estimate is not None else None,
            "open_milestones": target.open_milestones,
            "overdue_milestones": target.overdue_milestones,
            "history_projects_considered": len(samples),
        },
    )
    if target.start_date is None:
        return out.insufficient(
            "No start date (actual, planned or baseline) is recorded, so elapsed time cannot be measured."
        )
    if not target.estimate_approved or target.original_estimate is None or target.original_estimate <= 0:
        return out.insufficient(
            "No approved estimate, so the project's size cannot be compared with completed projects."
        )
    label, group, largest = comparable_group(target, samples)
    if not group:
        return out.insufficient(
            f"Only {largest} completed project(s) of the same type ({type_label(target)}) have a start date, a "
            f"completion date and an approved estimate; at least {MIN_SAMPLE} are needed."
        )
    elapsed = max(0, (as_of - target.start_date).days)
    original = float(target.original_estimate) * scope_factor
    durations = [original * s.days_per_hour for s in group]
    conditional = [d for d in durations if d > elapsed]
    out.sample_size = len(group)
    out.comparison_group = f"{len(group)} completed projects, {label}"
    if len(conditional) < MIN_SAMPLE:
        return out.insufficient(
            f"The project has already run {elapsed} days, longer than {len(group) - len(conditional)} of "
            f"{len(group)} comparable projects would imply; history cannot say how much longer it will take."
        )

    def to_date(days: float) -> date:
        return target.start_date + timedelta(days=math.ceil(days) + extra_delay_days)

    predicted = to_date(central(conditional))
    out.status = PREDICTED
    out.factors = [
        factor("Comparable projects", out.comparison_group, role=CALCULATION),
        factor("Median calendar days per estimated hour", round(central([s.days_per_hour for s in group]), 3),
               role=CALCULATION),
        factor("Days elapsed since start", elapsed, role=CALCULATION,
               detail=f"From the {target.start_source}. Only comparable outcomes longer than this are used."),
    ]
    if scope_factor != 1.0:
        out.factors.append(factor("Scope change (scenario)", f"{(scope_factor - 1) * 100:+.0f}%", role=CALCULATION))
    if extra_delay_days:
        out.factors.append(factor("Added delay (scenario)", f"{extra_delay_days} days", role=CALCULATION))
    capacity_binds = capacity is not None and capacity.finish is not None and capacity.finish > predicted
    if capacity is not None:
        out.data_used["capacity_check"] = {
            "finish": capacity.finish.isoformat() if capacity.finish else None,
            "remaining_hours": str(capacity.remaining_hours),
            "note": capacity.note,
        }
        out.factors.append(factor("Designer capacity", capacity.finish.isoformat() if capacity.finish else None,
                                  role=CALCULATION if capacity_binds else "context", detail=capacity.note))
    if capacity_binds:
        predicted = capacity.finish
        out.warnings.append("The assigned designer's available capacity, not comparable history, sets this date.")
    elif len(conditional) >= MIN_RANGE_SAMPLE:
        out.lower_date = to_date(quantile(conditional, 0.1))
        out.upper_date = to_date(quantile(conditional, 0.9))
        out.range_basis = f"10th–90th percentile of {len(conditional)} comparable durations longer than the time elapsed"
    out.predicted_date = predicted
    if target.current_target is not None:
        out.variance_value = Decimal((predicted - target.current_target).days)
        if not capacity_binds:
            deadline = (target.current_target - target.start_date).days - extra_delay_days
            out.observed_frequency = Decimal(str(round(share(conditional, lambda d: math.ceil(d) > deadline), 4)))
        if target.current_target < as_of:
            out.warnings.append("The current target date has already passed (an operational overdue alert, not a prediction).")
    else:
        out.warnings.append("No current target date, so no delivery variance can be stated.")
    if target.committed_date and target.current_target and target.committed_date != target.current_target:
        out.factors.append(factor("Target moved since commitment", f"{target.target_moved_days} days",
                                  detail=f"Committed {target.committed_date}, current target {target.current_target}."))
    if target.overdue_milestones:
        out.factors.append(factor("Overdue milestones", target.overdue_milestones,
                                  detail="Context only; the date comes from elapsed time and comparable durations."))
    if target.open_without_target:
        out.factors.append(factor("Open milestones without a target date", target.open_without_target))
    if target.designer_id is None:
        out.warnings.append("No designer is assigned, so capacity was not checked.")
    return out
