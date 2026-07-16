"""Financial Planning API — independent EBMP module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import MODULE_FINANCIAL_PLANNING
from app.core.exceptions import ProTrackValidationError
from app.core.module_actions import (
    MODULE_ACTION_APPROVE,
    MODULE_ACTION_CONFIGURE,
    MODULE_ACTION_CREATE,
    MODULE_ACTION_EDIT,
    MODULE_ACTION_EXPORT,
    MODULE_ACTION_VIEW,
    user_has_module_action,
)
from app.core.permissions import get_role_name
from app.models.enums import ActivityAction, BudgetApprovalStatus, BudgetScopeType, EntityType
from app.models.finance import (
    AiForecastPlaceholder,
    Budget,
    CompanyFinanceSettings,
    CostCentre,
    Currency,
    EmployeeCostProfile,
    Expense,
    FxRate,
    Quote,
    TeamCommercialFeeBand,
    TeamCommercialTerms,
)
from app.models.models import Activity, Customer, Team, TeamMember, User, WorkingModel
from app.schemas.finance import (
    BudgetCockpitRead,
    BudgetCreate,
    BudgetRead,
    BudgetStatusUpdate,
    CompanyFinanceSettingsRead,
    CostCentreRead,
    CurrencyRead,
    EmployeeCostProfileCreate,
    EmployeeCostProfileRead,
    EmployeeCostRosterItem,
    EmployeeLeavingDateUpdate,
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    FinanceDashboardRead,
    FinancePlanCloneRequest,
    FinancePlanCreate,
    FinancePlanDetail,
    FinancePlanAiApplyRequest,
    FinancePlanAiInsightsRead,
    FinancePlanLineCreate,
    FinancePlanLineRead,
    FinancePlanLineUpdate,
    FinancePlanListItem,
    FinancePlanSummary,
    FinancePlanUpdate,
    FinanceReportRow,
    FxRateCreate,
    FxRateRead,
    KpiBreakdownRead,
    PaidByDefaultRead,
    PlanVsActualRead,
    QuoteImportItemResult,
    QuoteImportResult,
    QuoteManualCreate,
    QuoteRead,
    QuoteUpdate,
    RenewalNotifyResult,
    TeamCommercialFeeBandInput,
    TeamCommercialFeeBandRead,
    TeamCommercialTermsCreate,
    TeamCommercialTermsRead,
    TeamCommercialTermsUpdate,
)
from app.services.finance import annual_plan_service
from app.services.finance.dashboard_service import get_finance_dashboard
from app.services.finance.fx_service import to_base_amount
from app.services.finance.annual_plan_service import current_fy_start
from app.services.finance.plan_vs_actual_service import (
    compute_plan_vs_actual,
    seed_plan_from_live,
)
from app.services.finance.plan_ai_service import apply_ai_action, build_ai_insights
from app.services.finance.paid_by_defaults import default_paid_by
from app.services.finance.commercial_fee_rules import (
    billing_mode_for_strategy,
    uses_flat_customer_fee,
)
from app.services.finance.quote_import_service import (
    import_quotes_from_upload,
)
from app.services.finance.renewal_notifier import notify_upcoming_renewals
from app.services.finance.roster_service import get_employee_cost_roster
from app.core.salary_eligibility import user_requires_salary
from app.models.enums import WorkingModelCode

router = APIRouter(prefix="/finance", tags=["financial-planning"])


def _expense_read(row: Expense, *, fy_start: date | None = None) -> ExpenseRead:
    start = fy_start or current_fy_start()
    data = ExpenseRead.model_validate(row)
    purchase = row.purchase_date
    excluded = purchase is None or purchase < start
    return data.model_copy(update={"prior_fy_excluded_from_overview": excluded})


def _role(db: Session, user: User) -> str:
    return get_role_name(db, user)


def _require_finance_action(db: Session, user: User, action: str) -> None:
    role_name = _role(db, user)
    if not user_has_module_action(user, role_name, MODULE_FINANCIAL_PLANNING, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Financial Planning access required",
        )


def _audit(
    db: Session,
    *,
    user: User,
    action: ActivityAction,
    entity_type: EntityType,
    entity_id: UUID | None,
    new_value: str | None = None,
) -> None:
    db.add(
        Activity(
            user_id=user.id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            new_value=new_value,
        )
    )


@router.get("/dashboard", response_model=FinanceDashboardRead)
def finance_dashboard(
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    if team_id is not None and db.get(Team, team_id) is None:
        raise HTTPException(status_code=400, detail="Team not found")
    return get_finance_dashboard(db, team_id=team_id)


@router.get("/kpi-breakdown", response_model=KpiBreakdownRead)
def finance_kpi_breakdown(
    metric: str = Query(..., description="KPI metric key, e.g. overhead_opex"),
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ranked composition of a finance KPI total (click-through from cockpit cards)."""
    from app.services.finance.kpi_breakdown_service import get_kpi_breakdown

    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    if team_id is not None and db.get(Team, team_id) is None:
        raise HTTPException(status_code=400, detail="Team not found")
    try:
        return KpiBreakdownRead.model_validate(
            get_kpi_breakdown(db, metric=metric, team_id=team_id)
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/expenses/paid-by-default", response_model=PaidByDefaultRead)
def get_paid_by_default(
    team_id: UUID = Query(...),
    cost_centre_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=400, detail="Team not found")
    if db.get(CostCentre, cost_centre_id) is None:
        raise HTTPException(status_code=400, detail="Cost centre not found")
    paid = default_paid_by(db, team_id=team_id, cost_centre_id=cost_centre_id)
    reason = (
        "Defaulted from Team commercial: customer pays software/hardware"
        if paid.value == "customer"
        else "Defaulted to Paid by Prosohm (team commercial or cost centre)"
    )
    return PaidByDefaultRead(paid_by=paid, reason=reason)


@router.get("/currencies", response_model=list[CurrencyRead])
def list_currencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return db.scalars(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.code)).all()


@router.get("/settings", response_model=CompanyFinanceSettingsRead)
def finance_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    settings = db.scalar(
        select(CompanyFinanceSettings).where(CompanyFinanceSettings.is_active.is_(True))
    )
    if settings is None:
        raise HTTPException(status_code=404, detail="Finance settings not configured")
    return settings


@router.get("/fx-rates", response_model=list[FxRateRead])
def list_fx_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return db.scalars(select(FxRate).order_by(FxRate.effective_date.desc()).limit(200)).all()


@router.post("/fx-rates", response_model=FxRateRead, status_code=status.HTTP_201_CREATED)
def create_fx_rate(
    payload: FxRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CONFIGURE)
    row = FxRate(**payload.model_dump())
    db.add(row)
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.fx_rate_updated,
        entity_type=EntityType.fx_rate,
        entity_id=row.id,
        new_value=f"{row.from_currency}->{row.to_currency}={row.rate}",
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/cost-centres", response_model=list[CostCentreRead])
def list_cost_centres(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return db.scalars(
        select(CostCentre).where(CostCentre.is_active.is_(True)).order_by(CostCentre.sort_order)
    ).all()


@router.get("/expenses", response_model=list[ExpenseRead])
def list_expenses(
    team_id: UUID | None = Query(default=None),
    current_fy_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    fy_start = current_fy_start()
    stmt = select(Expense).where(Expense.is_active.is_(True)).order_by(Expense.name)
    if team_id is not None:
        stmt = stmt.where(Expense.team_id == team_id)
    if current_fy_only:
        stmt = stmt.where(Expense.purchase_date.is_not(None), Expense.purchase_date >= fy_start)
    return [_expense_read(row, fy_start=fy_start) for row in db.scalars(stmt).all()]


@router.post("/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    if db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=400, detail="Team is required and must exist.")
    if db.get(CostCentre, payload.cost_centre_id) is None:
        raise HTTPException(status_code=400, detail="Cost centre not found")
    try:
        base_amount, fx_rate, fx_date = to_base_amount(
            db,
            amount=payload.amount,
            currency_code=payload.currency_code,
            on_date=payload.purchase_date,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = payload.model_dump()
    paid_by = data.pop("paid_by", None)
    if paid_by is None:
        paid_by = default_paid_by(
            db, team_id=payload.team_id, cost_centre_id=payload.cost_centre_id
        )
    row = Expense(
        **data,
        paid_by=paid_by,
        base_amount_inr=base_amount,
        fx_rate=fx_rate,
        fx_date=fx_date,
        is_active=True,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.cost_updated,
        entity_type=EntityType.expense,
        entity_id=row.id,
        new_value=row.name,
    )
    db.commit()
    db.refresh(row)
    return _expense_read(row)


@router.patch("/expenses/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    row = db.get(Expense, expense_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Expense not found")
    data = payload.model_dump(exclude_unset=True)
    if "purchase_date" in data and data["purchase_date"] is None:
        raise HTTPException(status_code=400, detail="Date of purchase is required.")
    if "team_id" in data:
        if data["team_id"] is None or db.get(Team, data["team_id"]) is None:
            raise HTTPException(status_code=400, detail="Team is required and must exist.")
    if "cost_centre_id" in data and data["cost_centre_id"] is not None:
        if db.get(CostCentre, data["cost_centre_id"]) is None:
            raise HTTPException(status_code=400, detail="Cost centre not found")

    paid_by_explicit = "paid_by" in data
    for key, value in data.items():
        setattr(row, key, value)

    team_id = row.team_id
    cost_centre_id = row.cost_centre_id
    if team_id is None:
        raise HTTPException(status_code=400, detail="Team is required and must exist.")
    if row.purchase_date is None:
        raise HTTPException(status_code=400, detail="Date of purchase is required.")
    if not paid_by_explicit and ("team_id" in data or "cost_centre_id" in data):
        row.paid_by = default_paid_by(db, team_id=team_id, cost_centre_id=cost_centre_id)

    try:
        base_amount, fx_rate, fx_date = to_base_amount(
            db,
            amount=row.amount,
            currency_code=row.currency_code,
            on_date=row.purchase_date,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row.base_amount_inr = base_amount
    row.fx_rate = fx_rate
    row.fx_date = fx_date
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.cost_updated,
        entity_type=EntityType.expense,
        entity_id=row.id,
        new_value=f"expense_update:{row.name}",
    )
    db.commit()
    db.refresh(row)
    return _expense_read(row)

@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    row = db.get(Expense, expense_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Expense not found")
    row.is_active = False
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.cost_updated,
        entity_type=EntityType.expense,
        entity_id=row.id,
        new_value=f"expense_deleted:{row.name}",
    )
    db.commit()


@router.post("/renewals/notify", response_model=RenewalNotifyResult)
def trigger_renewal_notifications(
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create in-app notifications for expenses in the renewal window."""
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    count, expense_ids = notify_upcoming_renewals(db, team_id=team_id)
    db.commit()
    return RenewalNotifyResult(notified_count=count, expense_ids=expense_ids)


@router.get("/employee-costs/roster", response_model=list[EmployeeCostRosterItem])
def employee_cost_roster(
    team_id: UUID | None = Query(default=None),
    include_exempt: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return get_employee_cost_roster(db, team_id=team_id, include_exempt=include_exempt)


@router.patch(
    "/employee-costs/roster/{user_id}/leaving-date",
    response_model=EmployeeCostRosterItem,
)
def update_employee_leaving_date(
    user_id: UUID,
    payload: EmployeeLeavingDateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set last working day — salaries/headcount honor this for P&L."""
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.leaving_date = payload.leaving_date
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.cost_updated,
        entity_type=EntityType.user,
        entity_id=user.id,
        new_value=f"leaving_date:{payload.leaving_date}",
    )
    db.commit()
    rows = get_employee_cost_roster(db, include_exempt=True)
    match = next((row for row in rows if row["user_id"] == user_id), None)
    if match is None:
        return {
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "team_names": [],
            "requires_salary": user.requires_salary,
            "has_profile": False,
            "joining_date": user.joining_date,
            "leaving_date": user.leaving_date,
            "salary_month_factor": "0",
        }
    return match


@router.get("/employee-costs", response_model=list[EmployeeCostProfileRead])
def list_employee_costs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return db.scalars(
        select(EmployeeCostProfile).where(EmployeeCostProfile.is_active.is_(True))
    ).all()


@router.post(
    "/employee-costs",
    response_model=EmployeeCostProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def upsert_employee_cost(
    payload: EmployeeCostProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    target = db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user_requires_salary(target):
        raise HTTPException(
            status_code=400,
            detail="User is salary-exempt (Requires salary is off). Enable it on Admin → Users first.",
        )
    try:
        base_salary, fx_rate, _ = to_base_amount(
            db,
            amount=payload.monthly_salary,
            currency_code=payload.currency_code,
            on_date=payload.effective_from,
        )
        base_hourly, _, _ = to_base_amount(
            db,
            amount=payload.hourly_cost,
            currency_code=payload.currency_code,
            on_date=payload.effective_from,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = db.scalar(
        select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == payload.user_id)
    )
    if row is None:
        row = EmployeeCostProfile(
            **payload.model_dump(),
            base_monthly_salary_inr=base_salary,
            base_hourly_cost_inr=base_hourly,
            fx_rate=fx_rate,
            is_active=True,
        )
        db.add(row)
    else:
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        row.base_monthly_salary_inr = base_salary
        row.base_hourly_cost_inr = base_hourly
        row.fx_rate = fx_rate
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.cost_updated,
        entity_type=EntityType.employee_cost,
        entity_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return row


def _salary_required_headcount(db: Session, team_id: UUID) -> int:
    from app.services.finance.billable_headcount import billable_salary_headcount

    return billable_salary_headcount(db, team_id)


def _replace_fee_bands(
    db: Session,
    row: TeamCommercialTerms,
    bands: list[TeamCommercialFeeBandInput] | None,
    *,
    currency_code: str,
    on_date: date,
) -> None:
    if bands is None:
        return
    for existing in list(row.fee_bands or []):
        db.delete(existing)
    db.flush()
    for band in bands:
        skill = (band.skill_level or "").strip().lower()
        amount = band.fee_amount or Decimal("0")
        currency = band.currency_code or currency_code
        base_fee, fx_rate, _ = to_base_amount(
            db, amount=amount, currency_code=currency, on_date=on_date
        )
        db.add(
            TeamCommercialFeeBand(
                terms_id=row.id,
                skill_level=skill,
                fee_amount=amount,
                currency_code=currency,
                base_fee_inr=base_fee,
                fx_rate=fx_rate,
                notes=band.notes,
            )
        )
    db.flush()


def _team_commercial_read(db: Session, row: TeamCommercialTerms) -> TeamCommercialTermsRead:
    from app.services.finance.dashboard_service import _normalize_monthly_fee
    from app.services.finance.billable_headcount import billable_salary_counts_by_skill

    team = db.get(Team, row.team_id)
    model = db.get(WorkingModel, row.working_model_id)
    strategy = model.strategy_key.value if model is not None else None
    resource_count = _salary_required_headcount(db, row.team_id)
    counts = billable_salary_counts_by_skill(db, row.team_id)
    fee_band_reads: list[TeamCommercialFeeBandRead] = []
    for band in sorted(row.fee_bands or [], key=lambda b: b.skill_level or ""):
        skill = band.skill_level or ""
        fee_band_reads.append(
            TeamCommercialFeeBandRead(
                id=band.id,
                terms_id=band.terms_id,
                skill_level=skill or None,
                fee_amount=band.fee_amount,
                currency_code=band.currency_code,
                base_fee_inr=band.base_fee_inr,
                fx_rate=band.fx_rate,
                notes=band.notes,
                billable_count=counts.get(skill, 0),
            )
        )
    if strategy == WorkingModelCode.retainer.value:
        bands = list(row.fee_bands or [])
        if bands:
            band_map = {(b.skill_level or ""): Decimal(str(b.base_fee_inr or 0)) for b in bands}
            default_rate = band_map.get("") or Decimal(str(row.base_fee_inr or 0))
            period_amount = Decimal("0.00")
            for skill, count in counts.items():
                period_amount += band_map.get(skill, default_rate) * Decimal(count)
        else:
            period_amount = Decimal(str(row.base_fee_inr or 0)) * Decimal(resource_count or 0)
        monthly_signal = _normalize_monthly_fee(period_amount, row.billing_period)
    elif uses_flat_customer_fee(strategy):
        monthly_signal = _normalize_monthly_fee(Decimal(str(row.base_fee_inr or 0)), row.billing_period)
    else:
        monthly_signal = Decimal("0.00")
    return TeamCommercialTermsRead(
        id=row.id,
        team_id=row.team_id,
        working_model_id=row.working_model_id,
        billing_mode=row.billing_mode,
        customer_fee_amount=row.customer_fee_amount,
        currency_code=row.currency_code,
        billing_period=row.billing_period,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        notes=row.notes,
        customer_pays_software=bool(getattr(row, "customer_pays_software", False)),
        customer_pays_hardware=bool(getattr(row, "customer_pays_hardware", False)),
        base_fee_inr=row.base_fee_inr,
        fx_rate=row.fx_rate,
        is_active=row.is_active,
        team_name=team.name if team else None,
        working_model_name=model.name if model else None,
        working_model_strategy=strategy,
        resource_count=resource_count,
        monthly_fee_signal_inr=monthly_signal,
        fee_bands=fee_band_reads,
    )


@router.get("/team-commercial", response_model=list[TeamCommercialTermsRead])
def list_team_commercial(
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    stmt = (
        select(TeamCommercialTerms)
        .where(TeamCommercialTerms.is_active.is_(True))
        .options(selectinload(TeamCommercialTerms.fee_bands))
        .order_by(TeamCommercialTerms.effective_from.desc())
    )
    if team_id is not None:
        stmt = stmt.where(TeamCommercialTerms.team_id == team_id)
    rows = db.scalars(stmt).all()
    return [_team_commercial_read(db, row) for row in rows]


@router.post(
    "/team-commercial",
    response_model=TeamCommercialTermsRead,
    status_code=status.HTTP_201_CREATED,
)
def create_team_commercial(
    payload: TeamCommercialTermsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    if db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=400, detail="Team not found")
    model = db.get(WorkingModel, payload.working_model_id)
    if model is None:
        raise HTTPException(status_code=400, detail="Working model not found")
    data = payload.model_dump(exclude={"fee_bands"})
    strategy = model.strategy_key
    data["billing_mode"] = data.get("billing_mode") or billing_mode_for_strategy(strategy)
    if not uses_flat_customer_fee(strategy):
        data["customer_fee_amount"] = 0
    try:
        base_fee, fx_rate, _ = to_base_amount(
            db,
            amount=data["customer_fee_amount"],
            currency_code=data["currency_code"],
            on_date=data["effective_from"],
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Soft-close prior active terms for this team (one active row per team).
    prior = db.scalars(
        select(TeamCommercialTerms).where(
            TeamCommercialTerms.team_id == payload.team_id,
            TeamCommercialTerms.is_active.is_(True),
        )
    ).all()
    for old in prior:
        old.is_active = False
        if old.effective_to is None:
            old.effective_to = payload.effective_from
    row = TeamCommercialTerms(
        **data,
        base_fee_inr=base_fee,
        fx_rate=fx_rate,
        is_active=True,
    )
    db.add(row)
    db.flush()
    try:
        _replace_fee_bands(
            db,
            row,
            payload.fee_bands,
            currency_code=row.currency_code,
            on_date=row.effective_from,
        )
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit(
        db,
        user=current_user,
        action=ActivityAction.cost_updated,
        entity_type=EntityType.team,
        entity_id=row.team_id,
        new_value=f"team_commercial:{row.billing_mode.value}",
    )
    db.commit()
    db.refresh(row)
    return _team_commercial_read(db, row)


@router.put("/team-commercial/{terms_id}", response_model=TeamCommercialTermsRead)
def update_team_commercial(
    terms_id: UUID,
    payload: TeamCommercialTermsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    row = db.get(TeamCommercialTerms, terms_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Team commercial terms not found")
    data = payload.model_dump(exclude_unset=True)
    fee_bands = data.pop("fee_bands", None)
    for key, value in data.items():
        setattr(row, key, value)
    model = db.get(WorkingModel, row.working_model_id)
    if model is None:
        raise HTTPException(status_code=400, detail="Working model not found")
    strategy = model.strategy_key
    if "billing_mode" not in data or data.get("billing_mode") is None:
        row.billing_mode = billing_mode_for_strategy(strategy)
    if not uses_flat_customer_fee(strategy):
        row.customer_fee_amount = 0
    currency = row.currency_code
    amount = row.customer_fee_amount
    on_date = row.effective_from
    try:
        base_fee, fx_rate, _ = to_base_amount(
            db, amount=amount, currency_code=currency, on_date=on_date
        )
        row.base_fee_inr = base_fee
        row.fx_rate = fx_rate
        _replace_fee_bands(
            db,
            row,
            fee_bands,
            currency_code=currency,
            on_date=on_date,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.cost_updated,
        entity_type=EntityType.team,
        entity_id=row.team_id,
        new_value=f"team_commercial_update:{row.id}",
    )
    db.commit()
    db.refresh(row)
    return _team_commercial_read(db, row)


@router.delete("/team-commercial/{terms_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_commercial(
    terms_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    row = db.get(TeamCommercialTerms, terms_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Team commercial terms not found")
    row.is_active = False
    db.commit()


@router.get("/budgets", response_model=list[BudgetRead])
def list_budgets(
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    stmt = select(Budget).where(Budget.is_active.is_(True))
    if team_id is not None:
        stmt = stmt.where(Budget.scope_type == BudgetScopeType.team, Budget.scope_id == team_id)
    return db.scalars(stmt.order_by(Budget.name)).all()


@router.get("/budgets/cockpit", response_model=BudgetCockpitRead)
def budgets_cockpit(
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Portfolio KPIs, quarterly rollups, and risk insights for Budgets & reports."""
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    if team_id is not None and db.get(Team, team_id) is None:
        raise HTTPException(status_code=400, detail="Team not found")
    from app.services.finance.budget_cockpit_service import build_budget_cockpit

    return BudgetCockpitRead.model_validate(build_budget_cockpit(db, team_id=team_id))


@router.post("/budgets", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    from app.services.finance.renewal_budget_service import (
        apply_renewals_to_budget_forecast_quarters,
        even_split_four,
        renewals_by_quarter_inr,
    )

    data = payload.model_dump()
    allocated = Decimal(str(data.get("allocated") or 0))
    quarter_alloc = {
        "q1": Decimal(str(data.get("q1_allocated") or 0)),
        "q2": Decimal(str(data.get("q2_allocated") or 0)),
        "q3": Decimal(str(data.get("q3_allocated") or 0)),
        "q4": Decimal(str(data.get("q4_allocated") or 0)),
    }
    if sum(quarter_alloc.values()) == 0 and allocated:
        quarter_alloc = even_split_four(allocated)
        data.update({f"{k}_allocated": v for k, v in quarter_alloc.items()})
        data["allocated"] = allocated
    else:
        data["allocated"] = sum(quarter_alloc.values()) or allocated

    fy_year = data.get("fiscal_year")
    fy_start = (
        date(int(fy_year), 4, 1)
        if fy_year
        else current_fy_start()
    )
    team_scope = data.get("scope_id") if data.get("scope_type") == BudgetScopeType.team else None
    renewals = renewals_by_quarter_inr(db, fy_start=fy_start, team_id=team_scope)
    forecast_q = {
        "q1": Decimal(str(data.get("q1_forecast") or 0)),
        "q2": Decimal(str(data.get("q2_forecast") or 0)),
        "q3": Decimal(str(data.get("q3_forecast") or 0)),
        "q4": Decimal(str(data.get("q4_forecast") or 0)),
    }
    if sum(forecast_q.values()) == 0:
        forecast_q = apply_renewals_to_budget_forecast_quarters(
            q_allocated=quarter_alloc, renewals=renewals
        )
    data.update({f"{k}_forecast": v for k, v in forecast_q.items()})
    data["forecast"] = sum(forecast_q.values())

    try:
        base_allocated, fx_rate, _ = to_base_amount(
            db, amount=data["allocated"], currency_code=data["currency_code"]
        )
        base_spent, _, _ = to_base_amount(
            db, amount=data["spent"], currency_code=data["currency_code"]
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    remaining = data["allocated"] - data["spent"]
    variance = data["allocated"] - data["forecast"]
    row = Budget(
        **data,
        remaining=remaining,
        variance=variance,
        base_allocated_inr=base_allocated,
        base_spent_inr=base_spent,
        fx_rate=fx_rate,
        approval_status=BudgetApprovalStatus.draft,
        is_active=True,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        user=current_user,
        action=ActivityAction.budget_created,
        entity_type=EntityType.budget,
        entity_id=row.id,
        new_value=row.name,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/plans/{plan_id}/sync-renewals", response_model=FinancePlanDetail)
def sync_plan_renewals(
    plan_id: UUID,
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed/refresh Annual Plan expense lines from known software renewals in the FY."""
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    from app.services.finance.renewal_budget_service import sync_renewals_into_plan

    try:
        plan = sync_renewals_into_plan(db, plan_id, team_id=team_id)
        db.commit()
        plan = annual_plan_service.get_plan(db, plan.id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/sync-sales-from-quotes", response_model=FinancePlanDetail)
def sync_plan_sales_from_quotes(
    plan_id: UUID,
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert Annual Plan sales lines from awarded quotes by quoted_date FY quarter."""
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    from app.services.finance.plan_sales_from_quotes_service import (
        sync_sales_from_awarded_quotes,
    )

    try:
        plan, _counts = sync_sales_from_awarded_quotes(db, plan_id, team_id=team_id)
        db.commit()
        plan = annual_plan_service.get_plan(db, plan.id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/plans/{plan_id}/plan-vs-actual", response_model=PlanVsActualRead)
def get_plan_vs_actual(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """YTD plan vs live run-rate actuals + rolling FY forecast (FP&A Phase A)."""
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    try:
        plan = annual_plan_service.get_plan(db, plan_id)
        return PlanVsActualRead.model_validate(compute_plan_vs_actual(db, plan))
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/seed-from-live", response_model=FinancePlanDetail)
def seed_plan_from_live_endpoint(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fill Wages + Overhead lines from live salary roster and overhead pool."""
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    try:
        plan = seed_plan_from_live(db, plan_id)
        db.commit()
        plan = annual_plan_service.get_plan(db, plan.id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/plans/{plan_id}/clone",
    response_model=FinancePlanDetail,
    status_code=status.HTTP_201_CREATED,
)
def clone_finance_plan(
    plan_id: UUID,
    payload: FinancePlanCloneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clone a plan as a named scenario under the same fiscal year."""
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    try:
        plan = annual_plan_service.clone_plan(
            db, plan_id, scenario_name=payload.scenario_name
        )
        db.commit()
        plan = annual_plan_service.get_plan(db, plan.id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/plans/{plan_id}/ai-insights", response_model=FinancePlanAiInsightsRead)
def get_plan_ai_insights(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministic AI Assist insights for an annual plan (no external LLM)."""
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    try:
        return FinancePlanAiInsightsRead.model_validate(build_ai_insights(db, plan_id))
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/ai-apply", response_model=FinancePlanDetail)
def apply_plan_ai_action(
    plan_id: UUID,
    payload: FinancePlanAiApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply an opt-in AI Assist action to the plan workbook."""
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    try:
        plan = apply_ai_action(db, plan_id, action_code=payload.action_code)
        db.commit()
        plan = annual_plan_service.get_plan(db, plan.id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/budgets/{budget_id}/status", response_model=BudgetRead)
def update_budget_status(
    budget_id: UUID,
    payload: BudgetStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_APPROVE)
    row = db.get(Budget, budget_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    row.approval_status = payload.approval_status
    action = (
        ActivityAction.budget_approved
        if payload.approval_status == BudgetApprovalStatus.approved
        else ActivityAction.budget_rejected
    )
    _audit(
        db,
        user=current_user,
        action=action,
        entity_type=EntityType.budget,
        entity_id=row.id,
        new_value=payload.approval_status.value,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/budgets/{budget_id}/sync-spent", response_model=BudgetRead)
def sync_budget_spent(
    budget_id: UUID,
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Opt-in: set budget spent from live YTD operating cost run-rate."""
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    from app.services.finance.budget_cockpit_service import sync_budget_spent_from_operating

    try:
        row = sync_budget_spent_from_operating(db, budget_id, team_id=team_id)
        db.commit()
        db.refresh(row)
        return row
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/quotes", response_model=list[QuoteRead])
def list_quotes(
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    stmt = select(Quote).where(Quote.is_active.is_(True)).order_by(Quote.tool_number)
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)
    return [_quote_read(db, row) for row in db.scalars(stmt).all()]


@router.patch("/quotes/{quote_id}", response_model=QuoteRead)
def update_quote_endpoint(
    quote_id: UUID,
    payload: QuoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.finance.quote_import_service import update_quote

    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    row = db.get(Quote, quote_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Quote not found")
    if payload.team_id is not None and db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=400, detail="Team is required and must exist.")
    data = payload.model_dump(exclude_unset=True)
    create_project = bool(data.pop("create_project", False))
    try:
        update_quote(
            db,
            quote=row,
            actor=current_user,
            create_project=create_project,
            **data,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit(
        db,
        user=current_user,
        action=ActivityAction.quote_revised,
        entity_type=EntityType.quote,
        entity_id=row.id,
        new_value=row.external_quote_number or row.tool_number,
    )
    db.commit()
    db.refresh(row)
    return _quote_read(db, row)


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quote_endpoint(
    quote_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.finance.quote_import_service import soft_delete_quote

    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    row = db.get(Quote, quote_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Quote not found")
    soft_delete_quote(db, quote=row)
    _audit(
        db,
        user=current_user,
        action=ActivityAction.quote_revised,
        entity_type=EntityType.quote,
        entity_id=row.id,
        new_value=f"quote_deleted:{row.external_quote_number or row.tool_number}",
    )
    db.commit()


def _quote_import_items(
    db: Session,
    *,
    current_user: User,
    outcomes: list,
) -> list[QuoteImportItemResult]:
    from app.services.finance.quote_import_service import QuoteImportOutcome

    items: list[QuoteImportItemResult] = []
    for outcome in outcomes:
        assert isinstance(outcome, QuoteImportOutcome)
        quote = outcome.quote
        if outcome.project_created and quote.project_id is not None:
            _audit(
                db,
                user=current_user,
                action=ActivityAction.project_created,
                entity_type=EntityType.project,
                entity_id=quote.project_id,
                new_value=f"created_from_quote_import:{quote.tool_number}",
            )
        _audit(
            db,
            user=current_user,
            action=ActivityAction.quote_imported,
            entity_type=EntityType.quote,
            entity_id=quote.id,
            new_value=quote.external_quote_number or quote.tool_number,
        )
        customer = db.get(Customer, quote.customer_id)
        team = db.get(Team, quote.team_id) if quote.team_id else None
        items.append(
            QuoteImportItemResult(
                quote_id=quote.id,
                tool_number=quote.tool_number,
                external_quote_number=quote.external_quote_number,
                customer_name=customer.name if customer else None,
                team_name=team.name if team else None,
                quoted_hours=outcome.quoted_hours,
                quoted_revenue=outcome.quoted_revenue,
                currency_code=quote.currency_code,
                project_linked=quote.project_id is not None,
                project_created=outcome.project_created,
                warnings=outcome.warnings,
            )
        )
    return items


@router.post("/quotes/manual", response_model=QuoteImportResult)
def create_manual_quote(
    payload: QuoteManualCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phase path: type Quote #, Project #, and cost — no smart PDF required."""
    from app.services.finance.quote_import_service import import_manual_quote

    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    if db.get(Team, payload.team_id) is None:
        raise HTTPException(status_code=400, detail="Team is required and must exist.")
    try:
        outcome = import_manual_quote(
            db,
            actor=current_user,
            team_id=payload.team_id,
            customer_id=payload.customer_id,
            tool_number=payload.tool_number,
            quoted_revenue=payload.quoted_revenue,
            external_quote_number=payload.external_quote_number,
            currency_code=payload.currency_code,
            quoted_hours=payload.quoted_hours,
            quoted_date=payload.quoted_date,
            create_project=payload.create_project,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = _quote_import_items(db, current_user=current_user, outcomes=[outcome])
    db.commit()
    return QuoteImportResult(
        imported_count=1,
        quote_ids=[outcome.quote.id],
        items=items,
    )


@router.post("/quotes/import", response_model=QuoteImportResult)
async def import_quotes(
    file: UploadFile = File(...),
    team_id: UUID = Form(...),
    create_project: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    if db.get(Team, team_id) is None:
        raise HTTPException(status_code=400, detail="Team is required and must exist.")
    content = await file.read()
    filename = file.filename or "upload"
    try:
        if filename.lower().endswith(".xls") and not filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail="Legacy .xls is not supported. Save as .xlsx or upload PDF/CSV.",
            )
        outcomes = import_quotes_from_upload(
            db,
            filename=filename,
            content=content,
            actor=current_user,
            team_id=team_id,
            create_project=create_project,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = _quote_import_items(db, current_user=current_user, outcomes=outcomes)
    db.commit()
    return QuoteImportResult(
        imported_count=len(outcomes),
        quote_ids=[item.quote.id for item in outcomes],
        items=items,
    )


def _quote_read(db: Session, row: Quote) -> QuoteRead:
    from app.services.finance.quote_import_service import _current_revision

    customer = db.get(Customer, row.customer_id)
    team = db.get(Team, row.team_id) if row.team_id else None
    revision = _current_revision(db, row)
    data = QuoteRead.model_validate(row)
    return data.model_copy(
        update={
            "team_name": team.name if team else None,
            "customer_name": customer.name if customer else None,
            "project_linked": row.project_id is not None,
            "quoted_hours": revision.quoted_hours if revision else None,
            "quoted_revenue": revision.quoted_revenue if revision else None,
            "base_quoted_revenue_inr": (
                revision.base_quoted_revenue_inr if revision else None
            ),
            "fx_rate": revision.fx_rate if revision else None,
            "fx_date": revision.fx_date if revision else None,
            "revisions": [],
        }
    )


@router.get("/reports/profit-loss", response_model=list[FinanceReportRow])
def report_profit_loss(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    dash = get_finance_dashboard(db)
    revenue = Decimal(str(dash["revenue"]["yearly_revenue"]))
    cost = Decimal(str(dash["cost"]["monthly_operating_cost"]))
    profit = Decimal(str(dash["profitability"]["gross_profit"]))
    overhead = dash.get("overhead") or {}
    pool = Decimal(str(overhead.get("overhead_pool_monthly_inr") or 0))
    cpr = Decimal(str(overhead.get("overhead_cost_per_resource_inr") or 0))
    return [
        FinanceReportRow(label="Revenue (yearly signal)", amount=revenue, amount_inr=revenue),
        FinanceReportRow(label="Gross Profit (monthly signal)", amount=profit, amount_inr=profit),
        FinanceReportRow(label="Operating Cost (monthly)", amount=cost, amount_inr=cost),
        FinanceReportRow(
            label="Overhead pool (Corporate monthly)",
            amount=pool,
            amount_inr=pool,
        ),
        FinanceReportRow(
            label="Overhead cost per billable resource (monthly)",
            amount=cpr,
            amount_inr=cpr,
        ),
    ]


@router.get("/reports/project-profitability", response_model=list[FinanceReportRow])
def report_project_profitability(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EXPORT)
    dash = get_finance_dashboard(db)
    return [
        FinanceReportRow(
            label=str(row.get("project_id")),
            amount=Decimal(str(row.get("gross_profit") or 0)),
            amount_inr=Decimal(str(row.get("base_revenue_inr") or 0)),
            currency_code=str(row.get("currency_code") or "INR"),
        )
        for row in dash["project_snapshots"]
    ]


@router.get("/ai-placeholders")
def list_ai_placeholders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return db.scalars(
        select(AiForecastPlaceholder).where(AiForecastPlaceholder.is_active.is_(True))
    ).all()


def _plan_detail_response(plan) -> FinancePlanDetail:
    payload = annual_plan_service.plan_to_detail_dict(plan)
    return FinancePlanDetail(
        id=payload["id"],
        name=payload["name"],
        fiscal_year_label=payload["fiscal_year_label"],
        fy_start_date=payload["fy_start_date"],
        fy_end_date=payload["fy_end_date"],
        currency_code=payload["currency_code"],
        tax_percent=payload["tax_percent"],
        provision_percent=payload["provision_percent"],
        status=payload["status"],
        lines=[FinancePlanLineRead.model_validate(row) for row in payload["lines"]],
        summary=FinancePlanSummary.model_validate(payload["summary"]),
        line_totals=payload["line_totals"],
    )


@router.get("/plans", response_model=list[FinancePlanListItem])
def list_finance_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return annual_plan_service.list_plans(db)


@router.post("/plans", response_model=FinancePlanDetail, status_code=status.HTTP_201_CREATED)
def create_finance_plan(
    payload: FinancePlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    try:
        plan = annual_plan_service.create_plan(
            db,
            name=payload.name,
            fiscal_year_start_year=payload.fiscal_year_start_year,
            fy_start_month=payload.fy_start_month,
            currency_code=payload.currency_code,
            tax_percent=payload.tax_percent,
            provision_percent=payload.provision_percent,
        )
        db.commit()
        plan = annual_plan_service.get_plan(db, plan.id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/plans/{plan_id}", response_model=FinancePlanDetail)
def get_finance_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    try:
        plan = annual_plan_service.get_plan(db, plan_id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/plans/{plan_id}", response_model=FinancePlanDetail)
def patch_finance_plan(
    plan_id: UUID,
    payload: FinancePlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    try:
        plan = annual_plan_service.update_plan(
            db,
            plan_id,
            name=payload.name,
            tax_percent=payload.tax_percent,
            provision_percent=payload.provision_percent,
            status=payload.status,
        )
        db.commit()
        plan = annual_plan_service.get_plan(db, plan.id)
        return _plan_detail_response(plan)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/lines", response_model=FinancePlanLineRead, status_code=status.HTTP_201_CREATED)
def create_finance_plan_line(
    plan_id: UUID,
    payload: FinancePlanLineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    try:
        line = annual_plan_service.add_line(
            db,
            plan_id,
            section=payload.section,
            code=payload.code,
            label=payload.label,
        )
        db.commit()
        db.refresh(line)
        return FinancePlanLineRead.model_validate(annual_plan_service.line_to_read_dict(line))
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/plans/{plan_id}/lines/{line_id}", response_model=FinancePlanLineRead)
def update_finance_plan_line(
    plan_id: UUID,
    line_id: UUID,
    payload: FinancePlanLineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    dumped = payload.model_dump(exclude_unset=True)
    months = {
        key: value
        for key, value in dumped.items()
        if key.startswith("month_") and value is not None
    }
    quarters = {
        key: value
        for key, value in dumped.items()
        if key in {"q1", "q2", "q3", "q4"} and value is not None
    }
    try:
        line = annual_plan_service.update_line(
            db,
            plan_id,
            line_id,
            label=payload.label,
            notes=payload.notes,
            months=months or None,
            quarters=quarters or None,
        )
        db.commit()
        db.refresh(line)
        return FinancePlanLineRead.model_validate(annual_plan_service.line_to_read_dict(line))
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/plans/{plan_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_finance_plan_line(
    plan_id: UUID,
    line_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_EDIT)
    try:
        annual_plan_service.delete_line(db, plan_id, line_id)
        db.commit()
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
