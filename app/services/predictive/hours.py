"""Final engineering-hours prediction (hours-1). Never changes quoted or approved hours."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.prediction import PREDICTED
from app.services.predictive.inputs import ProjectFacts, comparable_group, type_label
from app.services.predictive.stats import MIN_RANGE_SAMPLE, MIN_SAMPLE, central, quantile, share
from app.services.predictive.types import CALCULATION, Outcome, factor, hours

TYPE = "project_final_hours"
VERSION = "hours-1"


@dataclass(frozen=True)
class HoursSample:
    facts: ProjectFacts
    original: float
    actual: float

    @property
    def ratio(self) -> float:
        return self.actual / self.original


def hours_samples(history: list[ProjectFacts]) -> list[HoursSample]:
    """Phase 3 sample rule: approved original estimate above zero and recorded actuals above zero."""
    out = []
    for f in history:
        if f.completed_on is None or not f.estimate_approved or f.actual_status != "recorded":
            continue
        if not f.original_estimate or f.original_estimate <= 0 or not f.actual_hours or f.actual_hours <= 0:
            continue
        out.append(HoursSample(f, float(f.original_estimate), float(f.actual_hours)))
    return out


def _warnings(target: ProjectFacts) -> list[str]:
    notes = []
    if target.unapproved_hours or target.rejected_hours:
        notes.append(
            f"Actual hours are approved time only: {target.unapproved_hours} h on draft or submitted and "
            f"{target.rejected_hours} h on rejected timesheets are not included."
        )
    if "stage_attribution_incomplete" in target.issue_codes:
        notes.append("Hours are not fully linked to stages, so stage history is not used.")
    return notes


def predict_final_hours(target: ProjectFacts, samples: list[HoursSample], as_of: date, *,
                        scope_factor: float = 1.0) -> Outcome:
    out = Outcome(
        prediction_type=TYPE,
        subject_type="project",
        subject_key=f"project:{target.project_id}",
        subject_label=target.label,
        unit="hours",
        project_id=target.project_id,
        customer_id=target.customer_id,
        team_id=target.team_id,
        baseline_label="Current approved estimate",
        baseline_value=target.current_estimate,
        horizon_start=as_of,
        horizon_end=target.current_target,
        data_used={
            "quoted_hours": str(target.quoted_hours) if target.quoted_hours is not None else None,
            "approved_original_estimate": str(target.original_estimate) if target.original_estimate is not None else None,
            "approved_current_estimate": str(target.current_estimate) if target.current_estimate is not None else None,
            "actual_hours": str(target.actual_hours) if target.actual_hours is not None else None,
            "actual_status": target.actual_status,
            "estimate_source": target.estimate_source,
            "history_projects_considered": len(samples),
        },
        warnings=_warnings(target),
    )
    if not target.estimate_approved or target.original_estimate is None or target.original_estimate <= 0:
        out.factors.append(factor("Quoted hours", str(target.quoted_hours) if target.quoted_hours is not None else None,
                                  detail="Commercial figure; not used as an approved estimate."))
        return out.insufficient(
            "No approved estimate (stage estimates or milestone planned hours). Quoted hours are a commercial figure "
            "and are not used to predict effort."
        )
    if target.actual_status == "missing":
        return out.insufficient("Actual hours are missing (a cached total exists without timesheet entries).")
    actual = float(target.actual_hours or 0)
    if target.actual_status == "none_recorded":
        out.warnings.append("No timesheet hours are recorded on this project yet.")
    label, group, largest = comparable_group(target, samples)
    if not group:
        return out.insufficient(
            f"Only {largest} completed project(s) of the same type ({type_label(target)}) have an approved estimate and "
            f"recorded actual hours; at least {MIN_SAMPLE} are needed. Projects of other types are not used."
        )
    original = float(target.original_estimate) * scope_factor
    finals = [original * s.ratio for s in group]
    conditional = [f for f in finals if f > actual]
    out.sample_size = len(group)
    out.comparison_group = f"{len(group)} completed projects, {label}"
    if len(conditional) < MIN_SAMPLE:
        return out.insufficient(
            f"{hours(actual)} h are already recorded, more than the final hours {len(group) - len(conditional)} of "
            f"{len(group)} comparable projects would imply; history cannot say how much work remains."
        )
    predicted = central(conditional)
    out.status = PREDICTED
    out.predicted_value = hours(predicted)
    if len(conditional) >= MIN_RANGE_SAMPLE:
        out.lower_value = hours(quantile(conditional, 0.1))
        out.upper_value = hours(quantile(conditional, 0.9))
        out.range_basis = f"10th–90th percentile of {len(conditional)} comparable outcomes still above the hours recorded"
    if target.current_estimate is not None:
        approved = float(target.current_estimate)
        out.variance_value = hours(predicted - approved)
        out.observed_frequency = Decimal(str(round(share(conditional, lambda f: f > approved), 4)))
    ratios = [s.ratio for s in group]
    out.factors = [
        factor("Comparable projects", out.comparison_group, role=CALCULATION),
        factor("Median actual ÷ original estimate", round(central(ratios), 3), role=CALCULATION,
               detail="How far comparable projects ended above (>1) or below (<1) their original approved estimate."),
        factor("Hours recorded so far", hours(actual), role=CALCULATION,
               detail="Only comparable outcomes above this are used, so the prediction is never below hours already spent."),
        factor("Expected remaining hours", hours(predicted - actual), role=CALCULATION),
    ]
    if target.current_estimate is not None and target.original_estimate != target.current_estimate:
        out.factors.append(factor("Approved estimate revised", f"{target.original_estimate} h → {target.current_estimate} h",
                                  detail="The prediction starts from the original estimate so later revisions do not hide overruns."))
    if scope_factor != 1.0:
        out.factors.append(factor("Scope change (scenario)", f"{(scope_factor - 1) * 100:+.0f}%", role=CALCULATION))
    if target.current_estimate is not None and float(target.current_estimate) > 0:
        out.factors.append(factor("Approved hours used so far", f"{actual / float(target.current_estimate) * 100:.0f}%",
                                  detail="Context only: share of the approved estimate already booked."))
    return out
