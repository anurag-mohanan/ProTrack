"""Strategic objectives: targets, baselines, actuals, progress and history.

Automatic objectives read their actual from the KPI registry on every read; no manual value can
replace it. Manual objectives take dated measurements with evidence, appended (never edited).
Targets and baselines set or changed without approval rights stay *proposed*; changes by an
approver are recorded with the approver and reason. Financial and workforce figures are hidden
from people who may not see them.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.management import (
    DIRECTION_DECREASE,
    MEASURE_AUTOMATIC,
    MEASURE_MANUAL,
    ManagementAction,
    ObjectiveMeasurement,
    StrategicInitiative,
    StrategicObjective,
)
from app.models.models import Project, Team, User
from app.schemas.management import MeasurementCreate, ObjectiveCreate, ObjectiveUpdate, TargetChange
from app.services.finance.fy_calendar_service import company_fy_start_month
from app.services.management import kpis
from app.services.management.access import ManagementAccess, ManagementForbidden
from app.services.management.events import list_events, record_event, user_name
from app.services.management.filters import Period, sub_period
from app.services.management.metrics import CURRENCY, KPI_DEFINITIONS, number

ON_TRACK_SLACK = 10.0
AT_RISK_SLACK = 25.0
LEVEL_AT_RISK = 75.0


def objective_period(db: Session, obj: StrategicObjective) -> Period:
    return sub_period(obj.fy_start_year, company_fy_start_month(db), obj.period_type, obj.period_index)


def _json_list(raw: str | None) -> list:
    return json.loads(raw) if raw else []


def _require_manage(access: ManagementAccess) -> None:
    if not access.manage:
        raise ManagementForbidden("Changing strategic objectives needs the Manage strategy permission.")


def _can_edit(access: ManagementAccess, obj: StrategicObjective) -> bool:
    return access.manage or obj.owner_id == access.user.id


def _check_refs(db: Session, *, owner_id=None, team_id=None, project_ids=None, kpi_keys=None) -> None:
    if owner_id is not None and db.get(User, owner_id) is None:
        raise ValueError("Unknown owner")
    if team_id is not None and db.get(Team, team_id) is None:
        raise ValueError("Unknown team")
    if project_ids:
        found = set(db.scalars(select(Project.id).where(Project.id.in_(project_ids), Project.is_deleted.is_(False))).all())
        if len(found) != len(set(project_ids)):
            raise ValueError("Unknown project in related projects")
    for key in kpi_keys or []:
        if key not in KPI_DEFINITIONS:
            raise ValueError(f"Unknown KPI '{key}'")


def _restricted(access: ManagementAccess, obj: StrategicObjective) -> str | None:
    if obj.measurement == MEASURE_AUTOMATIC and obj.metric_key in kpis.REGISTRY:
        allowed, reason = kpis.can_view(access, kpis.REGISTRY[obj.metric_key])
        if not allowed:
            return reason
    if (obj.unit == CURRENCY or obj.category == "financial") and not access.finance:
        return "Financial objective values need Finance view access."
    return None


def progress_percent(direction: str, baseline: Decimal | None, target: Decimal, current) -> float | None:
    """Share of the way from baseline (or zero) to target; a decrease needs a baseline."""
    if current is None:
        return None
    current = Decimal(str(current))
    if direction == DIRECTION_DECREASE:
        if baseline is None:
            return None
        span = baseline - target
        if span <= 0:
            return 100.0 if current <= target else 0.0
        return round(max(float((baseline - current) / span * 100), 0.0), 1)
    start = baseline or Decimal("0")
    span = target - start
    if span <= 0:
        return 100.0 if current >= target else 0.0
    return round(max(float((current - start) / span * 100), 0.0), 1)


def _cumulative(obj: StrategicObjective) -> bool:
    spec = kpis.REGISTRY.get(obj.metric_key or "")
    if spec is not None:
        return spec.unit in {"currency", "count", "hours"} and not spec.point_in_time
    return False


def pace(obj: StrategicObjective, progress: float | None, today: date) -> dict:
    """Expected progress by today and the status the figures suggest (a person sets the real status)."""
    span = max((obj.target_date - obj.start_date).days, 1)
    elapsed = min(max((today - obj.start_date).days + 1, 0), span)
    cumulative = _cumulative(obj)
    expected = round(elapsed / span * 100, 1) if cumulative else 100.0
    if obj.status in {"completed", "cancelled"}:
        suggested = obj.status
    elif today < obj.start_date:
        suggested = "not_started"
    elif progress is None:
        suggested = None
    elif progress >= 100:
        suggested = "on_track"
    elif today > obj.target_date:
        suggested = "delayed"
    elif cumulative:
        suggested = ("on_track" if progress >= expected - ON_TRACK_SLACK
                     else "at_risk" if progress >= expected - AT_RISK_SLACK else "delayed")
    else:
        suggested = "at_risk" if progress >= LEVEL_AT_RISK else "delayed"
    return {
        "expected_percent": expected,
        "time_elapsed_percent": round(elapsed / span * 100, 1),
        "basis": "cumulative" if cumulative else "level",
        "suggested_status": suggested,
        "note": ("Expected progress grows with elapsed time (cumulative measure)." if cumulative else
                 "Level measure: compared with the target directly, not with elapsed time."),
    }


def _latest_manual(db: Session, obj: StrategicObjective) -> ObjectiveMeasurement | None:
    return db.scalars(select(ObjectiveMeasurement).where(
        ObjectiveMeasurement.objective_id == obj.id, ObjectiveMeasurement.source == MEASURE_MANUAL,
    ).order_by(ObjectiveMeasurement.recorded_at.desc(), ObjectiveMeasurement.period_end.desc())).first()


def current_value(db: Session, access: ManagementAccess, obj: StrategicObjective, today: date) -> dict:
    period = objective_period(db, obj)
    if obj.measurement == MEASURE_AUTOMATIC:
        if obj.metric_key not in kpis.REGISTRY:
            return {"value": None, "kind": "actual", "status": "unavailable", "note": "KPI no longer available."}
        params = json.loads(obj.metric_params_json or "{}")
        return kpis.calculate(db, access, obj.metric_key, params, period, today)
    latest = _latest_manual(db, obj)
    if latest is None:
        return {"value": None, "kind": "manual", "status": "unavailable", "note": "No value recorded yet.",
                "period": period.as_dict()}
    recorder = db.get(User, latest.recorded_by_id) if latest.recorded_by_id else None
    return {"value": number(latest.value), "kind": "manual", "status": "available",
            "period": {"start": latest.period_start.isoformat(), "end": latest.period_end.isoformat()},
            "note": latest.note, "evidence": latest.evidence, "recorded_by": user_name(recorder),
            "recorded_at": latest.recorded_at.isoformat(), "source": "Manual entry with evidence"}


def serialize(db: Session, access: ManagementAccess, obj: StrategicObjective, today: date | None = None,
              *, detail: bool = False) -> dict:
    today = today or date.today()
    restricted = _restricted(access, obj)
    period = objective_period(db, obj)
    users = {u.id: u for u in db.scalars(select(User).where(
        User.id.in_({i for i in (obj.owner_id, obj.target_approved_by_id, obj.created_by_id) if i}))).all()}
    team = db.get(Team, obj.supporting_team_id) if obj.supporting_team_id else None
    out = {
        "id": str(obj.id), "title": obj.title, "description": obj.description,
        "fy_start_year": obj.fy_start_year, "period_type": obj.period_type, "period_index": obj.period_index,
        "period": period.as_dict(), "category": obj.category, "unit": obj.unit, "direction": obj.direction,
        "measurement": obj.measurement, "metric_key": obj.metric_key,
        "metric_label": kpis.REGISTRY[obj.metric_key].label if obj.metric_key in kpis.REGISTRY else None,
        "metric_params": json.loads(obj.metric_params_json or "{}"),
        "owner_id": str(obj.owner_id) if obj.owner_id else None, "owner": user_name(users.get(obj.owner_id)),
        "supporting_team_id": str(obj.supporting_team_id) if obj.supporting_team_id else None,
        "supporting_team": team.name if team else None,
        "start_date": obj.start_date.isoformat(), "target_date": obj.target_date.isoformat(),
        "status": obj.status, "related_kpis": _json_list(obj.related_kpis_json),
        "related_project_ids": _json_list(obj.related_project_ids_json),
        "target_state": "approved" if obj.target_approved else "proposed",
        "target_approved_by": user_name(users.get(obj.target_approved_by_id)),
        "target_approved_at": obj.target_approved_at.isoformat() if obj.target_approved_at else None,
        "restricted": restricted is not None, "restricted_reason": restricted,
        "can_edit": _can_edit(access, obj), "can_change_target": access.approve,
        "can_record_measurement": obj.measurement == MEASURE_MANUAL and _can_edit(access, obj),
    }
    if restricted:
        out.update({"target": None, "baseline": None, "current": None, "progress_percent": None,
                    "pace": pace(obj, None, today)})
    else:
        current = current_value(db, access, obj, today)
        progress = progress_percent(obj.direction, obj.baseline_value, obj.target_value, current.get("value"))
        out.update({
            "target": {"value": number(obj.target_value), "kind": "target", "state": out["target_state"]},
            "baseline": {"value": number(obj.baseline_value), "kind": "baseline", "note": obj.baseline_note}
            if obj.baseline_value is not None else None,
            "current": current, "progress_percent": progress, "pace": pace(obj, progress, today),
        })
    if detail:
        out["events"] = list_events(db, "objective", obj.id)
        measurements = db.scalars(select(ObjectiveMeasurement).where(ObjectiveMeasurement.objective_id == obj.id)
                                  .order_by(ObjectiveMeasurement.recorded_at.desc())).all()
        out["measurements"] = [] if restricted else [{
            "id": str(m.id), "period_start": m.period_start.isoformat(), "period_end": m.period_end.isoformat(),
            "value": number(m.value), "source": m.source, "source_detail": m.source_detail, "note": m.note,
            "evidence": m.evidence, "supersedes_id": str(m.supersedes_id) if m.supersedes_id else None,
            "recorded_at": m.recorded_at.isoformat(),
        } for m in measurements]
        out["initiatives"] = [{"id": str(i.id), "name": i.name, "status": i.status, "progress_percent": i.progress_percent}
                              for i in db.scalars(select(StrategicInitiative).where(
                                  StrategicInitiative.objective_id == obj.id)).all()]
        out["actions"] = [{"id": str(a.id), "title": a.title, "status": a.status,
                           "due_date": a.due_date.isoformat() if a.due_date else None}
                          for a in db.scalars(select(ManagementAction).where(ManagementAction.objective_id == obj.id)).all()]
    return out


def list_objectives(db: Session, access: ManagementAccess, *, fy_start_year: int | None = None,
                    status: str | None = None, category: str | None = None, today: date | None = None) -> list[dict]:
    stmt = select(StrategicObjective)
    if fy_start_year is not None:
        stmt = stmt.where(StrategicObjective.fy_start_year == fy_start_year)
    if status:
        stmt = stmt.where(StrategicObjective.status == status)
    if category:
        stmt = stmt.where(StrategicObjective.category == category)
    rows = db.scalars(stmt.order_by(StrategicObjective.fy_start_year.desc(), StrategicObjective.title)).all()
    return [serialize(db, access, o, today) for o in rows]


def get_objective(db: Session, objective_id: UUID) -> StrategicObjective:
    obj = db.get(StrategicObjective, objective_id)
    if obj is None:
        raise LookupError("Objective not found")
    return obj


def create_objective(db: Session, access: ManagementAccess, body: ObjectiveCreate) -> StrategicObjective:
    _require_manage(access)
    _check_refs(db, owner_id=body.owner_id, team_id=body.supporting_team_id, project_ids=body.related_project_ids,
                kpi_keys=body.related_kpis)
    params = None
    if body.measurement == MEASURE_AUTOMATIC:
        params = kpis.validate_params(db, body.metric_key, body.metric_params)
        spec = kpis.REGISTRY[body.metric_key]
        if body.unit != spec.unit:
            raise ValueError(f"{spec.label} is measured in {spec.unit}")
        if body.direction != spec.direction:
            raise ValueError(f"{spec.label} improves by {spec.direction}")
    period = sub_period(body.fy_start_year, company_fy_start_month(db), body.period_type,
                        None if body.period_type == "annual" else body.period_index)
    if body.direction == DIRECTION_DECREASE and body.baseline_value is None:
        raise ValueError("A reduction objective needs a baseline to measure progress from")
    start, end = body.start_date or period.start, body.target_date or period.end
    if end < start:
        raise ValueError("Target date is before the start date")
    approved = access.approve
    obj = StrategicObjective(
        title=body.title, description=body.description, fy_start_year=body.fy_start_year,
        period_type=body.period_type, period_index=None if body.period_type == "annual" else body.period_index,
        category=body.category, unit=body.unit, direction=body.direction, measurement=body.measurement,
        metric_key=body.metric_key if body.measurement == MEASURE_AUTOMATIC else None,
        metric_params_json=json.dumps(params) if params else None,
        target_value=body.target_value, baseline_value=body.baseline_value, baseline_note=body.baseline_note,
        target_approved=approved, target_approved_by_id=access.user.id if approved else None,
        target_approved_at=datetime.utcnow() if approved else None,
        owner_id=body.owner_id, supporting_team_id=body.supporting_team_id, start_date=start, target_date=end,
        status="not_started", related_kpis_json=json.dumps(body.related_kpis) if body.related_kpis else None,
        related_project_ids_json=json.dumps([str(p) for p in body.related_project_ids]) if body.related_project_ids else None,
        created_by_id=access.user.id,
    )
    db.add(obj)
    db.flush()
    record_event(db, entity_type="objective", entity_id=obj.id, event_type="created",
                 summary=f"Objective created ({'target approved' if approved else 'target proposed'})",
                 actor=access.user, approved_by=access.user if approved else None,
                 new={"target": str(body.target_value), "baseline": str(body.baseline_value) if body.baseline_value is not None else None,
                      "measurement": body.measurement, "metric_key": body.metric_key})
    return obj


_SIMPLE = ("title", "description", "category", "start_date", "target_date")


def update_objective(db: Session, access: ManagementAccess, obj: StrategicObjective, body: ObjectiveUpdate) -> None:
    if not _can_edit(access, obj):
        raise ManagementForbidden("Only the owner or a strategy manager can change this objective.")
    data = body.model_dump(exclude_unset=True)
    owner_only = not access.manage
    if owner_only and set(data) - {"status", "status_reason", "description"}:
        raise ManagementForbidden("The owner can update status and description; other changes need Manage strategy.")
    _check_refs(db, owner_id=data.get("owner_id"), team_id=data.get("supporting_team_id"),
                project_ids=data.get("related_project_ids"), kpi_keys=data.get("related_kpis"))
    old, new = {}, {}
    for name in _SIMPLE:
        if name in data and data[name] is not None and getattr(obj, name) != data[name]:
            old[name], new[name] = getattr(obj, name), data[name]
            setattr(obj, name, data[name])
    for name, column in (("owner_id", "owner_id"), ("supporting_team_id", "supporting_team_id")):
        if name in data and getattr(obj, column) != data[name]:
            old[name], new[name] = getattr(obj, column), data[name]
            setattr(obj, column, data[name])
    if "related_kpis" in data and data["related_kpis"] is not None:
        obj.related_kpis_json = json.dumps(data["related_kpis"])
        new["related_kpis"] = data["related_kpis"]
    if "related_project_ids" in data and data["related_project_ids"] is not None:
        obj.related_project_ids_json = json.dumps([str(p) for p in data["related_project_ids"]])
        new["related_project_ids"] = [str(p) for p in data["related_project_ids"]]
    if obj.target_date < obj.start_date:
        raise ValueError("Target date is before the start date")
    if old or new:
        record_event(db, entity_type="objective", entity_id=obj.id, event_type="updated",
                     summary="Objective details updated", actor=access.user, old=old, new=new)
    status = data.get("status")
    if status and status != obj.status:
        reason = data.get("status_reason")
        if status in {"cancelled", "delayed", "at_risk"} and not reason:
            raise ValueError("Give a reason for this status")
        record_event(db, entity_type="objective", entity_id=obj.id, event_type="status_changed",
                     summary=f"Status {obj.status} -> {status}", actor=access.user, old=obj.status, new=status,
                     reason=reason)
        obj.status = status


def change_target(db: Session, access: ManagementAccess, obj: StrategicObjective, body: TargetChange) -> None:
    if not access.approve:
        raise ManagementForbidden("Changing an objective's target or baseline needs the Approve strategy permission.")
    if body.target_value is not None and body.target_value != obj.target_value:
        record_event(db, entity_type="objective", entity_id=obj.id, event_type="target_changed",
                     summary=f"Target {obj.target_value} -> {body.target_value}", actor=access.user,
                     approved_by=access.user, old=str(obj.target_value), new=str(body.target_value), reason=body.reason)
        obj.target_value = body.target_value
    if body.baseline_value is not None and body.baseline_value != obj.baseline_value:
        record_event(db, entity_type="objective", entity_id=obj.id, event_type="baseline_changed",
                     summary=f"Baseline {obj.baseline_value} -> {body.baseline_value}", actor=access.user,
                     approved_by=access.user, old=str(obj.baseline_value) if obj.baseline_value is not None else None,
                     new=str(body.baseline_value), reason=body.reason)
        obj.baseline_value = body.baseline_value
        if body.baseline_note is not None:
            obj.baseline_note = body.baseline_note
    obj.target_approved = True
    obj.target_approved_by_id = access.user.id
    obj.target_approved_at = datetime.utcnow()


def approve_target(db: Session, access: ManagementAccess, obj: StrategicObjective, note: str | None) -> None:
    if not access.approve:
        raise ManagementForbidden("Approving targets needs the Approve strategy permission.")
    if obj.target_approved:
        raise ValueError("The target is already approved")
    obj.target_approved = True
    obj.target_approved_by_id = access.user.id
    obj.target_approved_at = datetime.utcnow()
    record_event(db, entity_type="objective", entity_id=obj.id, event_type="target_approved",
                 summary=f"Target {obj.target_value} approved", actor=access.user, approved_by=access.user,
                 new=str(obj.target_value), reason=note)


def record_measurement(db: Session, access: ManagementAccess, obj: StrategicObjective,
                       body: MeasurementCreate) -> ObjectiveMeasurement:
    if obj.measurement != MEASURE_MANUAL:
        raise ValueError("This objective is calculated automatically; its actual cannot be entered by hand. "
                         "Add a comment instead.")
    if not _can_edit(access, obj):
        raise ManagementForbidden("Only the owner or a strategy manager can record values.")
    if obj.status == "cancelled":
        raise ValueError("The objective is cancelled")
    period = objective_period(db, obj)
    if body.period_start < period.start or body.period_end > period.end:
        raise ValueError(f"The measurement must fall within {period.label}")
    if body.supersedes_id is not None:
        previous = db.get(ObjectiveMeasurement, body.supersedes_id)
        if previous is None or previous.objective_id != obj.id:
            raise ValueError("The corrected measurement belongs to another objective")
    row = ObjectiveMeasurement(
        objective_id=obj.id, period_start=body.period_start, period_end=body.period_end, value=body.value,
        source=MEASURE_MANUAL, source_detail="Entered by hand", note=body.note, evidence=body.evidence,
        supersedes_id=body.supersedes_id, recorded_by_id=access.user.id,
    )
    db.add(row)
    db.flush()
    record_event(db, entity_type="objective", entity_id=obj.id,
                 event_type="measurement_recorded",
                 summary=("Correction recorded" if body.supersedes_id else "Value recorded") + f": {body.value}",
                 actor=access.user, new={"value": str(body.value), "period_start": body.period_start,
                                         "period_end": body.period_end, "evidence": body.evidence})
    return row


def add_note(db: Session, access: ManagementAccess, entity_type: str, entity_id: UUID, *, kind: str, text: str,
             editable: bool) -> None:
    if kind == "decision" and not access.manage:
        raise ManagementForbidden("Recording decisions needs the Manage strategy permission.")
    if not editable:
        raise ManagementForbidden("Only the owner or a strategy manager can comment here.")
    record_event(db, entity_type=entity_type, entity_id=entity_id, event_type=kind,
                 summary=text[:200], body=text, actor=access.user)


def can_comment(access: ManagementAccess, owner_id) -> bool:
    return access.manage or owner_id == access.user.id
