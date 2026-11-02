"""Prediction accuracy, model governance and enable/disable controls.

Accuracy is computed only from predictions that were scored against actual outcomes
(``outcome_status = evaluated`` and ``counts_for_accuracy``). Below ``MIN_EVALUATED`` scored
predictions no error figure is reported, only the count. A model version can only become active
when it is not measurably worse than the current one; when there is too little evidence either
way the change needs an explicit, audited note.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType
from app.models.models import User
from app.models.prediction import (
    MODEL_ACTIVE,
    MODEL_CANDIDATE,
    OUTCOME_EVALUATED,
    OUTCOME_NOT_EVALUABLE,
    OUTCOME_PENDING,
    Prediction,
    PredictionModelVersion,
    PredictionSetting,
)
from app.services.activity_service import log_activity
from app.services.predictive import registry

MIN_EVALUATED = 10
DEGRADATION_FACTOR = 1.25
RECENT_DAYS = 90
HORIZONS = ((0, 30, "0–30 days"), (31, 90, "31–90 days"), (91, 180, "91–180 days"), (181, None, "Over 180 days"))
CALIBRATION_BINS = ((0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01))
MIN_ACTIVATION_NOTE = 10


class GovernanceError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 2) if values else None


def _inside(r: Prediction) -> bool:
    if r.lower_date is not None and r.actual_date is not None:
        return r.lower_date <= r.actual_date <= r.upper_date
    if r.lower_value is not None and r.actual_value is not None:
        return r.lower_value <= r.actual_value <= r.upper_value
    return False


def _metrics(rows: list[Prediction]) -> dict:
    n = len(rows)
    out: dict = {"evaluated": n, "reportable": n >= MIN_EVALUATED}
    if n < MIN_EVALUATED:
        out["message"] = f"Only {n} prediction(s) scored against actual outcomes; at least {MIN_EVALUATED} are needed."
        return out
    errors = [float(r.abs_error) for r in rows if r.abs_error is not None]
    pct = [float(r.pct_error) for r in rows if r.pct_error is not None]
    naive = [(float(r.abs_error), float(r.naive_abs_error)) for r in rows
             if r.naive_abs_error is not None and r.abs_error is not None]
    signed = [float(r.error_value) for r in rows if r.error_value is not None]
    out.update(
        mean_absolute_error=_mean(errors),
        median_absolute_error=round(statistics.median(errors), 2) if errors else None,
        mean_bias=_mean(signed),
        mean_absolute_percentage_error=_mean(pct) if len(pct) >= MIN_EVALUATED else None,
        percentage_error_n=len(pct),
    )
    if len(naive) >= MIN_EVALUATED:
        model_mae, naive_mae = _mean([a for a, _ in naive]), _mean([b for _, b in naive])
        out["naive_baseline"] = {"n": len(naive), "model_mae": model_mae, "baseline_mae": naive_mae,
                                 "better_than_baseline": model_mae is not None and naive_mae is not None and model_mae < naive_mae}
    ranged = [r for r in rows if (r.lower_value is not None or r.lower_date is not None)
              and (r.actual_value is not None or r.actual_date is not None)]
    if len(ranged) >= MIN_EVALUATED:
        inside = sum(1 for r in ranged if _inside(r))
        out["range_coverage"] = {"n": len(ranged), "inside_share": round(inside / len(ranged), 3),
                                 "expected_share": 0.8}
    return out


def _calibration(rows: list[Prediction]) -> list[dict]:
    """Observed share at prediction time against how often the event then happened, per band."""
    pairs = [(float(r.observed_frequency), bool(r.event_occurred)) for r in rows
             if r.observed_frequency is not None and r.event_occurred is not None]
    out = []
    for low, high in CALIBRATION_BINS:
        band = [hit for share, hit in pairs if low <= share < high]
        row = {"band": f"{low:.0%}–{min(high, 1.0):.0%}", "n": len(band)}
        if len(band) >= MIN_EVALUATED:
            row["event_rate"] = round(sum(band) / len(band), 3)
        out.append(row)
    return out


def _horizons(rows: list[Prediction]) -> list[dict]:
    out = []
    for low, high, label in HORIZONS:
        band = [r for r in rows if r.horizon_days is not None and r.horizon_days >= low and (high is None or r.horizon_days <= high)]
        out.append({"horizon": label, **_metrics(band)})
    return out


def _degradation(rows: list[Prediction]) -> dict:
    cutoff = _now() - timedelta(days=RECENT_DAYS)
    recent = [float(r.abs_error) for r in rows if r.evaluated_at and r.evaluated_at >= cutoff and r.abs_error is not None]
    earlier = [float(r.abs_error) for r in rows if r.evaluated_at and r.evaluated_at < cutoff and r.abs_error is not None]
    if len(recent) < MIN_EVALUATED or len(earlier) < MIN_EVALUATED:
        return {"status": "insufficient", "recent_n": len(recent), "earlier_n": len(earlier),
                "message": f"Needs {MIN_EVALUATED} scored predictions in the last {RECENT_DAYS} days and before."}
    r, e = statistics.fmean(recent), statistics.fmean(earlier)
    degraded = r > e * DEGRADATION_FACTOR
    return {"status": "degraded" if degraded else "stable", "recent_n": len(recent), "earlier_n": len(earlier),
            "recent_mae": round(r, 2), "earlier_mae": round(e, 2),
            "message": (f"Recent error ({round(r, 2)}) is more than {DEGRADATION_FACTOR}× the earlier error ({round(e, 2)})."
                        if degraded else "No degradation detected.")}


def _scored(db: Session, prediction_type: str, version: str | None = None) -> list[Prediction]:
    stmt = select(Prediction).where(Prediction.prediction_type == prediction_type,
                                    Prediction.outcome_status == OUTCOME_EVALUATED,
                                    Prediction.counts_for_accuracy.is_(True))
    if version:
        stmt = stmt.where(Prediction.model_version == version)
    return list(db.scalars(stmt))


def version_accuracy(db: Session, prediction_type: str, version: str) -> dict:
    return _metrics(_scored(db, prediction_type, version))


def accuracy_report(db: Session, prediction_types: list[str]) -> list[dict]:
    settings = {s.prediction_type: s for s in db.scalars(select(PredictionSetting))}
    counts = dict(((t, s), n) for t, s, n in db.execute(
        select(Prediction.prediction_type, Prediction.outcome_status, func.count())
        .where(Prediction.is_shadow.is_(False), Prediction.prediction_type.in_(prediction_types or ["-"]))
        .group_by(Prediction.prediction_type, Prediction.outcome_status)))
    out = []
    for ptype in prediction_types:
        spec = registry.TYPES[ptype]
        setting = settings.get(ptype)
        active = setting.active_version if setting else None
        rows = [r for r in _scored(db, ptype, active) if not r.is_shadow] if active else []
        versions = []
        for v in db.scalars(select(PredictionModelVersion).where(PredictionModelVersion.prediction_type == ptype)
                            .order_by(PredictionModelVersion.registered_at)):
            versions.append({"version": v.version, "status": v.status, "description": v.description,
                             "registered_at": v.registered_at, "activated_at": v.activated_at,
                             "activation_note": v.activation_note, "accuracy": version_accuracy(db, ptype, v.version)})
        out.append({
            "prediction_type": ptype, "label": spec.label, "unit": spec.unit, "module": spec.module,
            "enabled": bool(setting.is_enabled) if setting else True,
            "disabled_reason": setting.disabled_reason if setting else None,
            "active_version": active,
            "pending": counts.get((ptype, OUTCOME_PENDING), 0),
            "not_evaluable": counts.get((ptype, OUTCOME_NOT_EVALUABLE), 0),
            "overall": _metrics(rows),
            "by_horizon": _horizons(rows),
            "calibration": _calibration(rows),
            "degradation": _degradation(rows),
            "versions": versions,
            "examples": [{"subject": r.subject_label, "predicted": str(r.predicted_date or r.predicted_value),
                          "actual": str(r.actual_date or r.actual_value), "abs_error": str(r.abs_error),
                          "as_of": r.as_of.isoformat()}
                         for r in sorted(rows, key=lambda r: r.evaluated_at or _now(), reverse=True)[:10]],
        })
    return out


@dataclass(frozen=True)
class ActivationCheck:
    allowed: bool
    needs_note: bool
    message: str


def activation_check(db: Session, prediction_type: str, version: str) -> ActivationCheck:
    setting = db.scalar(select(PredictionSetting).where(PredictionSetting.prediction_type == prediction_type))
    if setting is None or setting.active_version == version:
        return ActivationCheck(False, False, "This version is already active.")
    current = version_accuracy(db, prediction_type, setting.active_version) if setting.active_version else {"reportable": False}
    candidate = version_accuracy(db, prediction_type, version)
    if current.get("reportable") and candidate.get("reportable"):
        if candidate["mean_absolute_error"] > current["mean_absolute_error"]:
            return ActivationCheck(False, False, (
                f"Refused: {version} has a higher mean absolute error ({candidate['mean_absolute_error']}) than the "
                f"active {setting.active_version} ({current['mean_absolute_error']})."))
        return ActivationCheck(True, False, (
            f"{version} error {candidate['mean_absolute_error']} is not worse than {setting.active_version} "
            f"({current['mean_absolute_error']})."))
    return ActivationCheck(True, True, (
        f"Not enough scored predictions to compare ({candidate.get('evaluated', 0)} for {version}, "
        f"{current.get('evaluated', 0)} for the active version). Activation needs a recorded justification."))


def activate_version(db: Session, prediction_type: str, version: str, *, user: User, note: str | None) -> PredictionModelVersion:
    target = db.scalar(select(PredictionModelVersion).where(PredictionModelVersion.prediction_type == prediction_type,
                                                            PredictionModelVersion.version == version))
    if target is None:
        raise GovernanceError("Unknown model version.")
    check = activation_check(db, prediction_type, version)
    note = (note or "").strip()
    if not check.allowed:
        raise GovernanceError(check.message)
    if check.needs_note and len(note) < MIN_ACTIVATION_NOTE:
        raise GovernanceError(check.message)
    setting = db.scalar(select(PredictionSetting).where(PredictionSetting.prediction_type == prediction_type))
    previous = setting.active_version
    for v in db.scalars(select(PredictionModelVersion).where(PredictionModelVersion.prediction_type == prediction_type,
                                                             PredictionModelVersion.status == MODEL_ACTIVE)):
        v.status = MODEL_CANDIDATE  # keeps running in shadow so the comparison continues
    now = _now()
    target.status = MODEL_ACTIVE
    target.activated_at = now
    target.activated_by_id = user.id
    target.activation_note = f"{note} [{check.message}]" if note else check.message
    setting.active_version = version
    setting.updated_by_id = user.id
    log_activity(db, user=user, entity_type=EntityType.prediction_model, entity_id=target.id,
                 action=ActivityAction.prediction_model_activated, old_value=previous,
                 new_value=json.dumps({"type": prediction_type, "version": version, "note": note, "check": check.message}),
                 outcome="success", module="predictive", commit=False)
    db.commit()
    db.refresh(target)
    return target


def set_enabled(db: Session, prediction_type: str, enabled: bool, *, user: User, reason: str | None) -> PredictionSetting:
    """Disable or re-enable one prediction type. Stored predictions are kept; runs skip disabled types."""
    if prediction_type not in registry.TYPES:
        raise GovernanceError("Unknown prediction type.")
    registry.sync(db)
    setting = db.scalar(select(PredictionSetting).where(PredictionSetting.prediction_type == prediction_type))
    reason = (reason or "").strip() or None
    if not enabled and not reason:
        raise GovernanceError("Give a reason for disabling this prediction type.")
    previous = {"enabled": setting.is_enabled, "reason": setting.disabled_reason}
    setting.is_enabled = enabled
    setting.disabled_reason = None if enabled else reason[:500]
    setting.updated_by_id = user.id
    log_activity(db, user=user, entity_type=EntityType.prediction_setting, entity_id=setting.id,
                 action=ActivityAction.prediction_setting_changed, old_value=json.dumps(previous),
                 new_value=json.dumps({"type": prediction_type, "enabled": enabled, "reason": reason}),
                 outcome="success", module="predictive", commit=False)
    db.commit()
    db.refresh(setting)
    return setting
