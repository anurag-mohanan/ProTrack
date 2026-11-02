"""Permission-filtered reads of stored predictions, shared by the API and the assistant.

Only the latest active-version (non-shadow) rows are read unless history is asked for. Rows are
clipped to the caller's scope before they leave this module: project and milestone rows to visible
projects, person and team rows to the caller's capacity scope, skill rows to organisation-wide
capacity viewers, finance rows to Finance viewers. Project labels inside resource rows are replaced
by a count when the caller cannot see the project.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.models import Project
from app.models.prediction import Prediction, PredictionRun, PredictionSetting
from app.services.predictive import registry

STALE_AFTER_DAYS = 8
PROJECT_MODULE, RESOURCE_MODULE, FINANCE_MODULE = "projects", "resources", "finance"


@dataclass(frozen=True)
class PredictionScope:
    visibility_clause: object | None
    can_view_capacity: bool
    capacity_team_ids: frozenset[UUID] | None  # None = every team
    finance_visible: bool

    def modules(self) -> set[str]:
        out = {PROJECT_MODULE}
        if self.can_view_capacity:
            out.add(RESOURCE_MODULE)
        if self.finance_visible:
            out.add(FINANCE_MODULE)
        return out

    def types(self) -> list[str]:
        allowed = self.modules()
        return [key for key, spec in registry.TYPES.items() if spec.module in allowed]


def visible_project_ids(db: Session, scope: PredictionScope) -> set[UUID] | None:
    """None when every project is visible."""
    if scope.visibility_clause is None:
        return None
    return set(db.scalars(select(Project.id).where(Project.is_deleted.is_(False), scope.visibility_clause)))


def _loads(value: str | None, default):
    return json.loads(value) if value else default


def _clip_projects(data: dict, visible: set[UUID] | None) -> dict:
    rows = data.get("projects")
    if visible is None or not isinstance(rows, list):
        return data
    shown = [r for r in rows if r.get("project_id") and UUID(r["project_id"]) in visible]
    hidden = len(rows) - len(shown)
    out = {**data, "projects": shown}
    if hidden:
        out["projects_not_visible_to_you"] = hidden
    return out


def prediction_dict(p: Prediction, visible: set[UUID] | None = None) -> dict:
    spec = registry.TYPES.get(p.prediction_type)
    return {
        "id": str(p.id), "prediction_type": p.prediction_type, "type_label": spec.label if spec else p.prediction_type,
        "model_version": p.model_version, "is_shadow": p.is_shadow, "is_latest": p.is_latest,
        "subject_type": p.subject_type, "subject_key": p.subject_key, "subject_label": p.subject_label,
        "project_id": str(p.project_id) if p.project_id else None,
        "milestone_id": str(p.milestone_id) if p.milestone_id else None,
        "team_id": str(p.team_id) if p.team_id else None, "currency": p.currency,
        "as_of": p.as_of.isoformat(), "horizon_start": p.horizon_start.isoformat() if p.horizon_start else None,
        "horizon_end": p.horizon_end.isoformat() if p.horizon_end else None,
        "status": p.status, "reason": p.reason, "unit": p.unit,
        "predicted_value": str(p.predicted_value) if p.predicted_value is not None else None,
        "predicted_date": p.predicted_date.isoformat() if p.predicted_date else None,
        "lower_value": str(p.lower_value) if p.lower_value is not None else None,
        "upper_value": str(p.upper_value) if p.upper_value is not None else None,
        "lower_date": p.lower_date.isoformat() if p.lower_date else None,
        "upper_date": p.upper_date.isoformat() if p.upper_date else None,
        "range_basis": p.range_basis,
        "probability": str(p.probability) if p.probability is not None else None,
        "observed_frequency": str(p.observed_frequency) if p.observed_frequency is not None else None,
        "baseline_label": p.baseline_label,
        "baseline_value": str(p.baseline_value) if p.baseline_value is not None else None,
        "baseline_date": p.baseline_date.isoformat() if p.baseline_date else None,
        "variance_value": str(p.variance_value) if p.variance_value is not None else None,
        "sample_size": p.sample_size, "comparison_group": p.comparison_group,
        "factors": _loads(p.factors_json, []),
        "data_used": _clip_projects(_loads(p.data_used_json, {}), visible),
        "warnings": _loads(p.warnings_json, []),
        "outcome_status": p.outcome_status,
        "actual_value": str(p.actual_value) if p.actual_value is not None else None,
        "actual_date": p.actual_date.isoformat() if p.actual_date else None,
        "abs_error": str(p.abs_error) if p.abs_error is not None else None,
        "pct_error": str(p.pct_error) if p.pct_error is not None else None,
        "outcome_note": p.outcome_note,
    }


def scoped_statement(db: Session, scope: PredictionScope, *, prediction_types: list[str] | None = None):
    allowed = [t for t in (prediction_types or scope.types()) if t in scope.types()]
    stmt = select(Prediction).where(Prediction.prediction_type.in_(allowed or ["-"]))
    project_types = [t for t in allowed if registry.TYPES[t].module == PROJECT_MODULE]
    resource_types = [t for t in allowed if registry.TYPES[t].module == RESOURCE_MODULE]
    finance_types = [t for t in allowed if registry.TYPES[t].module == FINANCE_MODULE]
    clauses = []
    if project_types:
        project_clause = Prediction.project_id.in_(
            select(Project.id).where(Project.is_deleted.is_(False),
                                     *([scope.visibility_clause] if scope.visibility_clause is not None else []))
        )
        clauses.append(Prediction.prediction_type.in_(project_types) & project_clause)
    if resource_types:
        if scope.capacity_team_ids is None:
            clauses.append(Prediction.prediction_type.in_(resource_types))
        else:
            clauses.append(Prediction.prediction_type.in_(resource_types)
                           & Prediction.subject_type.in_(["person", "team"])
                           & Prediction.team_id.in_(scope.capacity_team_ids or [UUID(int=0)]))
    if finance_types:
        clauses.append(Prediction.prediction_type.in_(finance_types))
    return stmt.where(or_(*clauses)) if clauses else stmt.where(Prediction.id.is_(None))


def latest(db: Session, scope: PredictionScope, *, prediction_types: list[str] | None = None,
           project_id: UUID | None = None, status: str | None = None, subject_type: str | None = None,
           limit: int | None = None) -> list[Prediction]:
    stmt = scoped_statement(db, scope, prediction_types=prediction_types).where(
        Prediction.is_latest.is_(True), Prediction.is_shadow.is_(False))
    if project_id:
        stmt = stmt.where(Prediction.project_id == project_id)
    if status:
        stmt = stmt.where(Prediction.status == status)
    if subject_type:
        stmt = stmt.where(Prediction.subject_type == subject_type)
    stmt = stmt.order_by(Prediction.prediction_type, Prediction.subject_label)
    if limit:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def history(db: Session, scope: PredictionScope, *, project_id: UUID, prediction_type: str,
            limit: int = 50) -> list[Prediction]:
    stmt = scoped_statement(db, scope, prediction_types=[prediction_type]).where(
        Prediction.project_id == project_id, Prediction.is_shadow.is_(False), Prediction.milestone_id.is_(None))
    return list(db.scalars(stmt.order_by(Prediction.as_of.desc(), Prediction.created_at.desc()).limit(limit)))


def freshness(db: Session, today: date) -> dict:
    """When predictions were last produced, and whether that is recent enough to rely on."""
    last = db.scalar(select(PredictionRun).where(PredictionRun.status == "succeeded")
                     .order_by(PredictionRun.finished_at.desc()).limit(1))
    disabled = sorted(db.scalars(select(PredictionSetting.prediction_type)
                                 .where(PredictionSetting.is_enabled.is_(False))))
    if last is None:
        return {"last_run_as_of": None, "stale": True, "disabled_types": disabled,
                "message": "Predictions have never been run."}
    stale = last.as_of < today - timedelta(days=STALE_AFTER_DAYS)
    return {
        "last_run_as_of": last.as_of.isoformat(), "stale": stale, "disabled_types": disabled,
        "message": (f"The latest predictions are from {last.as_of}; they may be out of date." if stale
                    else f"Predictions as of {last.as_of}."),
    }
