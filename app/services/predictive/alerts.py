"""Predictive Control Tower findings from the latest stored predictions.

Separate from operational findings (``source = predictive``) and suppressed whenever the matching
operational condition is already true, so one problem never appears twice. Only active-version,
non-shadow predictions from enabled types and from the last week are used.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ProjectRiskType
from app.models.models import Project
from app.models.prediction import PREDICTED, Prediction, PredictionSetting
from app.services.predictive import delivery, hours, milestone, resources

MAX_AGE_DAYS = 8
DELAY_HIGH_DAYS = 14
OVERRUN_MIN = Decimal("0.10")
OVERRUN_HIGH = Decimal("0.25")
UTILISATION_HIGH = Decimal("150")
FORECAST_CAVEAT = (
    "This is a forecast from comparable completed work, not a certainty. Nothing has been changed; any revision "
    "goes through the normal approval workflow."
)


def _latest(db: Session, types: tuple[str, ...], today: date) -> list[Prediction]:
    enabled = set(db.scalars(select(PredictionSetting.prediction_type).where(PredictionSetting.is_enabled.is_(True))))
    wanted = [t for t in types if t in enabled]
    if not wanted:
        return []
    return list(db.scalars(select(Prediction).where(
        Prediction.prediction_type.in_(wanted),
        Prediction.is_latest.is_(True),
        Prediction.is_shadow.is_(False),
        Prediction.status == PREDICTED,
        Prediction.as_of >= today - timedelta(days=MAX_AGE_DAYS),
    )))


def _evidence(p: Prediction) -> list[tuple[str, str]]:
    unit = " h" if p.unit == "hours" else ""
    value = p.predicted_date.isoformat() if p.predicted_date else f"{p.predicted_value}{unit}"
    lines = [("Forecast", value)]
    if p.lower_date or p.lower_value is not None:
        low = p.lower_date.isoformat() if p.lower_date else f"{p.lower_value}{unit}"
        high = p.upper_date.isoformat() if p.upper_date else f"{p.upper_value}{unit}"
        lines.append(("Likely range", f"{low} to {high} ({p.range_basis})"))
    else:
        lines.append(("Likely range", "Not shown: fewer than 10 comparable outcomes"))
    baseline = p.baseline_date.isoformat() if p.baseline_date else (f"{p.baseline_value}{unit}" if p.baseline_value is not None else "Not recorded")
    lines.append((p.baseline_label or "Baseline", baseline))
    if p.variance_value is not None:
        suffix = " days" if p.unit == "days" else unit
        lines.append(("Forecast variance", f"{p.variance_value:+}{suffix}"))
    if p.observed_frequency is not None:
        lines.append(("Comparable history beyond the baseline", f"{p.observed_frequency * 100:.0f}% (an observed share, not a probability)"))
    lines.append(("Comparable history", p.comparison_group or f"{p.sample_size} cases"))
    lines.append(("Model", f"{p.model_version}, predicted on {p.as_of.isoformat()}"))
    return lines


def predictive_detections(db: Session, projects: list[Project], today: date, operational: list,
                          allowed: dict[UUID, set[ProjectRiskType]]) -> list:
    from app.services.control_tower_service import Detection, _project_owner

    by_id = {p.id: p for p in projects}
    live = {(d.rule_id, d.project_id, d.milestone_id) for d in operational if d.not_assessable_reason is None}
    rows = _latest(db, (delivery.TYPE, hours.TYPE, milestone.TYPE, resources.TYPE), today)
    out = []

    def make(rule_id, project, p, severity, title, explanation, milestone_id=None, metrics=None, evidence=None,
             owner=None):
        owner_id, basis = owner or _project_owner(project)
        out.append(Detection(
            rule_id=rule_id, project_id=project.id, milestone_id=milestone_id, severity=severity, title=title,
            explanation=f"{explanation} {FORECAST_CAVEAT}", metrics=metrics or {}, evidence=evidence or _evidence(p),
            owner_user_id=owner_id, owner_basis=basis, source="predictive", prediction_id=p.id if p else None,
        ))

    for p in rows:
        project = by_id.get(p.project_id) if p.project_id else None
        if p.prediction_type == delivery.TYPE and project is not None:
            if ProjectRiskType.overdue not in allowed.get(project.id, set()):
                continue
            if ("project_past_target", project.id, None) in live or p.variance_value is None or p.variance_value <= 0:
                continue
            days = int(p.variance_value)
            make("delivery_forecast_risk", project, p, "high" if days >= DELAY_HIGH_DAYS else "medium",
                 f"Forecast to finish {days} days after its current target",
                 f"Comparable projects suggest completion around {p.predicted_date}, after the current target {p.baseline_date}.",
                 metrics={"forecast_variance_days": days, "predicted_date": p.predicted_date})
        elif p.prediction_type == hours.TYPE and project is not None:
            if ProjectRiskType.hours_over_quote not in allowed.get(project.id, set()):
                continue
            if ("estimate_overrun_realized", project.id, None) in live:
                continue
            if not p.baseline_value or p.variance_value is None or p.variance_value <= 0:
                continue
            share = p.variance_value / p.baseline_value
            if share < OVERRUN_MIN:
                continue
            make("estimate_overrun_forecast", project, p, "high" if share >= OVERRUN_HIGH else "medium",
                 f"Forecast to need {share * 100:.0f}% more hours than approved",
                 f"Comparable projects suggest about {p.predicted_value} h in total against {p.baseline_value} h approved.",
                 metrics={"forecast_overrun_hours": p.variance_value, "forecast_overrun_share": share.quantize(Decimal("0.001"))})
        elif p.prediction_type == milestone.TYPE and project is not None and p.milestone_id:
            if ProjectRiskType.milestone_delay not in allowed.get(project.id, set()):
                continue
            if ("milestone_overdue", project.id, p.milestone_id) in live or p.variance_value is None or p.variance_value <= 0:
                continue
            days = int(p.variance_value)
            make("milestone_delay_forecast", project, p, "high" if days >= DELAY_HIGH_DAYS else "medium",
                 f"Milestone forecast to finish {days} days late",
                 f"Comparable milestones suggest finishing around {p.predicted_date}, after its target {p.baseline_date}.",
                 milestone_id=p.milestone_id, metrics={"forecast_variance_days": days})
    _bottlenecks(rows, by_id, make)
    return out


def _bottlenecks(rows: list[Prediction], projects: dict[UUID, Project], make) -> None:
    """One finding per over-capacity designer, on their open project that ends first; no names are shown."""
    for p in rows:
        if p.prediction_type != resources.TYPE or p.subject_type != "person" or not p.subject_key.endswith(":4w"):
            continue
        data = json.loads(p.data_used_json or "{}")
        if not data.get("shortage") or not data.get("demand_complete", False):
            continue
        affected = [row for row in data.get("projects", []) if row.get("project_id") and UUID(row["project_id"]) in projects]
        if not affected:
            continue
        affected.sort(key=lambda row: row.get("end") or "9999-12-31")
        project = projects[UUID(affected[0]["project_id"])]
        utilisation = Decimal(data.get("utilisation_percent", "0"))
        weeks = data.get("overloaded_weeks", [])
        evidence = [
            ("Forecast project demand (next 4 weeks)", f"{p.predicted_value} h"),
            ("Capacity (allocatable, less historical non-project time)", f"{p.baseline_value} h"),
            ("Forecast utilisation", f"{utilisation}%"),
            ("Weeks over capacity", ", ".join(weeks) if weeks else "None individually"),
            ("Open projects contributing", str(len(affected))),
            ("Model", f"{p.model_version}, predicted on {p.as_of.isoformat()}"),
        ]
        make("resource_bottleneck", project, p, "high" if utilisation >= UTILISATION_HIGH else "medium",
             "Assigned designer forecast over capacity in the next 4 weeks",
             "The designer's forecast project work exceeds their capacity. Work is assumed to be spread evenly to "
             "each project's end date because ProTrack has no allocation plan.",
             metrics={"utilisation_percent": utilisation, "overloaded_weeks": weeks, "contributing_projects": len(affected)},
             evidence=evidence)
