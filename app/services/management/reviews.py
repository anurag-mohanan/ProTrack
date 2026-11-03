"""Management reviews: generated figures, human summary, decisions, actions and history.

Generation stores a dated snapshot of the ten review sections, calculated organisation-wide from
the same builders as the cockpit. Forecasts sit in their own section and are never mixed with
actuals. A snapshot is replaced only while the review is a draft; finalising needs a human
executive summary and the Approve strategy permission, after which the review cannot change
(decisions and comments are still appended). Sections a reader may not see are removed on read.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.control_tower import OPEN_FINDING_STATUSES, ProjectRiskFinding
from app.models.management import (
    ACTION_CLOSED,
    REVIEW_DRAFT,
    REVIEW_FINAL,
    ManagementAction,
    ManagementReview,
    StrategicObjective,
)
from app.models.models import Project, User
from app.schemas.management import ActionCreate, DecisionCreate, ReviewCreate, ReviewUpdate
from app.services.control_tower_service import TRIAGE_DISMISSED
from app.services.finance.fy_calendar_service import company_fy_start_month
from app.services.management import actions as action_service
from app.services.management import objectives as objective_service
from app.services.management.access import ManagementAccess, ManagementForbidden
from app.services.management.business import build_business
from app.services.management.customers import build_customer_table
from app.services.management.efficiency import build_efficiency
from app.services.management.events import list_events, record_event, user_name
from app.services.management.filters import CockpitFilters, Period, build_filters, sub_period
from app.services.management.kpis import calculation_access
from app.services.management.metrics import FORECAST
from app.services.management.operations import build_operations, qtd_reports
from app.services.management.workforce import build_workforce
from app.services.predictive import read as predictions

SECTIONS = ("executive_summary", "financial", "delivery", "efficiency", "customer", "workforce", "objectives",
            "risks", "decisions_required", "action_items")
FINANCE_SECTIONS = {"financial"}
WORKFORCE_SECTIONS = {"workforce"}
COMPARE_KEYS = {
    "financial": ("invoiced_revenue", "collections", "awarded_value", "outstanding_receivables"),
    "delivery": ("projects_completed", "active_projects", "projects_overdue", "projects_at_risk",
                 "on_time_delivery_rate", "delivery_variance_days", "hour_variance_percent"),
    "workforce": ("active_employees", "available_capacity", "capacity_utilisation"),
}
PERIOD_TYPE = {"monthly": "monthly", "quarterly": "quarterly", "annual": "annual"}


def _require_reviews(access: ManagementAccess) -> None:
    if not access.reviews:
        raise ManagementForbidden("Management reviews need organisation-wide report scope or Manage strategy.")


def _require_manage(access: ManagementAccess) -> None:
    if not access.manage:
        raise ManagementForbidden("Preparing management reviews needs the Manage strategy permission.")


def review_period(db: Session, review_type: str, fy_start_year: int, period_index: int | None) -> Period:
    if review_type != "annual" and period_index is None:
        raise ValueError("Monthly and quarterly reviews need a period number")
    return sub_period(fy_start_year, company_fy_start_month(db), PERIOD_TYPE[review_type],
                      None if review_type == "annual" else period_index)


def _kpis(section: dict) -> dict:
    return {k["key"]: k for k in section.get("kpis", [])}


def _risks(db: Session, project_ids: list[UUID]) -> dict:
    if not project_ids:
        return {"open_high_or_critical": 0, "top": []}
    rows = db.execute(
        select(ProjectRiskFinding, Project.code)
        .join(Project, Project.id == ProjectRiskFinding.project_id)
        .where(ProjectRiskFinding.project_id.in_(project_ids), ProjectRiskFinding.status.in_(OPEN_FINDING_STATUSES),
               ProjectRiskFinding.severity.in_(("critical", "high")), ProjectRiskFinding.category != "data_quality",
               or_(ProjectRiskFinding.triage_status.is_(None), ProjectRiskFinding.triage_status != TRIAGE_DISMISSED))
        .order_by(ProjectRiskFinding.severity, ProjectRiskFinding.first_detected_at)
    ).all()
    return {
        "open_high_or_critical": len(rows),
        "top": [{"project": code, "title": f.title, "severity": f.severity, "category": f.category,
                 "source": f.source or "operational"} for f, code in rows[:10]],
    }


def _highlights(financial: dict, delivery: dict, objectives: list[dict]) -> list[str]:
    out = []
    fin = _kpis(financial)
    if fin.get("invoiced_revenue", {}).get("value") is not None:
        out.append(f"Invoiced revenue INR {fin['invoiced_revenue']['value']:,.0f}; collections INR "
                   f"{(fin.get('collections', {}).get('value') or 0):,.0f}.")
    ops = _kpis(delivery)
    if ops:
        out.append(f"{ops['projects_completed']['value']} project(s) completed in the period; "
                   f"{ops['active_projects']['value']} active, {ops['projects_overdue']['value']} past their target date.")
    behind = [o["title"] for o in objectives if (o.get("pace") or {}).get("suggested_status") in {"at_risk", "delayed"}]
    if behind:
        out.append(f"{len(behind)} objective(s) behind plan: {', '.join(behind[:5])}.")
    return out


def build_snapshot(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date) -> dict:
    calc = calculation_access(access)
    reports = qtd_reports(db, calc, filters, today)
    financial = build_business(db, calc, filters, today)
    delivery = build_operations(db, calc, filters, today, reports=reports)
    efficiency = build_efficiency(db, calc, filters, compare_by="classification", today=today, reports=reports)
    customers = build_customer_table(db, calc, filters, today, reports=reports)
    workforce = build_workforce(db, calc, filters, today)
    period = filters.period
    objective_rows = db.scalars(select(StrategicObjective).where(
        StrategicObjective.start_date <= period.end, StrategicObjective.target_date >= period.start,
        StrategicObjective.status != "cancelled")).all()
    objectives = []
    for obj in objective_rows:
        item = objective_service.serialize(db, calc, obj, today)
        objectives.append({k: item[k] for k in ("id", "title", "category", "unit", "status", "target", "baseline",
                                                "current", "progress_percent", "pace", "owner", "target_state",
                                                "measurement", "metric_key")}
                          | {"finance": obj.unit == "currency" or obj.category == "financial"
                             or (obj.metric_key or "") in {"invoiced_revenue", "collections", "awarded_value",
                                                          "outstanding_receivables"},
                             "workforce": (obj.metric_key or "") in {"capacity_utilisation", "training_completion_rate",
                                                                    "skill_verified_holders"}})
    active_ids = [r.project_id for r in reports[1].projects.items]
    risks = _risks(db, active_ids)
    open_actions = db.scalars(select(ManagementAction).where(ManagementAction.status.notin_(ACTION_CLOSED))).all()
    overdue = [a for a in open_actions if a.due_date and a.due_date < today]
    blocked = [a for a in open_actions if a.status == "blocked"]
    decisions_required = (
        [{"type": "objective", "id": o["id"], "text": f"Objective '{o['title']}' is {o['pace']['suggested_status'].replace('_', ' ')} "
          "against its target."} for o in objectives if o["pace"].get("suggested_status") in {"at_risk", "delayed"}]
        + [{"type": "action", "id": str(a.id), "text": f"Action '{a.title}' is blocked."} for a in blocked]
        + [{"type": "action", "id": str(a.id), "text": f"Action '{a.title}' is overdue (due {a.due_date:%d %b %Y})."}
           for a in overdue if a.status != "blocked"]
        + [{"type": "risk", "id": None, "text": f"{r['project']}: {r['title']} ({r['severity']})."} for r in risks["top"][:5]]
    )
    scope = predictions.PredictionScope(visibility_clause=None, can_view_capacity=True, capacity_team_ids=None,
                                        finance_visible=True)
    forecast_counts: dict[str, int] = {}
    for p in predictions.latest(db, scope, status="predicted"):
        forecast_counts[p.prediction_type] = forecast_counts.get(p.prediction_type, 0) + 1
    return {
        "generated_for": period.as_dict(),
        "executive_summary": {"generated_highlights": _highlights(financial, delivery, objectives),
                              "note": "Highlights are generated from the figures below; the executive summary is "
                                      "written by a person."},
        "financial": financial,
        "delivery": delivery,
        "efficiency": {k: efficiency[k] for k in ("kpis", "comparison", "effort", "rework", "active_consumption",
                                                  "fairness_note", "notes", "warnings")},
        "customer": {"rows": customers["rows"][:10], "total": len(customers["rows"]), "notes": customers["notes"],
                     "finance_columns": customers["finance_visible"]},
        "workforce": workforce,
        "objectives": objectives,
        "risks": risks,
        "decisions_required": decisions_required,
        "action_items": {"open": len(open_actions), "overdue": len(overdue), "blocked": len(blocked),
                         "items": [{"id": str(a.id), "title": a.title, "status": a.status, "owner_id": str(a.owner_id),
                                    "due_date": a.due_date.isoformat() if a.due_date else None} for a in open_actions[:25]]},
        "forecasts": {
            "kind": FORECAST,
            "projects_forecast_risk": _kpis(delivery).get("projects_forecast_risk", {}).get("value"),
            "workload_bottlenecks": workforce.get("bottlenecks"),
            "stored_predictions": forecast_counts,
            "freshness": predictions.freshness(db, today),
            "note": "Phase 7 forecasts at generation time. Forecasts are not actuals and are not used in any figure above.",
        },
    }


def _redact(snapshot: dict, access: ManagementAccess) -> dict:
    out = dict(snapshot)
    if not access.finance:
        for name in FINANCE_SECTIONS:
            out[name] = {"visible": False, "reason": "Needs Finance view access."}
        customer = dict(out.get("customer") or {})
        customer["rows"] = [{k: v for k, v in r.items() if k not in {"invoiced", "awarded", "collected", "outstanding",
                                                                   "previous_period_invoiced", "revenue_trend_percent"}}
                            for r in customer.get("rows", [])]
        customer["finance_columns"] = False
        out["customer"] = customer
        out["executive_summary"] = {**out.get("executive_summary", {}),
                                    "generated_highlights": [h for h in out.get("executive_summary", {}).get(
                                        "generated_highlights", []) if "INR" not in h]}
    if not access.workforce:
        for name in WORKFORCE_SECTIONS:
            out[name] = {"visible": False, "reason": "Needs Resource Planning or HR view access."}
        if "forecasts" in out:
            out["forecasts"] = {**out["forecasts"], "workload_bottlenecks": None}
    hidden = []
    for item in out.get("objectives", []):
        if (item.get("finance") and not access.finance) or (item.get("workforce") and not access.workforce):
            hidden.append({**{k: item[k] for k in ("id", "title", "category", "status", "owner")},
                           "restricted": True, "target": None, "current": None, "progress_percent": None})
        else:
            hidden.append(item)
    out["objectives"] = hidden
    return out


def get_review(db: Session, access: ManagementAccess, review_id: UUID) -> ManagementReview:
    _require_reviews(access)
    row = db.get(ManagementReview, review_id)
    if row is None:
        raise LookupError("Review not found")
    return row


def serialize(db: Session, access: ManagementAccess, row: ManagementReview, *, detail: bool = False) -> dict:
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(
        {i for i in (row.generated_by_id, row.finalised_by_id, row.created_by_id) if i}))).all()}
    out = {
        "id": str(row.id), "review_type": row.review_type, "title": row.title, "status": row.status,
        "fy_start_year": row.fy_start_year, "period_index": row.period_index,
        "period": {"start": row.period_start.isoformat(), "end": row.period_end.isoformat()},
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "generated_by": user_name(users.get(row.generated_by_id)),
        "finalised_at": row.finalised_at.isoformat() if row.finalised_at else None,
        "finalised_by": user_name(users.get(row.finalised_by_id)),
        "executive_summary": row.executive_summary,
        "ai_summary_draft": row.ai_summary_draft,
        "ai_summary_status": "draft - not reviewed" if row.ai_summary_draft else None,
        "previous_review_id": str(row.previous_review_id) if row.previous_review_id else None,
        "filters": json.loads(row.filters_json or "{}"),
        "can_edit": access.manage and row.status == REVIEW_DRAFT,
        "can_finalise": access.approve and row.status == REVIEW_DRAFT,
        "sections": list(SECTIONS),
    }
    if detail:
        out["snapshot"] = _redact(json.loads(row.snapshot_json or "{}"), access)
        out["events"] = list_events(db, "review", row.id)
        out["decisions"] = [e for e in out["events"] if e["event_type"] == "decision"]
        out["actions"] = [action_service.serialize(db, a, access=access) for a in db.scalars(
            select(ManagementAction).where(ManagementAction.review_id == row.id)
            .order_by(ManagementAction.created_at)).all()]
    return out


def list_reviews(db: Session, access: ManagementAccess, *, review_type: str | None = None,
                 fy_start_year: int | None = None) -> list[dict]:
    _require_reviews(access)
    stmt = select(ManagementReview)
    if review_type:
        stmt = stmt.where(ManagementReview.review_type == review_type)
    if fy_start_year is not None:
        stmt = stmt.where(ManagementReview.fy_start_year == fy_start_year)
    return [serialize(db, access, r) for r in db.scalars(stmt.order_by(ManagementReview.period_start.desc(),
                                                                      ManagementReview.created_at.desc())).all()]


def _previous(db: Session, row: ManagementReview) -> ManagementReview | None:
    return db.scalars(select(ManagementReview).where(
        ManagementReview.review_type == row.review_type, ManagementReview.period_end < row.period_start,
        ManagementReview.id != row.id,
    ).order_by(ManagementReview.status.desc(), ManagementReview.period_end.desc())).first()


def create_review(db: Session, access: ManagementAccess, body: ReviewCreate, today: date | None = None) -> ManagementReview:
    _require_manage(access)
    today = today or date.today()
    period = review_period(db, body.review_type, body.fy_start_year, body.period_index)
    if period.start > today:
        raise ValueError("The review period has not started")
    filters = build_filters(db, access, period=period, customer_id=body.customer_id, team_id=body.team_id)
    row = ManagementReview(
        review_type=body.review_type, title=f"{body.review_type.capitalize()} management review - {period.label}",
        fy_start_year=body.fy_start_year, period_index=None if body.review_type == "annual" else body.period_index,
        period_start=period.start, period_end=period.end, status=REVIEW_DRAFT,
        filters_json=json.dumps(filters.as_dict()), created_by_id=access.user.id,
    )
    db.add(row)
    db.flush()
    previous = _previous(db, row)
    row.previous_review_id = previous.id if previous else None
    _generate(db, access, row, filters, today)
    record_event(db, entity_type="review", entity_id=row.id, event_type="created", summary=f"Review created: {row.title}",
                 actor=access.user)
    return row


def _filters_for(db: Session, access: ManagementAccess, row: ManagementReview) -> CockpitFilters:
    saved = json.loads(row.filters_json or "{}")
    period = review_period(db, row.review_type, row.fy_start_year, row.period_index)
    return build_filters(db, access, period=period,
                         customer_id=UUID(saved["customer_id"]) if saved.get("customer_id") else None,
                         team_id=UUID(saved["team_id"]) if saved.get("team_id") else None)


def _generate(db: Session, access: ManagementAccess, row: ManagementReview, filters: CockpitFilters, today: date) -> None:
    row.snapshot_json = json.dumps(build_snapshot(db, access, filters, today), default=str)
    row.generated_at = datetime.utcnow()
    row.generated_by_id = access.user.id
    record_event(db, entity_type="review", entity_id=row.id, event_type="generated",
                 summary=f"Figures generated as of {today:%d %b %Y}", actor=access.user)


def regenerate(db: Session, access: ManagementAccess, row: ManagementReview, today: date | None = None) -> None:
    _require_manage(access)
    if row.status != REVIEW_DRAFT:
        raise ValueError("A finalised review cannot be regenerated")
    _generate(db, access, row, _filters_for(db, access, row), today or date.today())


def update_review(db: Session, access: ManagementAccess, row: ManagementReview, body: ReviewUpdate) -> None:
    _require_manage(access)
    if row.status != REVIEW_DRAFT:
        raise ValueError("A finalised review cannot be changed")
    data = body.model_dump(exclude_unset=True)
    if "title" in data and data["title"]:
        row.title = data["title"]
    if "executive_summary" in data and data["executive_summary"] != row.executive_summary:
        record_event(db, entity_type="review", entity_id=row.id, event_type="updated",
                     summary="Executive summary edited", actor=access.user)
        row.executive_summary = data["executive_summary"]


def finalise(db: Session, access: ManagementAccess, row: ManagementReview) -> None:
    if not access.approve:
        raise ManagementForbidden("Finalising a management review needs the Approve strategy permission.")
    if row.status != REVIEW_DRAFT:
        raise ValueError("The review is already final")
    if not (row.executive_summary or "").strip():
        raise ValueError("Write or confirm the executive summary before finalising; generated text is not official")
    if row.snapshot_json is None:
        raise ValueError("Generate the review figures first")
    row.status = REVIEW_FINAL
    row.finalised_at = datetime.utcnow()
    row.finalised_by_id = access.user.id
    record_event(db, entity_type="review", entity_id=row.id, event_type="finalised", summary="Review finalised",
                 actor=access.user, approved_by=access.user)


def record_decision(db: Session, access: ManagementAccess, row: ManagementReview, body: DecisionCreate) -> None:
    _require_manage(access)
    event = record_event(db, entity_type="review", entity_id=row.id, event_type="decision", summary=body.text[:200],
                         body=body.text, actor=access.user)
    if body.action_title:
        action_service.create_action(
            db, access, ActionCreate(title=body.action_title, owner_id=body.action_owner_id, due_date=body.action_due_date,
                                     priority=body.action_priority, description=f"From review decision: {body.text}"),
            decision_event_id=event.id, review_id=row.id)


def _flat(snapshot: dict) -> dict[str, dict]:
    out = {}
    for section, keys in COMPARE_KEYS.items():
        values = _kpis(snapshot.get(section) or {})
        for key in keys:
            if key in values:
                out[key] = {"section": section, "label": values[key]["label"], "unit": values[key]["unit"],
                            "value": values[key]["value"]}
    return out


def compare(db: Session, access: ManagementAccess, row: ManagementReview, other_id: UUID | None = None) -> dict:
    other = get_review(db, access, other_id) if other_id else (
        db.get(ManagementReview, row.previous_review_id) if row.previous_review_id else _previous(db, row))
    if other is None:
        return {"review": serialize(db, access, row), "other": None, "rows": [],
                "note": "No earlier review of this type to compare with."}
    current = _flat(_redact(json.loads(row.snapshot_json or "{}"), access))
    previous = _flat(_redact(json.loads(other.snapshot_json or "{}"), access))
    rows = []
    for key, item in current.items():
        before = previous.get(key, {}).get("value")
        now = item["value"]
        rows.append({**item, "key": key, "current": now, "previous": before,
                     "change": round(now - before, 2) if now is not None and before is not None else None})
    return {"review": serialize(db, access, row), "other": serialize(db, access, other), "rows": rows,
            "note": "Both columns are actuals as generated for each review; forecasts are not compared."}
