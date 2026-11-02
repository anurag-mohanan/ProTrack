"""Predictive intelligence API: stored predictions, accuracy, models, patterns and scenarios.

Every read goes through ``app.services.predictive.read`` with the caller's scope: projects they can
see (and their report team scope), capacity data only with Resource Planning access, Finance data
only with Finance access. Nothing here writes to project, timesheet, resource or Finance records.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.access_control import MODULE_FINANCIAL_PLANNING, SPECIAL_EDIT_PROJECTS
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import can_view_reports, get_role_name, is_admin, user_holds_special
from app.core.team_access import project_visibility_clause, resolve_team_scope
from app.models.models import Project, User
from app.models.prediction import INSUFFICIENT, PREDICTED, PredictionRun, PredictionScenario, PredictionSetting
from app.schemas.predictive import ActivateVersionIn, ScenarioAssumptionsIn, ScenarioSaveIn, SettingUpdateIn
from app.services.predictive import accuracy, read, registry, scenarios
from app.services.predictive.inputs import load_facts
from app.services.predictive.read import PredictionScope
from app.services.reporting.report_scope import ReportScopeForbidden, resolve_report_scope
from app.services.skills.access import can_view_capacity


def _require_reports(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_reports(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Predictive intelligence requires the Reports module.")
    return current_user


router = APIRouter(prefix="/predictions", tags=["predictions"], dependencies=[Depends(_require_reports)])


class _Access:
    def __init__(self, db: Session, user: User):
        try:
            report_teams = resolve_report_scope(db, user).team_ids
        except ReportScopeForbidden as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        clause = project_visibility_clause(db, user)
        if report_teams is not None:
            team_clause = Project.team_id.in_(report_teams) if report_teams else Project.id.is_(None)
            clause = team_clause if clause is None else and_(clause, team_clause)
        capacity = can_view_capacity(db, user)
        teams = resolve_team_scope(db, user) if capacity else set()
        self.user = user
        self.admin = is_admin(db, user)
        self.manage = self.admin or user_holds_special(db, user, SPECIAL_EDIT_PROJECTS)
        self.org_wide = report_teams is None
        self.scope = PredictionScope(
            visibility_clause=clause,
            can_view_capacity=capacity,
            capacity_team_ids=None if teams is None else frozenset(teams),
            finance_visible=user_has_module_action(user, get_role_name(db, user), MODULE_FINANCIAL_PLANNING,
                                                   MODULE_ACTION_VIEW),
        )

    def flags(self) -> dict:
        return {"run": self.manage, "manage_models": self.admin, "scenarios": self.manage,
                "capacity": self.scope.can_view_capacity, "finance": self.scope.finance_visible,
                "patterns": self.org_wide}


def _access(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> _Access:
    return _Access(db, current_user)


def _forbid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _visible_project(db: Session, access: _Access, project_id: UUID) -> Project:
    stmt = select(Project).where(Project.id == project_id, Project.is_deleted.is_(False))
    if access.scope.visibility_clause is not None:
        stmt = stmt.where(access.scope.visibility_clause)
    project = db.scalar(stmt)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _rows(db: Session, access: _Access, **filters) -> list[dict]:
    visible = read.visible_project_ids(db, access.scope)
    return [read.prediction_dict(p, visible) for p in read.latest(db, access.scope, **filters)]


def _coverage(rows: list[dict]) -> dict:
    reasons = Counter((r["reason"] or "No reason recorded") for r in rows if r["status"] == INSUFFICIENT)
    return {"predicted": sum(1 for r in rows if r["status"] == PREDICTED),
            "insufficient": sum(1 for r in rows if r["status"] == INSUFFICIENT),
            "top_reasons": [{"reason": k, "count": v} for k, v in reasons.most_common(5)]}


def _at_risk(rows: list[dict], limit: int = 10) -> list[dict]:
    hits = [r for r in rows if r["status"] == PREDICTED and r["variance_value"] and Decimal(r["variance_value"]) > 0]
    return sorted(hits, key=lambda r: Decimal(r["variance_value"]), reverse=True)[:limit]


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _run_read(run: PredictionRun | None, *, include_error: bool) -> dict | None:
    if run is None:
        return None
    return {"id": str(run.id), "status": run.status, "trigger": run.trigger, "as_of": run.as_of.isoformat(),
            "started_at": run.started_at, "finished_at": run.finished_at,
            "counts": json.loads(run.counts_json) if run.counts_json else None,
            "error": run.error if include_error else None}


@router.get("/overview")
def overview(db: Session = Depends(get_db), access: _Access = Depends(_access)):
    """Portfolio forecast: the most actionable items only, with coverage so gaps are visible."""
    today = date.today()
    delivery_rows = _rows(db, access, prediction_types=["project_delivery"])
    hours_rows = _rows(db, access, prediction_types=["project_final_hours"])
    milestone_rows = _rows(db, access, prediction_types=["milestone_delay"])
    trend = Counter(r["predicted_date"][:7] for r in delivery_rows if r["status"] == PREDICTED and r["predicted_date"])
    settings = {s.prediction_type: s for s in db.scalars(select(PredictionSetting))}
    last = db.scalar(select(PredictionRun).order_by(PredictionRun.started_at.desc()).limit(1))
    out = {
        "freshness": read.freshness(db, today),
        "latest_run": _run_read(last, include_error=access.manage),
        "can": access.flags(),
        "types": [{"key": k, "label": t.label, "module": t.module, "unit": t.unit, "description": t.description,
                   "enabled": settings[k].is_enabled if k in settings else True,
                   "active_version": settings[k].active_version if k in settings else None,
                   "visible": k in access.scope.types()} for k, t in registry.TYPES.items()],
        "likely_late": _at_risk(delivery_rows),
        "likely_overrun": _at_risk(hours_rows),
        "late_milestones": _at_risk(milestone_rows),
        "completion_trend": [{"month": m, "projects": n} for m, n in sorted(trend.items())],
        "coverage": {"project_delivery": _coverage(delivery_rows), "project_final_hours": _coverage(hours_rows),
                     "milestone_delay": _coverage(milestone_rows)},
        "bottlenecks": None,
        "finance": None,
    }
    if access.scope.can_view_capacity:
        demand = [r for r in _rows(db, access, prediction_types=["resource_demand"]) if r["subject_key"].endswith(":4w")]
        out["bottlenecks"] = {
            "people": [r for r in demand if r["subject_type"] == "person" and r["data_used"].get("shortage")],
            "teams": [r for r in demand if r["subject_type"] == "team" and r["data_used"].get("shortage")],
            "skills": [r for r in demand if r["subject_type"] == "skill"
                       and (r["data_used"].get("shortage") or r["data_used"].get("single_person_dependency"))],
            "coverage": _coverage(demand),
        }
    if access.scope.finance_visible:
        out["finance"] = {
            "billing": _rows(db, access, prediction_types=["finance_billing"]),
            "collections": _rows(db, access, prediction_types=["finance_collections"]),
        }
    return out


@router.get("")
def list_predictions(
    prediction_type: str = Query(..., max_length=40),
    status_filter: str | None = Query(None, alias="status", pattern="^(predicted|insufficient_data)$"),
    subject_type: str | None = Query(None, max_length=30),
    weeks: int | None = Query(None, ge=2, le=12),
    db: Session = Depends(get_db),
    access: _Access = Depends(_access),
):
    if prediction_type not in registry.TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown prediction type.")
    if prediction_type not in access.scope.types():
        raise _forbid("You do not have access to this prediction type.")
    rows = _rows(db, access, prediction_types=[prediction_type], status=status_filter, subject_type=subject_type)
    if weeks:
        rows = [r for r in rows if r["subject_key"].endswith(f":{weeks}w")]
    return {"prediction_type": prediction_type, "freshness": read.freshness(db, date.today()), "predictions": rows}


@router.get("/projects/{project_id}")
def project_detail(project_id: UUID, db: Session = Depends(get_db), access: _Access = Depends(_access)):
    """Actuals and approved figures (from the shared metrics) next to the forecasts, clearly separated."""
    project = _visible_project(db, access, project_id)
    today = date.today()
    facts = load_facts(db, [project], today).get(project.id)
    current = _rows(db, access, prediction_types=["project_delivery", "project_final_hours", "milestone_delay"],
                    project_id=project.id)
    history = {t: [read.prediction_dict(p) for p in read.history(db, access.scope, project_id=project.id, prediction_type=t)]
               for t in ("project_delivery", "project_final_hours")}
    return {
        "project": {"id": str(project.id), "code": project.code, "tool_number": project.tool_number,
                    "part_description": project.part_description,
                    "execution_status": project.execution_status.value if project.execution_status else None},
        "recorded": None if facts is None else {
            "committed_date": facts.committed_date, "committed_source": facts.committed_source,
            "current_target": facts.current_target, "start_date": facts.start_date, "start_source": facts.start_source,
            "quoted_hours": _text(facts.quoted_hours), "original_estimate": _text(facts.original_estimate),
            "current_estimate": _text(facts.current_estimate), "estimate_approved": facts.estimate_approved,
            "estimate_source": facts.estimate_source, "actual_hours": _text(facts.actual_hours),
            "actual_status": facts.actual_status, "unapproved_hours": _text(facts.unapproved_hours),
            "open_milestones": facts.open_milestones, "overdue_milestones": facts.overdue_milestones,
        },
        "delivery": next((r for r in current if r["prediction_type"] == "project_delivery"), None),
        "final_hours": next((r for r in current if r["prediction_type"] == "project_final_hours"), None),
        "milestones": [r for r in current if r["prediction_type"] == "milestone_delay"],
        "history": history,
        "freshness": read.freshness(db, today),
        "can_scenarios": access.manage,
    }


@router.get("/accuracy")
def accuracy_view(db: Session = Depends(get_db), access: _Access = Depends(_access)):
    return {"minimum_evaluated": accuracy.MIN_EVALUATED,
            "types": accuracy.accuracy_report(db, access.scope.types()),
            "can_manage": access.admin}


@router.get("/patterns")
def patterns_view(kind: str = Query("project", pattern="^(project|payment)$"), db: Session = Depends(get_db),
                  access: _Access = Depends(_access)):
    from app.services.predictive.patterns import portfolio_finance_patterns, portfolio_project_patterns

    if not access.org_wide:
        raise _forbid("Portfolio patterns cover every team and require organisation-wide Reports access.")
    if kind == "payment":
        if not access.scope.finance_visible:
            raise _forbid("Payment patterns require Finance access.")
        return portfolio_finance_patterns(db, date.today())
    return portfolio_project_patterns(db, date.today())


@router.post("/run")
def run_now(db: Session = Depends(get_db), access: _Access = Depends(_access)):
    from app.services.predictive.engine import PredictionRunInProgress, run_predictions

    if not access.manage:
        raise _forbid("Requires the 'edit_projects' permission.")
    try:
        run = run_predictions(db, trigger="manual", user_id=access.user.id)
    except PredictionRunInProgress as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="The prediction run failed. Earlier predictions were kept.") from exc
    return _run_read(run, include_error=True)


@router.put("/settings/{prediction_type}")
def update_setting(prediction_type: str, payload: SettingUpdateIn, db: Session = Depends(get_db),
                   access: _Access = Depends(_access)):
    if not access.admin:
        raise _forbid("Only administrators can enable or disable prediction types.")
    try:
        setting = accuracy.set_enabled(db, prediction_type, payload.enabled, user=access.user, reason=payload.reason)
    except accuracy.GovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"prediction_type": setting.prediction_type, "enabled": setting.is_enabled,
            "disabled_reason": setting.disabled_reason, "active_version": setting.active_version}


@router.post("/models/{prediction_type}/{version}/activate")
def activate(prediction_type: str, version: str, payload: ActivateVersionIn, db: Session = Depends(get_db),
             access: _Access = Depends(_access)):
    if not access.admin:
        raise _forbid("Only administrators can change the active model version.")
    try:
        target = accuracy.activate_version(db, prediction_type, version, user=access.user, note=payload.note)
    except accuracy.GovernanceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"prediction_type": prediction_type, "active_version": target.version, "note": target.activation_note}


# --- Scenarios ------------------------------------------------------------------


def _assumptions(payload: ScenarioAssumptionsIn) -> scenarios.Assumptions:
    return scenarios.Assumptions(
        scope_change_percent=payload.scope_change_percent, extra_delay_days=payload.extra_delay_days,
        target_shift_days=payload.target_shift_days,
        milestone_delays={str(k): v for k, v in payload.milestone_delays.items()},
        designer_id=payload.designer_id, added_hours_per_week=payload.added_hours_per_week,
        start_date=payload.start_date,
    )


def _scenario_read(db: Session, row: PredictionScenario) -> dict:
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([i for i in (row.created_by_id, row.updated_by_id) if i])))}

    def name(uid):
        user = users.get(uid)
        return (f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email) if user else None

    return {"id": str(row.id), "name": row.name, "project_id": str(row.project_id), "as_of": row.as_of.isoformat(),
            "created_by": name(row.created_by_id), "created_at": row.created_at,
            "updated_by": name(row.updated_by_id), "updated_at": row.updated_at,
            "assumptions": json.loads(row.assumptions_json), "result": json.loads(row.result_json),
            "label": scenarios.HYPOTHETICAL_LABEL}


def _scenario_error(exc: scenarios.ScenarioError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/projects/{project_id}/scenarios")
def list_scenarios(project_id: UUID, db: Session = Depends(get_db), access: _Access = Depends(_access)):
    project = _visible_project(db, access, project_id)
    rows = [_scenario_read(db, s) for s in scenarios.project_scenarios(db, project.id)]
    if not access.scope.can_view_capacity:
        for row in rows:
            for side in ("baseline", "scenario"):
                row["result"][side]["designer_load"] = None
            row["result"]["comparison"] = [c for c in row["result"]["comparison"] if not c["measure"].startswith("Designer load")]
    return {"label": scenarios.HYPOTHETICAL_LABEL, "scenarios": rows, "can_edit": access.manage}


@router.post("/projects/{project_id}/scenarios/preview")
def preview_scenario(project_id: UUID, payload: ScenarioAssumptionsIn, db: Session = Depends(get_db),
                     access: _Access = Depends(_access)):
    """Evaluate without saving. Writes nothing."""
    project = _visible_project(db, access, project_id)
    try:
        return scenarios.evaluate_scenario(db, project, _assumptions(payload), include_load=access.scope.can_view_capacity)
    except scenarios.ScenarioError as exc:
        raise _scenario_error(exc) from exc


@router.post("/projects/{project_id}/scenarios", status_code=status.HTTP_201_CREATED)
def create_scenario(project_id: UUID, payload: ScenarioSaveIn, db: Session = Depends(get_db),
                    access: _Access = Depends(_access)):
    if not access.manage:
        raise _forbid("Saving scenarios requires the 'edit_projects' permission.")
    project = _visible_project(db, access, project_id)
    try:
        row = scenarios.save_scenario(db, project, name=payload.name, assumptions=_assumptions(payload.assumptions),
                                      user=access.user, include_load=access.scope.can_view_capacity)
    except scenarios.ScenarioError as exc:
        raise _scenario_error(exc) from exc
    return _scenario_read(db, row)


def _own_scenario(db: Session, access: _Access, scenario_id: UUID) -> tuple[PredictionScenario, Project]:
    row = db.get(PredictionScenario, scenario_id)
    if row is None or row.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return row, _visible_project(db, access, row.project_id)


@router.put("/scenarios/{scenario_id}")
def update_scenario(scenario_id: UUID, payload: ScenarioSaveIn, db: Session = Depends(get_db),
                    access: _Access = Depends(_access)):
    if not access.manage:
        raise _forbid("Changing scenarios requires the 'edit_projects' permission.")
    row, project = _own_scenario(db, access, scenario_id)
    try:
        row = scenarios.save_scenario(db, project, name=payload.name, assumptions=_assumptions(payload.assumptions),
                                      user=access.user, include_load=access.scope.can_view_capacity, scenario=row)
    except scenarios.ScenarioError as exc:
        raise _scenario_error(exc) from exc
    return _scenario_read(db, row)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_scenario(scenario_id: UUID, db: Session = Depends(get_db), access: _Access = Depends(_access)):
    if not access.manage:
        raise _forbid("Deleting scenarios requires the 'edit_projects' permission.")
    row, _project = _own_scenario(db, access, scenario_id)
    scenarios.delete_scenario(db, row, user=access.user)
