"""Financial Planning API — independent EBMP module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    TeamCommercialTerms,
)
from app.models.models import Activity, Team, User, WorkingModel
from app.schemas.finance import (
    BudgetCreate,
    BudgetRead,
    BudgetStatusUpdate,
    CompanyFinanceSettingsRead,
    CostCentreRead,
    CurrencyRead,
    EmployeeCostProfileCreate,
    EmployeeCostProfileRead,
    EmployeeCostRosterItem,
    ExpenseCreate,
    ExpenseRead,
    FinanceDashboardRead,
    FinancePlanCreate,
    FinancePlanDetail,
    FinancePlanLineCreate,
    FinancePlanLineRead,
    FinancePlanLineUpdate,
    FinancePlanListItem,
    FinancePlanSummary,
    FinancePlanUpdate,
    FinanceReportRow,
    FxRateCreate,
    FxRateRead,
    PaidByDefaultRead,
    QuoteImportResult,
    QuoteRead,
    RenewalNotifyResult,
    TeamCommercialTermsCreate,
    TeamCommercialTermsRead,
    TeamCommercialTermsUpdate,
)
from app.services.finance import annual_plan_service
from app.services.finance.dashboard_service import get_finance_dashboard
from app.services.finance.fx_service import to_base_amount
from app.services.finance.paid_by_defaults import default_paid_by
from app.services.finance.quote_import_service import (
    import_quotes_from_upload,
)
from app.services.finance.renewal_notifier import notify_upcoming_renewals
from app.services.finance.roster_service import get_employee_cost_roster

router = APIRouter(prefix="/finance", tags=["financial-planning"])


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    stmt = select(Expense).where(Expense.is_active.is_(True)).order_by(Expense.name)
    if team_id is not None:
        stmt = stmt.where(Expense.team_id == team_id)
    return db.scalars(stmt).all()


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
            on_date=payload.start_date or date.today(),
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
    return row


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    return get_employee_cost_roster(db, team_id=team_id)


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


def _team_commercial_read(db: Session, row: TeamCommercialTerms) -> TeamCommercialTermsRead:
    team = db.get(Team, row.team_id)
    model = db.get(WorkingModel, row.working_model_id)
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
    if db.get(WorkingModel, payload.working_model_id) is None:
        raise HTTPException(status_code=400, detail="Working model not found")
    try:
        base_fee, fx_rate, _ = to_base_amount(
            db,
            amount=payload.customer_fee_amount,
            currency_code=payload.currency_code,
            on_date=payload.effective_from,
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
        **payload.model_dump(),
        base_fee_inr=base_fee,
        fx_rate=fx_rate,
        is_active=True,
    )
    db.add(row)
    db.flush()
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
    if row is None:
        raise HTTPException(status_code=404, detail="Team commercial terms not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    currency = row.currency_code
    amount = row.customer_fee_amount
    on_date = row.effective_from
    try:
        base_fee, fx_rate, _ = to_base_amount(
            db, amount=amount, currency_code=currency, on_date=on_date
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row.base_fee_inr = base_fee
    row.fx_rate = fx_rate
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


@router.post("/budgets", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    try:
        base_allocated, fx_rate, _ = to_base_amount(
            db, amount=payload.allocated, currency_code=payload.currency_code
        )
        base_spent, _, _ = to_base_amount(
            db, amount=payload.spent, currency_code=payload.currency_code
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    remaining = payload.allocated - payload.spent
    variance = payload.allocated - payload.forecast
    row = Budget(
        **payload.model_dump(),
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


@router.get("/quotes", response_model=list[QuoteRead])
def list_quotes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_VIEW)
    quotes = db.scalars(select(Quote).where(Quote.is_active.is_(True)).order_by(Quote.tool_number)).all()
    return quotes


@router.post("/quotes/import", response_model=QuoteImportResult)
async def import_quotes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_finance_action(db, current_user, MODULE_ACTION_CREATE)
    content = await file.read()
    filename = file.filename or "upload"
    try:
        if filename.lower().endswith(".xls") and not filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail="Legacy .xls is not supported. Save as .xlsx or upload PDF/CSV.",
            )
        quotes = import_quotes_from_upload(
            db, filename=filename, content=content, actor=current_user
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for quote in quotes:
        _audit(
            db,
            user=current_user,
            action=ActivityAction.quote_imported,
            entity_type=EntityType.quote,
            entity_id=quote.id,
            new_value=quote.tool_number,
        )
    db.commit()
    return QuoteImportResult(
        imported_count=len(quotes),
        quote_ids=[quote.id for quote in quotes],
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
    return [
        FinanceReportRow(label="Revenue", amount=revenue, amount_inr=revenue),
        FinanceReportRow(label="Operating Cost", amount=cost, amount_inr=cost),
        FinanceReportRow(label="Gross Profit", amount=profit, amount_inr=profit),
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
        return line
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
    months = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if key.startswith("month_") and value is not None
    }
    try:
        line = annual_plan_service.update_line(
            db,
            plan_id,
            line_id,
            label=payload.label,
            notes=payload.notes,
            months=months or None,
        )
        db.commit()
        db.refresh(line)
        return line
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
