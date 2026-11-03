"""Automatic KPI registry for strategic objectives.

Each entry reads its actual from an existing management builder (which in turn uses the Finance
ledger, Quote-to-Delivery metrics, official hours rule, capacity calendar or skills records), for
the objective's period and parameters. Objectives are company documents, so the figure is
calculated organisation-wide and then shown only to people allowed to see that kind of figure.
Nothing here is stored as an actual; it is recalculated on read and snapshotted into reviews.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.user_types import employee_user_clause
from app.models.enums import ProjectClassification
from app.models.foundation import Skill, UserSkill
from app.models.models import Customer, Team, User
from app.models.skills import STATUS_VERIFIED
from app.services.management.access import ManagementAccess
from app.services.management.business import build_business
from app.services.management.filters import CockpitFilters, Period
from app.services.management.metrics import (
    COUNT,
    CURRENCY,
    DAYS,
    HOURS,
    KPI_DEFINITIONS,
    PERCENTAGE,
)
from app.services.management.operations import booked_hours, build_operations
from app.services.management.workforce import build_workforce

INCREASE, DECREASE = "increase", "decrease"
PARAMS = ("customer_id", "classification", "team_id", "skill_id", "min_level")


@dataclass(frozen=True)
class KpiSpec:
    key: str
    unit: str
    direction: str
    calc: Callable[[Session, ManagementAccess, CockpitFilters, dict, date], tuple]
    scope: str  # finance | workforce | operations
    params: tuple[str, ...] = ()
    point_in_time: bool = False
    note: str | None = None
    required: tuple[str, ...] = field(default=())

    @property
    def label(self) -> str:
        return KPI_DEFINITIONS.get(self.key, {}).get("label", self.key.replace("_", " ").capitalize())


def calculation_access(viewer: ManagementAccess) -> ManagementAccess:
    """Organisation-wide calculation; visibility of the result is decided separately."""
    return ManagementAccess(user=viewer.user, admin=True, org_wide=True, report_team_ids=None, visibility_clause=None,
                            finance=True, capacity=True, hr=True, manage=False, approve=False, export=False)


def can_view(viewer: ManagementAccess, spec: KpiSpec) -> tuple[bool, str | None]:
    if spec.scope == "finance" and not viewer.finance:
        return False, "Finance figure: needs Finance view access."
    if spec.scope == "workforce" and not viewer.workforce:
        return False, "Workforce figure: needs Resource Planning or HR view access."
    if spec.scope == "operations" and not viewer.reviews:
        return False, "Company-wide delivery figure: needs organisation-wide report scope."
    return True, None


def _filters(period: Period, params: dict) -> CockpitFilters:
    return CockpitFilters(
        period,
        customer_id=UUID(params["customer_id"]) if params.get("customer_id") else None,
        classification=ProjectClassification(params["classification"]) if params.get("classification") else None,
        team_id=UUID(params["team_id"]) if params.get("team_id") else None,
    )


def _from(section: dict, key: str) -> tuple:
    item = next((k for k in section.get("kpis", []) if k["key"] == key), None)
    if item is None:
        return None, None, section.get("reason")
    return item["value"], item["sample"], item["note"]


def _business(key: str):
    def calc(db, access, filters, params, today):
        return _from(build_business(db, access, filters, today), key)
    return calc


def _operations(key: str):
    def calc(db, access, filters, params, today):
        return _from(build_operations(db, access, filters, today), key)
    return calc


def _workforce(key: str):
    def calc(db, access, filters, params, today):
        return _from(build_workforce(db, access, filters, today), key)
    return calc


def _hours_booked(db, access, filters, params, today):
    rows = booked_hours(db, access, filters, "month")
    return (sum(r["hours"] or 0 for r in rows), sum(r["projects"] for r in rows), None) if rows else (0, 0, None)


def _skill_holders(db, access, filters, params, today):
    skill_id = UUID(params["skill_id"])
    stmt = (
        select(func.count(func.distinct(UserSkill.user_id)))
        .join(User, User.id == UserSkill.user_id)
        .where(UserSkill.skill_id == skill_id, UserSkill.status == STATUS_VERIFIED, User.is_active.is_(True),
               User.is_deleted.is_(False), employee_user_clause())
    )
    if params.get("min_level"):
        stmt = stmt.where(UserSkill.verified_level >= int(params["min_level"]))
    return db.scalar(stmt) or 0, None, "Active employees with a verified record, as of today."


_OPS_PARAMS = ("customer_id", "classification", "team_id")
REGISTRY: dict[str, KpiSpec] = {
    spec.key: spec
    for spec in (
        KpiSpec("invoiced_revenue", CURRENCY, INCREASE, _business("invoiced_revenue"), "finance", ("customer_id", "team_id")),
        KpiSpec("collections", CURRENCY, INCREASE, _business("collections"), "finance", ("customer_id", "team_id")),
        KpiSpec("awarded_value", CURRENCY, INCREASE, _business("awarded_value"), "finance", ("customer_id", "team_id")),
        KpiSpec("outstanding_receivables", CURRENCY, DECREASE, _business("outstanding_receivables"), "finance",
                ("customer_id", "team_id"), point_in_time=True),
        KpiSpec("projects_completed", COUNT, INCREASE, _operations("projects_completed"), "operations", _OPS_PARAMS),
        KpiSpec("on_time_delivery_rate", PERCENTAGE, INCREASE, _operations("on_time_delivery_rate"), "operations",
                _OPS_PARAMS),
        KpiSpec("delivery_variance_days", DAYS, DECREASE, _operations("delivery_variance_days"), "operations",
                _OPS_PARAMS),
        KpiSpec("hour_variance_percent", PERCENTAGE, DECREASE, _operations("hour_variance_percent"), "operations",
                _OPS_PARAMS),
        KpiSpec("rework_hours", HOURS, DECREASE, _operations("rework_hours"), "operations", _OPS_PARAMS),
        KpiSpec("hours_booked", HOURS, INCREASE, _hours_booked, "operations", _OPS_PARAMS),
        KpiSpec("capacity_utilisation", PERCENTAGE, INCREASE, _workforce("capacity_utilisation"), "workforce",
                ("team_id",)),
        KpiSpec("training_completion_rate", PERCENTAGE, INCREASE, _workforce("training_completion_rate"), "workforce",
                ("team_id",)),
        KpiSpec("skill_verified_holders", COUNT, INCREASE, _skill_holders, "workforce", ("skill_id", "min_level"),
                point_in_time=True, required=("skill_id",)),
    )
}


def registry_list() -> list[dict]:
    return [
        {"key": s.key, "label": s.label, "unit": s.unit, "direction": s.direction, "scope": s.scope,
         "params": list(s.params), "required_params": list(s.required), "point_in_time": s.point_in_time,
         "definition": KPI_DEFINITIONS.get(s.key, {}).get("definition"), "source": KPI_DEFINITIONS.get(s.key, {}).get("source")}
        for s in REGISTRY.values()
    ]


def validate_params(db: Session, key: str, params: dict | None) -> dict:
    spec = REGISTRY.get(key)
    if spec is None:
        raise ValueError(f"Unknown automatic KPI '{key}'")
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    unknown = set(params) - set(spec.params)
    if unknown:
        raise ValueError(f"{spec.label} does not take: {', '.join(sorted(unknown))}")
    missing = [p for p in spec.required if p not in params]
    if missing:
        raise ValueError(f"{spec.label} needs: {', '.join(missing)}")
    checks = {"customer_id": Customer, "team_id": Team, "skill_id": Skill}
    for name, model in checks.items():
        if name in params:
            try:
                ident = UUID(str(params[name]))
            except ValueError as exc:
                raise ValueError(f"{name} is not a valid id") from exc
            if db.get(model, ident) is None:
                raise ValueError(f"Unknown {name.removesuffix('_id')}")
            params[name] = str(ident)
    if "classification" in params:
        ProjectClassification(params["classification"])
    if "min_level" in params:
        level = int(params["min_level"])
        if not 1 <= level <= 5:
            raise ValueError("min_level must be between 1 and 5")
        params["min_level"] = level
    return params


def calculate(db: Session, viewer: ManagementAccess, key: str, params: dict, period: Period,
              today: date | None = None) -> dict:
    """The actual for one automatic KPI, or the reason it is hidden or unavailable."""
    today = today or date.today()
    spec = REGISTRY[key]
    allowed, reason = can_view(viewer, spec)
    base = {"key": key, "label": spec.label, "unit": spec.unit, "kind": "actual",
            "point_in_time": spec.point_in_time, "period": period.as_dict(), "as_of": today.isoformat(),
            "source": KPI_DEFINITIONS.get(key, {}).get("source")}
    if not allowed:
        return {**base, "visible": False, "value": None, "status": "restricted", "note": reason}
    if period.start > today:
        return {**base, "visible": True, "value": None, "status": "not_started",
                "note": "The period has not started; no actual exists yet."}
    value, sample, note = spec.calc(db, calculation_access(viewer), _filters(period, params), params, today)
    return {**base, "visible": True, "value": value, "sample": sample, "note": note,
            "status": "unavailable" if value is None else "available"}
