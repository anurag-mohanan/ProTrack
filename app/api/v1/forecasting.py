"""Phase 3 forecasts: read-only, on demand. Each forecast keeps its own access rule."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.access_control import MODULE_FINANCIAL_PLANNING
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import can_view_reports, get_role_name
from app.core.team_access import project_visibility_clause, resolve_team_scope
from app.models.models import Customer, Team, User
from app.schemas.forecasting import (
    CapacityForecastResponse,
    EngineeringForecastResponse,
    FinanceForecastResponse,
    ForecastCatalogResponse,
)
from app.services.forecasting.capacity import build_capacity_forecast
from app.services.forecasting.definitions import DEFINITIONS
from app.services.forecasting.effort import build_engineering_forecast
from app.services.forecasting.finance import build_finance_forecast
from app.services.reporting.report_scope import (
    ReportScopeForbidden,
    resolve_report_scope,
)
from app.services.skills.access import can_view_capacity

router = APIRouter(prefix="/forecasts", tags=["forecasts"], dependencies=[Depends(get_current_user)])


def _can_view_capacity(db: Session, user: User) -> bool:
    return can_view_capacity(db, user)


def _can_view_finance(db: Session, user: User) -> bool:
    return user_has_module_action(user, get_role_name(db, user), MODULE_FINANCIAL_PLANNING, MODULE_ACTION_VIEW)


def _forbid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@router.get("", response_model=ForecastCatalogResponse)
def forecast_catalog(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return ForecastCatalogResponse(
        definitions=list(DEFINITIONS),
        can_view_engineering=can_view_reports(db, current_user),
        can_view_capacity=_can_view_capacity(db, current_user),
        can_view_finance=_can_view_finance(db, current_user),
    )


@router.get("/engineering", response_model=EngineeringForecastResponse)
def engineering_forecast(
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remaining effort for open projects the caller can see. History factor is org-wide; samples are clipped."""
    if not can_view_reports(db, current_user):
        raise _forbid("You do not have access to Reports.")
    try:
        scope = resolve_report_scope(db, current_user)
    except ReportScopeForbidden as exc:
        raise _forbid(str(exc)) from exc
    return build_engineering_forecast(
        db,
        as_of=as_of,
        visibility_clause=project_visibility_clause(db, current_user),
        team_ids=frozenset(scope.team_ids) if scope.team_ids is not None else None,
    )


@router.get("/capacity", response_model=CapacityForecastResponse)
def capacity_forecast(
    start: date | None = Query(None),
    granularity: Literal["week", "month"] = Query("week"),
    periods: int = Query(8, ge=1, le=26),
    team_id: UUID | None = Query(None),
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_view_capacity(db, current_user):
        raise _forbid("Requires the Resource Planning module or view_resource_planning permission.")
    if team_id is not None and db.get(Team, team_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team not found")
    scoped = resolve_team_scope(db, current_user, team_id=team_id)
    if scoped is not None and team_id is not None and team_id not in scoped:
        raise _forbid("Team is outside your accessible scope")
    return build_capacity_forecast(
        db,
        start=start,
        granularity=granularity,
        periods=periods,
        team_ids=scoped,
        project_visibility_clause=project_visibility_clause(db, current_user),
        as_of=as_of,
    )


@router.get("/finance", response_model=FinanceForecastResponse)
def finance_forecast(
    as_of: date | None = Query(None),
    granularity: Literal["week", "month"] = Query("month"),
    periods: int = Query(6, ge=1, le=26),
    team_id: UUID | None = Query(None),
    customer_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_view_finance(db, current_user):
        raise _forbid("Finance access required")
    if team_id is not None and db.get(Team, team_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team not found")
    if customer_id is not None and db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer not found")
    return build_finance_forecast(
        db, as_of=as_of, granularity=granularity, periods=periods, team_id=team_id, customer_id=customer_id
    )
