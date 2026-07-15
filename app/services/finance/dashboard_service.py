"""Financial dashboard aggregates — Finance Rebuild 2 (team-scoped)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import BudgetApprovalStatus, CostNature, ExpensePaidBy, TeamBillingPeriod
from app.models.finance import (
    AiForecastPlaceholder,
    Budget,
    EmployeeCostProfile,
    Expense,
    ProjectFinancialSnapshot,
    QuoteRevision,
    TeamCommercialTerms,
)
from app.models.models import Project, Team, TeamMember, User
from app.services.finance.fx_service import get_base_currency
from app.services.finance.renewal_notifier import list_upcoming_renewals


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _normalize_monthly_fee(amount: Decimal, period: TeamBillingPeriod) -> Decimal:
    if period == TeamBillingPeriod.monthly:
        return amount
    if period == TeamBillingPeriod.quarterly:
        return (amount / Decimal("3")).quantize(Decimal("0.01"))
    if period == TeamBillingPeriod.annual:
        return (amount / Decimal("12")).quantize(Decimal("0.01"))
    return amount


def _user_ids_for_team(db: Session, team_id: UUID) -> set[UUID]:
    """Salary rollup for a team operating cost.

    - Primary home on this team.
    - Delivery teams: only **billable** membership (fixed-resource engineers).
      Managers / Planning Board / Design Leaders with ``is_billable_headcount=False``
      are Prosohm overhead and must not inflate delivery-team salary even if listed.
    - Corporate / Shared Services: all primary members (overhead pool).
    - Legacy ``User.team_id`` without a membership row: include only when the user's
      role is a fixed-resource default (or team is Corporate).
    """
    from app.core.fixed_resource_eligibility import (
        default_is_billable_headcount_for_user,
        role_is_fixed_resource_default,
    )
    from app.core.permissions import get_role_name
    from app.db.phase28_team_member_billable_schema_sync import is_corporate_team

    team = db.get(Team, team_id)
    corporate = is_corporate_team(team)
    ids: set[UUID] = set()
    members = db.scalars(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.is_primary.is_(True),
        )
    ).all()
    for member in members:
        if corporate or bool(getattr(member, "is_billable_headcount", True)):
            ids.add(member.user_id)

    member_user_ids = {
        row
        for row in db.scalars(
            select(TeamMember.user_id).where(TeamMember.team_id == team_id)
        ).all()
    }
    legacy = db.scalars(
        select(User).where(User.team_id == team_id, User.is_active.is_(True))
    ).all()
    for user in legacy:
        if user.id in member_user_ids:
            continue
        if corporate or role_is_fixed_resource_default(get_role_name(db, user)):
            ids.add(user.id)
        elif default_is_billable_headcount_for_user(db, team=team, user=user):
            ids.add(user.id)
    return ids


def _quote_revenue_cost(
    db: Session, *, team_id: UUID | None
) -> tuple[Decimal, Decimal]:
    """Sum current revision INR for active quotes (all company or one team)."""
    from app.models.finance import Quote

    if team_id is None:
        revenue = _d(
            db.scalar(select(func.coalesce(func.sum(QuoteRevision.base_quoted_revenue_inr), 0)))
        )
        cost = _d(
            db.scalar(select(func.coalesce(func.sum(QuoteRevision.base_estimated_cost_inr), 0)))
        )
        return revenue, cost

    quotes = db.scalars(
        select(Quote).where(Quote.is_active.is_(True), Quote.team_id == team_id)
    ).all()
    revenue = Decimal("0.00")
    cost = Decimal("0.00")
    for quote in quotes:
        rev = db.scalar(
            select(QuoteRevision)
            .where(
                QuoteRevision.quote_id == quote.id,
                QuoteRevision.version == quote.current_version,
                QuoteRevision.revision == quote.current_revision,
            )
            .limit(1)
        )
        if rev is None:
            rev = db.scalar(
                select(QuoteRevision)
                .where(QuoteRevision.quote_id == quote.id)
                .order_by(QuoteRevision.version.desc())
                .limit(1)
            )
        if rev is None:
            continue
        revenue += _d(rev.base_quoted_revenue_inr)
        cost += _d(rev.base_estimated_cost_inr)
    return revenue, cost


def _salary_for_users(db: Session, user_ids: set[UUID] | None) -> Decimal:
    stmt = (
        select(func.coalesce(func.sum(EmployeeCostProfile.base_monthly_salary_inr), 0))
        .select_from(EmployeeCostProfile)
        .join(User, User.id == EmployeeCostProfile.user_id)
        .where(
            EmployeeCostProfile.is_active.is_(True),
            User.requires_salary.is_(True),
            User.is_active.is_(True),
        )
    )
    if user_ids is not None:
        if not user_ids:
            return Decimal("0.00")
        stmt = stmt.where(EmployeeCostProfile.user_id.in_(user_ids))
    return _d(db.scalar(stmt))


def _expense_sum(
    db: Session,
    *,
    team_id: UUID | None,
    paid_by: ExpensePaidBy | None = None,
    nature: CostNature | None = None,
    fy_start: date | None = None,
) -> Decimal:
    from app.services.finance.annual_plan_service import current_fy_start

    stmt = select(func.coalesce(func.sum(Expense.base_amount_inr), 0)).where(Expense.is_active.is_(True))
    start = fy_start if fy_start is not None else current_fy_start()
    stmt = stmt.where(Expense.purchase_date.is_not(None), Expense.purchase_date >= start)
    if team_id is not None:
        stmt = stmt.where(Expense.team_id == team_id)
    if paid_by is not None:
        stmt = stmt.where(Expense.paid_by == paid_by)
    if nature is not None:
        stmt = stmt.where(Expense.nature == nature)
    return _d(db.scalar(stmt))


def _team_fee_monthly(db: Session, *, team_id: UUID | None, today: date) -> Decimal:
    from app.models.enums import WorkingModelCode
    from app.models.models import WorkingModel
    from app.services.finance.commercial_fee_rules import uses_flat_customer_fee

    stmt = select(TeamCommercialTerms).where(TeamCommercialTerms.is_active.is_(True))
    if team_id is not None:
        stmt = stmt.where(TeamCommercialTerms.team_id == team_id)
    total = Decimal("0.00")
    for term in db.scalars(stmt).all():
        if term.effective_from and term.effective_from > today:
            continue
        if term.effective_to and term.effective_to < today:
            continue
        model = db.get(WorkingModel, term.working_model_id)
        strategy = model.strategy_key if model is not None else None
        if not uses_flat_customer_fee(strategy):
            continue
        rate = _d(term.base_fee_inr)
        if strategy == WorkingModelCode.retainer or (
            hasattr(strategy, "value") and strategy.value == WorkingModelCode.retainer.value
        ):
            from app.services.finance.billable_headcount import billable_salary_headcount

            count = billable_salary_headcount(db, term.team_id)
            rate = rate * Decimal(count)
        total += _normalize_monthly_fee(rate, term.billing_period)
    return total


def _team_rollups(db: Session, team: Team, *, today: date, quote_revenue_share: Decimal) -> dict:
    user_ids = _user_ids_for_team(db, team.id)
    salary = _salary_for_users(db, user_ids)
    prosohm_opex = _expense_sum(
        db, team_id=team.id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.opex
    )
    pass_through = _expense_sum(
        db, team_id=team.id, paid_by=ExpensePaidBy.customer, nature=CostNature.opex
    )
    fee = _team_fee_monthly(db, team_id=team.id, today=today)
    operating = prosohm_opex + salary
    return {
        "team_id": str(team.id),
        "team_name": team.name,
        "salary_cost_inr": salary,
        "prosohm_opex_inr": prosohm_opex,
        "pass_through_opex_inr": pass_through,
        "monthly_operating_cost_inr": operating,
        "team_commercial_fee_monthly_inr": fee,
        "planning_revenue_signal_inr": quote_revenue_share + fee,
    }


def get_finance_dashboard(db: Session, *, team_id: UUID | None = None) -> dict:
    from app.services.finance.annual_plan_service import current_fy_label, current_fy_start

    base = get_base_currency(db)
    today = date.today()
    fy_start = current_fy_start(today)
    fy_label = current_fy_label(today)
    revenue, estimated_cost = _quote_revenue_cost(db, team_id=team_id)

    user_ids = _user_ids_for_team(db, team_id) if team_id else None
    salary_cost = _salary_for_users(db, user_ids)
    prosohm_opex = _expense_sum(
        db, team_id=team_id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.opex
    )
    pass_through_opex = _expense_sum(
        db, team_id=team_id, paid_by=ExpensePaidBy.customer, nature=CostNature.opex
    )
    capex = _expense_sum(
        db, team_id=team_id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.capex
    )
    team_fee_monthly = _team_fee_monthly(db, team_id=team_id, today=today)

    planning_revenue = revenue + team_fee_monthly
    operating_cost = prosohm_opex + salary_cost
    display_revenue = revenue + team_fee_monthly
    gross_profit = display_revenue - estimated_cost
    gross_margin = (
        (gross_profit / display_revenue * 100) if display_revenue else Decimal("0.00")
    )
    net_profit = display_revenue - estimated_cost - operating_cost
    net_base = display_revenue
    net_margin = (net_profit / net_base * 100) if net_base else Decimal("0.00")

    budget_stmt = select(func.coalesce(func.sum(Budget.base_allocated_inr), 0)).where(Budget.is_active.is_(True))
    spent_stmt = select(func.coalesce(func.sum(Budget.base_spent_inr), 0)).where(Budget.is_active.is_(True))
    if team_id is not None:
        from app.models.enums import BudgetScopeType

        budget_stmt = budget_stmt.where(
            Budget.scope_type == BudgetScopeType.team,
            Budget.scope_id == team_id,
        )
        spent_stmt = spent_stmt.where(
            Budget.scope_type == BudgetScopeType.team,
            Budget.scope_id == team_id,
        )
    budget_allocated = _d(db.scalar(budget_stmt))
    budget_spent = _d(db.scalar(spent_stmt))
    approved_budgets = int(
        db.scalar(
            select(func.count())
            .select_from(Budget)
            .where(Budget.approval_status == BudgetApprovalStatus.approved)
        )
        or 0
    )

    quoted_hours = _d(
        db.scalar(select(func.coalesce(func.sum(Project.quoted_hours), 0)).where(Project.is_deleted.is_(False)))
    )
    actual_hours = _d(
        db.scalar(select(func.coalesce(func.sum(Project.actual_hours), 0)).where(Project.is_deleted.is_(False)))
    )
    recovery = (actual_hours / quoted_hours * 100) if quoted_hours else Decimal("0.00")

    snapshots = db.scalars(select(ProjectFinancialSnapshot).limit(25)).all()
    placeholders = db.scalars(
        select(AiForecastPlaceholder).where(AiForecastPlaceholder.is_active.is_(True))
    ).all()

    renewals = []
    for expense in list_upcoming_renewals(db, today=today, team_id=team_id):
        days_until = (expense.next_renewal_date - today).days  # type: ignore[operator]
        team_name = None
        if expense.team_id:
            team = db.get(Team, expense.team_id)
            team_name = team.name if team else None
        renewals.append(
            {
                "expense_id": expense.id,
                "name": expense.name,
                "vendor_name": expense.vendor_name,
                "paid_by": expense.paid_by,
                "next_renewal_date": expense.next_renewal_date,
                "notify_before_days": expense.notify_before_days,
                "amount": expense.amount,
                "currency_code": expense.currency_code,
                "base_amount_inr": expense.base_amount_inr,
                "days_until": days_until,
                "team_id": expense.team_id,
                "team_name": team_name,
            }
        )

    by_team: list[dict] = []
    if team_id is None:
        teams = db.scalars(select(Team).where(Team.is_active.is_(True)).order_by(Team.name)).all()
        for team in teams:
            team_quote, _ = _quote_revenue_cost(db, team_id=team.id)
            by_team.append(
                _team_rollups(db, team, today=today, quote_revenue_share=team_quote)
            )

    selected_team_name = None
    if team_id is not None:
        selected = db.get(Team, team_id)
        selected_team_name = selected.name if selected else None

    return {
        "base_currency": base,
        "selected_team_id": str(team_id) if team_id else None,
        "selected_team_name": selected_team_name,
        "planning_fy_start": fy_start.isoformat(),
        "planning_fy_label": fy_label,
        "revenue": {
            "monthly_revenue": display_revenue,
            "quarterly_revenue": display_revenue,
            "yearly_revenue": display_revenue,
            "revenue_forecast": display_revenue,
            "customer_revenue": revenue,
            "business_model_revenue": team_fee_monthly,
            "quote_revenue": revenue,
            "team_commercial_fee_monthly": team_fee_monthly,
        },
        "cost": {
            "salary_cost": salary_cost,
            "software_cost": Decimal("0.00"),
            "infrastructure_cost": Decimal("0.00"),
            "travel": Decimal("0.00"),
            "training": Decimal("0.00"),
            "capex": capex,
            "recurring_costs": prosohm_opex,
            "monthly_operating_cost": operating_cost,
            "annual_operating_cost": operating_cost * Decimal("12"),
            "prosohm_opex": prosohm_opex,
            "pass_through_opex": pass_through_opex,
        },
        "profitability": {
            "gross_profit": gross_profit,
            "gross_margin": gross_margin.quantize(Decimal("0.01")),
            "net_margin": net_margin.quantize(Decimal("0.01")),
            "recovery_percent": recovery.quantize(Decimal("0.01")),
            "profit_forecast": net_profit,
            "project_margin": gross_margin.quantize(Decimal("0.01")),
            "customer_margin": gross_margin.quantize(Decimal("0.01")),
            "engineering_margin": gross_margin.quantize(Decimal("0.01")),
        },
        "budget": {
            "budget_allocated": budget_allocated,
            "budget_consumed": budget_spent,
            "remaining_budget": budget_allocated - budget_spent,
            "budget_forecast": budget_allocated,
            "budget_variance": budget_allocated - budget_spent,
            "department_budget": budget_allocated,
            "customer_budget": budget_allocated,
            "approved_budgets": approved_budgets,
        },
        "productivity": {
            "quoted_hours": quoted_hours,
            "actual_hours": actual_hours,
            "billable_hours": actual_hours,
            "non_billable_hours": Decimal("0.00"),
            "recovery_rate": recovery.quantize(Decimal("0.01")),
            "average_hourly_cost": (
                (estimated_cost / quoted_hours).quantize(Decimal("0.01"))
                if quoted_hours
                else Decimal("0.00")
            ),
            "average_hourly_revenue": (
                ((revenue + team_fee_monthly) / quoted_hours).quantize(Decimal("0.01"))
                if quoted_hours
                else Decimal("0.00")
            ),
            "engineering_productivity": recovery.quantize(Decimal("0.01")),
        },
        "project_snapshots": [
            {
                "project_id": str(row.project_id),
                "quoted_hours": row.quoted_hours,
                "actual_hours": row.actual_hours,
                "revenue": row.revenue,
                "gross_profit": row.gross_profit,
                "recovery_percent": row.recovery_percent,
                "profitability_percent": row.profitability_percent,
                "currency_code": row.currency_code,
                "base_revenue_inr": row.base_revenue_inr,
            }
            for row in snapshots
        ],
        "ai_placeholders": [
            {
                "id": str(row.id),
                "kind": row.kind.value,
                "title": row.title,
                "description": row.description,
            }
            for row in placeholders
        ],
        "upcoming_renewals": renewals,
        "team_commercial_fee_monthly_inr": team_fee_monthly,
        "pass_through_opex_inr": pass_through_opex,
        "salary_cost_inr": salary_cost,
        "by_team": by_team,
    }
