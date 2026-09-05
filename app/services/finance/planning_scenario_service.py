"""CRUD for persisted finance planning scenarios."""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import FinancePlanningScenarioStatus, FinancePlanningScenarioType
from app.models.finance import FinancePlanningScenario
from app.models.models import User
from app.services.finance.dashboard_service import get_finance_dashboard
from app.services.finance.fx_service import get_base_currency, resolve_fx_rate
from app.services.finance.scenario_calculator import (
    baseline_from_dashboard,
    compute_scenario,
    empty_payload,
)


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_payload(raw: str | None) -> dict:
    if not raw:
        return empty_payload()
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return empty_payload()
        return data
    except json.JSONDecodeError:
        return empty_payload()


def _serialize_payload(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _normalize_payload(payload: dict | None) -> dict:
    base = empty_payload()
    if not payload:
        return base
    merged = {**base, **payload}
    merged["overhead"] = {**base["overhead"], **(payload.get("overhead") or {})}
    merged["expansion"] = {**base["expansion"], **(payload.get("expansion") or {})}
    try:
        version = int(payload.get("schema_version") or base.get("schema_version") or 2)
    except (TypeError, ValueError):
        version = 2
    merged["schema_version"] = max(2, version)
    merged["opex_yearly"] = bool(merged.get("opex_yearly"))
    merged["capex_yearly"] = bool(merged.get("capex_yearly"))
    merged["new_teams"] = list(merged.get("new_teams") or [])
    merged["management_hires"] = list(merged.get("management_hires") or [])
    merged["facility_lines"] = list(merged.get("facility_lines") or [])
    what_if = payload.get("what_if")
    if isinstance(what_if, dict):
        merged["what_if"] = what_if
    elif "what_if" in merged and not isinstance(merged.get("what_if"), dict):
        merged.pop("what_if", None)
    return merged


def scenario_to_dict(row: FinancePlanningScenario) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "scenario_type": row.scenario_type.value,
        "status": row.status.value,
        "baseline_as_of": row.baseline_as_of,
        "payload": _parse_payload(row.payload_json),
        "created_by_user_id": row.created_by_user_id,
        "updated_by_user_id": row.updated_by_user_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_scenarios(
    db: Session,
    *,
    status: FinancePlanningScenarioStatus | None = None,
    scenario_type: FinancePlanningScenarioType | None = None,
) -> list[FinancePlanningScenario]:
    stmt = select(FinancePlanningScenario).order_by(
        FinancePlanningScenario.updated_at.desc(),
        FinancePlanningScenario.name.asc(),
    )
    if status is not None:
        stmt = stmt.where(FinancePlanningScenario.status == status)
    if scenario_type is not None:
        stmt = stmt.where(FinancePlanningScenario.scenario_type == scenario_type)
    return list(db.scalars(stmt).all())


def get_scenario(db: Session, scenario_id: UUID) -> FinancePlanningScenario:
    row = db.get(FinancePlanningScenario, scenario_id)
    if row is None:
        raise ProTrackValidationError("Planning scenario not found")
    return row


def create_scenario(
    db: Session,
    *,
    user: User,
    name: str,
    description: str | None,
    scenario_type: FinancePlanningScenarioType,
    status: FinancePlanningScenarioStatus,
    baseline_as_of: date | None,
    payload: dict | None,
) -> FinancePlanningScenario:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ProTrackValidationError("Scenario name is required")
    if len(clean_name) > 120:
        raise ProTrackValidationError("Scenario name must be 120 characters or fewer")

    row = FinancePlanningScenario(
        name=clean_name,
        description=(description or "").strip() or None,
        scenario_type=scenario_type,
        status=status,
        baseline_as_of=baseline_as_of or date.today(),
        payload_json=_serialize_payload(_normalize_payload(payload)),
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def update_scenario(
    db: Session,
    scenario_id: UUID,
    *,
    user: User,
    name: str | None = None,
    description: str | None = None,
    scenario_type: FinancePlanningScenarioType | None = None,
    status: FinancePlanningScenarioStatus | None = None,
    baseline_as_of: date | None = None,
    payload: dict | None = None,
) -> FinancePlanningScenario:
    row = get_scenario(db, scenario_id)
    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise ProTrackValidationError("Scenario name is required")
        if len(clean_name) > 120:
            raise ProTrackValidationError("Scenario name must be 120 characters or fewer")
        row.name = clean_name
    if description is not None:
        row.description = description.strip() or None
    if scenario_type is not None:
        row.scenario_type = scenario_type
    if status is not None:
        row.status = status
    if baseline_as_of is not None:
        row.baseline_as_of = baseline_as_of
    if payload is not None:
        row.payload_json = _serialize_payload(_normalize_payload(payload))
    row.updated_by_user_id = user.id
    db.flush()
    return row


def delete_scenario(db: Session, scenario_id: UUID) -> None:
    row = get_scenario(db, scenario_id)
    db.delete(row)


def clone_scenario(db: Session, scenario_id: UUID, *, user: User) -> FinancePlanningScenario:
    source = get_scenario(db, scenario_id)
    copy_name = f"{source.name} (copy)"
    if len(copy_name) > 120:
        copy_name = copy_name[:117] + "..."
    return create_scenario(
        db,
        user=user,
        name=copy_name,
        description=source.description,
        scenario_type=source.scenario_type,
        status=FinancePlanningScenarioStatus.draft,
        baseline_as_of=source.baseline_as_of,
        payload=_parse_payload(source.payload_json),
    )


def _enrich_revenue_fx(db: Session, payload: dict) -> dict:
    """Fill missing revenue_fx_rate_to_base from live FX table when currency ≠ base."""
    base = get_base_currency(db).upper()
    teams = list(payload.get("new_teams") or [])
    enriched: list[dict] = []
    for row in teams:
        team = dict(row)
        code = str(team.get("revenue_currency_code") or base).upper()
        team["revenue_currency_code"] = code
        existing = team.get("revenue_fx_rate_to_base")
        try:
            existing_f = float(existing) if existing is not None else 0.0
        except (TypeError, ValueError):
            existing_f = 0.0
        if code == base:
            team["revenue_fx_rate_to_base"] = 1.0
        elif existing_f <= 0:
            try:
                team["revenue_fx_rate_to_base"] = float(
                    resolve_fx_rate(db, from_currency=code, fetch_live=False)
                )
            except Exception:
                team["revenue_fx_rate_to_base"] = 1.0
        else:
            team["revenue_fx_rate_to_base"] = existing_f
        enriched.append(team)
    payload = {**payload, "new_teams": enriched}
    return payload


def compute_from_dashboard(
    db: Session,
    *,
    payload: dict,
    team_id: UUID | None = None,
) -> dict:
    dashboard = get_finance_dashboard(db, team_id=team_id)
    baseline = baseline_from_dashboard(dashboard)
    normalized = _enrich_revenue_fx(db, _normalize_payload(payload))
    result = compute_scenario(baseline, normalized)
    return {"baseline": baseline, "result": result, "payload": normalized}


def _summary_from_result(scenario_id: UUID, name: str, result: dict) -> dict:
    total_net = sum(_num(row.get("simulated_net")) for row in result.get("teams") or [])
    return {
        "scenario_id": scenario_id,
        "name": name,
        "simulated_pool": result.get("simulated_pool"),
        "simulated_cpr": result.get("simulated_cpr"),
        "company_simulated_operating": result.get("company_simulated_operating"),
        "delta_company_operating": result.get("delta_company_operating"),
        "total_simulated_net": total_net,
    }


def compare_scenarios(
    db: Session,
    *,
    scenario_id_a: UUID,
    scenario_id_b: UUID,
    team_id: UUID | None = None,
) -> dict:
    row_a = get_scenario(db, scenario_id_a)
    row_b = get_scenario(db, scenario_id_b)
    comp_a = compute_from_dashboard(db, payload=_parse_payload(row_a.payload_json), team_id=team_id)
    comp_b = compute_from_dashboard(db, payload=_parse_payload(row_b.payload_json), team_id=team_id)
    return {
        "scenario_a": _summary_from_result(row_a.id, row_a.name, comp_a["result"]),
        "scenario_b": _summary_from_result(row_b.id, row_b.name, comp_b["result"]),
    }
