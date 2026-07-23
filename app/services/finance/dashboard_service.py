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
from app.models.models import Customer, Project, Stream, Team, TeamMember, User
from app.services.finance.billable_headcount import (
    billable_salary_headcount,
    company_delivery_billable_salary_headcount,
)
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
    - Corporate / Management: all primary (or sole-home) members (overhead pool).
    - Members with **no primary team anywhere** still count on a team they work on
      (primary is optional in Admin — otherwise People costs never hit P&L).
    - Legacy ``User.team_id`` without a membership row: include only when the user's
      role is a fixed-resource default (or team is the overhead home).
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

    members = db.scalars(select(TeamMember).where(TeamMember.team_id == team_id)).all()
    member_user_ids = {member.user_id for member in members}
    users_with_any_primary = set(
        db.scalars(
            select(TeamMember.user_id).where(TeamMember.is_primary.is_(True))
        ).all()
    )

    for member in members:
        if not (corporate or bool(getattr(member, "is_billable_headcount", True))):
            continue
        if member.is_primary or member.user_id not in users_with_any_primary:
            ids.add(member.user_id)

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


def _current_quote_revision(db: Session, quote) -> QuoteRevision | None:
    current = db.scalar(
        select(QuoteRevision)
        .where(
            QuoteRevision.quote_id == quote.id,
            QuoteRevision.version == quote.current_version,
            QuoteRevision.revision == quote.current_revision,
        )
        .limit(1)
    )
    if current is not None:
        return current
    return db.scalar(
        select(QuoteRevision)
        .where(QuoteRevision.quote_id == quote.id)
        .order_by(QuoteRevision.version.desc())
        .limit(1)
    )


def _quote_period_amounts(
    db: Session,
    *,
    team_id: UUID | None,
    today: date,
    fy_start: date,
) -> tuple[Decimal, Decimal]:
    """Actual quote awards: this calendar month + current FY quarter (by invoiced_date)."""
    from app.models.finance import Quote
    from app.services.finance.plan_sales_from_quotes_service import effective_revenue_date
    from app.services.finance.renewal_budget_service import fy_quarter_date_bounds

    bounds = fy_quarter_date_bounds(today, fy_start=fy_start)
    q_start, q_end = bounds if bounds is not None else (None, None)

    quote_stmt = select(Quote).where(Quote.is_active.is_(True))
    if team_id is not None:
        quote_stmt = quote_stmt.where(Quote.team_id == team_id)

    monthly = Decimal("0.00")
    quarterly = Decimal("0.00")
    for quote in db.scalars(quote_stmt).all():
        revision = _current_quote_revision(db, quote)
        when = effective_revenue_date(quote)
        if when is None or revision is None:
            continue
        amount = _d(revision.base_quoted_revenue_inr)
        if when.year == today.year and when.month == today.month:
            monthly += amount
        if q_start is not None and q_end is not None and q_start <= when <= q_end:
            quarterly += amount
    return monthly.quantize(Decimal("0.01")), quarterly.quantize(Decimal("0.01"))


def _retainer_fee_for_period(
    db: Session,
    *,
    team_id: UUID | None,
    today: date,
    fy_start: date,
) -> tuple[Decimal, Decimal]:
    """Fixed/retainer fees: monthly rate, and actual accrued for months elapsed in quarter."""
    from app.services.finance.renewal_budget_service import (
        fy_quarter_date_bounds,
        months_elapsed_in_period,
    )

    monthly = _team_fee_monthly(db, team_id=team_id, today=today)
    bounds = fy_quarter_date_bounds(today, fy_start=fy_start)
    if bounds is None or monthly <= 0:
        return monthly, Decimal("0.00")
    q_start, q_end = bounds
    months = months_elapsed_in_period(today, q_start, q_end)
    return monthly, (monthly * Decimal(months)).quantize(Decimal("0.01"))


def _revenue_by_customer(
    db: Session, *, team_id: UUID | None, today: date | None = None, fy_start: date | None = None
) -> list[dict]:
    """Group actual awarded quote revenue by customer (month + FY quarter by invoiced_date)."""
    from app.models.finance import Quote
    from app.services.finance.annual_plan_service import current_fy_start
    from app.services.finance.plan_sales_from_quotes_service import effective_revenue_date
    from app.services.finance.renewal_budget_service import fy_quarter_date_bounds

    today = today or date.today()
    fy_start = fy_start or current_fy_start(today)
    bounds = fy_quarter_date_bounds(today, fy_start=fy_start)
    q_start, q_end = bounds if bounds is not None else (None, None)

    quote_stmt = select(Quote).where(Quote.is_active.is_(True))
    if team_id is not None:
        quote_stmt = quote_stmt.where(Quote.team_id == team_id)
    quotes = db.scalars(quote_stmt.order_by(Quote.tool_number)).all()

    grouped: dict[UUID, dict] = {}
    for quote in quotes:
        current = _current_quote_revision(db, quote)
        if current is None:
            continue
        when = effective_revenue_date(quote)
        if when is None:
            continue
        in_month = when.year == today.year and when.month == today.month
        in_quarter = q_start is not None and q_end is not None and q_start <= when <= q_end
        if not in_month and not in_quarter:
            continue

        customer = db.get(Customer, quote.customer_id)
        row = grouped.setdefault(
            quote.customer_id,
            {
                "key": str(quote.customer_id),
                "label": customer.name if customer is not None else str(quote.customer_id),
                "monthly_revenue_inr": Decimal("0.00"),
                "quarterly_revenue_inr": Decimal("0.00"),
                "quote_count": 0,
                "project_ids": set(),
            },
        )
        amount = _d(current.base_quoted_revenue_inr)
        if in_month:
            row["monthly_revenue_inr"] += amount
        if in_quarter:
            row["quarterly_revenue_inr"] += amount
            row["quote_count"] += 1
            if quote.project_id is not None:
                row["project_ids"].add(str(quote.project_id))

    rows: list[dict] = []
    for row in grouped.values():
        rows.append(
            {
                "key": row["key"],
                "label": row["label"],
                "monthly_revenue_inr": _d(row["monthly_revenue_inr"]),
                "quarterly_revenue_inr": _d(row["quarterly_revenue_inr"]),
                "quote_count": int(row["quote_count"]),
                "project_count": len(row["project_ids"]),
            }
        )
    rows.sort(key=lambda item: item["quarterly_revenue_inr"], reverse=True)
    return rows


def _revenue_by_stream(
    db: Session, *, team_id: UUID | None, today: date | None = None, fy_start: date | None = None
) -> list[dict]:
    """Group actual awarded quote revenue by stream (month + FY quarter by invoiced_date)."""
    from app.models.finance import Quote
    from app.services.finance.annual_plan_service import current_fy_start
    from app.services.finance.plan_sales_from_quotes_service import effective_revenue_date
    from app.services.finance.renewal_budget_service import fy_quarter_date_bounds

    today = today or date.today()
    fy_start = fy_start or current_fy_start(today)
    bounds = fy_quarter_date_bounds(today, fy_start=fy_start)
    q_start, q_end = bounds if bounds is not None else (None, None)

    quote_stmt = select(Quote).where(Quote.is_active.is_(True))
    if team_id is not None:
        quote_stmt = quote_stmt.where(Quote.team_id == team_id)
    quotes = db.scalars(quote_stmt.order_by(Quote.tool_number)).all()

    grouped: dict[str, dict] = {}
    for quote in quotes:
        current = _current_quote_revision(db, quote)
        if current is None:
            continue
        when = effective_revenue_date(quote)
        if when is None:
            continue
        in_month = when.year == today.year and when.month == today.month
        in_quarter = q_start is not None and q_end is not None and q_start <= when <= q_end
        if not in_month and not in_quarter:
            continue

        project = db.get(Project, quote.project_id) if quote.project_id is not None else None
        stream = (
            db.get(Stream, project.stream_id)
            if project and project.stream_id is not None
            else None
        )
        key = str(stream.id) if stream is not None else "unassigned"
        label = stream.name if stream is not None else "Unassigned stream"
        row = grouped.setdefault(
            key,
            {
                "key": key,
                "label": label,
                "monthly_revenue_inr": Decimal("0.00"),
                "quarterly_revenue_inr": Decimal("0.00"),
                "quote_count": 0,
                "project_ids": set(),
            },
        )
        amount = _d(current.base_quoted_revenue_inr)
        if in_month:
            row["monthly_revenue_inr"] += amount
        if in_quarter:
            row["quarterly_revenue_inr"] += amount
            row["quote_count"] += 1
            if quote.project_id is not None:
                row["project_ids"].add(str(quote.project_id))

    rows: list[dict] = []
    for row in grouped.values():
        rows.append(
            {
                "key": row["key"],
                "label": row["label"],
                "monthly_revenue_inr": _d(row["monthly_revenue_inr"]),
                "quarterly_revenue_inr": _d(row["quarterly_revenue_inr"]),
                "quote_count": int(row["quote_count"]),
                "project_count": len(row["project_ids"]),
            }
        )
    rows.sort(key=lambda item: item["quarterly_revenue_inr"], reverse=True)
    return rows


def _salary_for_users(
    db: Session, user_ids: set[UUID] | None, *, as_of: date | None = None
) -> Decimal:
    from app.services.finance.employment_cost import employment_salary_factor

    ref = as_of or date.today()
    stmt = (
        select(EmployeeCostProfile, User)
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
    total = Decimal("0.00")
    for profile, user in db.execute(stmt).all():
        factor = employment_salary_factor(user, as_of=ref)
        if factor <= 0:
            continue
        total += _d(profile.base_monthly_salary_inr) * factor
    return total.quantize(Decimal("0.01"))


def _salary_for_team(db: Session, team_id: UUID, *, as_of: date | None = None) -> Decimal:
    """Team-scoped salary for net profit / operating cost.

    Uses the billable∩home roster from ``_user_ids_for_team``, then prorates with
    primary-home periods (or full employment factor for sole-home members).
    """
    from app.services.finance.employment_cost import (
        employment_salary_factor,
        primary_team_salary_factor,
    )

    ref = as_of or date.today()
    eligible = _user_ids_for_team(db, team_id)
    if not eligible:
        return Decimal("0.00")

    stmt = (
        select(EmployeeCostProfile, User)
        .join(User, User.id == EmployeeCostProfile.user_id)
        .where(
            EmployeeCostProfile.is_active.is_(True),
            User.requires_salary.is_(True),
            User.is_active.is_(True),
            EmployeeCostProfile.user_id.in_(eligible),
        )
    )
    total = Decimal("0.00")
    for profile, user in db.execute(stmt).all():
        factor = primary_team_salary_factor(
            db, user_id=user.id, team_id=team_id, as_of=ref
        )
        if factor <= 0:
            # Sole-home / non-primary membership still in eligible set.
            factor = employment_salary_factor(user, as_of=ref)
        if factor <= 0:
            continue
        total += _d(profile.base_monthly_salary_inr) * factor
    return total.quantize(Decimal("0.01"))


def _user_ids_with_team_salary(
    db: Session, team_id: UUID, *, as_of: date | None = None
) -> set[UUID]:
    """Users whose salary contributes to this team's operating cost on as_of."""
    from app.services.finance.employment_cost import (
        employment_salary_factor,
        primary_team_salary_factor,
    )

    ref = as_of or date.today()
    eligible = _user_ids_for_team(db, team_id)
    ids: set[UUID] = set()
    for user_id in eligible:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            continue
        factor = primary_team_salary_factor(
            db, user_id=user_id, team_id=team_id, as_of=ref
        )
        if factor <= 0:
            factor = employment_salary_factor(user, as_of=ref)
        if factor > 0:
            ids.add(user_id)
    return ids


def _expense_monthly_amount(expense: Expense) -> Decimal:
    """Convert stored amount to a monthly signal using expense frequency."""
    from app.models.enums import CostFrequency

    amount = _d(expense.base_amount_inr)
    freq = expense.frequency
    if freq == CostFrequency.monthly or freq == CostFrequency.recurring:
        return amount
    if freq == CostFrequency.quarterly:
        return (amount / Decimal("3")).quantize(Decimal("0.01"))
    if freq == CostFrequency.yearly:
        return (amount / Decimal("12")).quantize(Decimal("0.01"))
    # one_time: full amount in months it remains active (FY purchase signal)
    return amount


def _expense_sum(
    db: Session,
    *,
    team_id: UUID | None,
    paid_by: ExpensePaidBy | None = None,
    nature: CostNature | None = None,
    fy_start: date | None = None,
    as_of: date | None = None,
) -> Decimal:
    from app.services.finance.annual_plan_service import current_fy_start
    from app.services.finance.employment_cost import expense_month_factor

    ref = as_of or date.today()
    stmt = select(Expense).where(Expense.is_active.is_(True))
    start = fy_start if fy_start is not None else current_fy_start()
    stmt = stmt.where(Expense.purchase_date.is_not(None), Expense.purchase_date >= start)
    if team_id is not None:
        stmt = stmt.where(Expense.team_id == team_id)
    if paid_by is not None:
        stmt = stmt.where(Expense.paid_by == paid_by)
    if nature is not None:
        stmt = stmt.where(Expense.nature == nature)
    total = Decimal("0.00")
    for expense in db.scalars(stmt).all():
        factor = expense_month_factor(expense, as_of=ref)
        if factor <= 0:
            continue
        total += _expense_monthly_amount(expense) * factor
    return total.quantize(Decimal("0.01"))


def _team_fee_monthly(db: Session, *, team_id: UUID | None, today: date) -> Decimal:
    from app.services.finance.retainer_fee import team_retainer_fee_monthly

    return team_retainer_fee_monthly(db, team_id=team_id, as_of=today)


def _team_rollups(
    db: Session,
    team: Team,
    *,
    today: date,
    quote_revenue: Decimal,
    quote_estimated_cost: Decimal,
) -> dict:
    from app.db.phase28_team_member_billable_schema_sync import is_corporate_team

    salary = _salary_for_team(db, team.id, as_of=today)
    prosohm_opex = _expense_sum(
        db, team_id=team.id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.opex
    )
    prosohm_capex = _expense_sum(
        db, team_id=team.id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.capex
    )
    pass_through = _expense_sum(
        db, team_id=team.id, paid_by=ExpensePaidBy.customer, nature=CostNature.opex
    )
    fee = _team_fee_monthly(db, team_id=team.id, today=today)
    from app.services.finance.annual_plan_service import current_fy_start
    from app.services.finance.renewal_budget_service import (
        fy_quarter_date_bounds,
        months_elapsed_in_period,
    )

    fy_start = current_fy_start(today)
    quote_month, quote_quarter = _quote_period_amounts(
        db, team_id=team.id, today=today, fy_start=fy_start
    )
    bounds = fy_quarter_date_bounds(today, fy_start=fy_start)
    fee_months = (
        months_elapsed_in_period(today, bounds[0], bounds[1]) if bounds is not None else 0
    )
    fee_quarter = (fee * Decimal(fee_months)).quantize(Decimal("0.01"))
    # Fully loaded team cost: salaries + software/OpEx + hardware CapEx assigned to the team.
    operating = prosohm_opex + salary + prosohm_capex
    revenue = quote_revenue + fee
    period_quarter_revenue = (quote_quarter + fee_quarter).quantize(Decimal("0.01"))
    gross_profit = revenue - quote_estimated_cost
    net_profit = gross_profit - operating
    gross_margin = (
        (gross_profit / revenue * Decimal("100")).quantize(Decimal("0.01"))
        if revenue > 0
        else Decimal("0.00")
    )
    net_margin = (
        (net_profit / revenue * Decimal("100")).quantize(Decimal("0.01"))
        if revenue > 0
        else Decimal("0.00")
    )
    return {
        "team_id": str(team.id),
        "team_name": team.name,
        "is_overhead_home": is_corporate_team(team),
        "salary_cost_inr": salary,
        "prosohm_opex_inr": prosohm_opex,
        "prosohm_capex_inr": prosohm_capex,
        "pass_through_opex_inr": pass_through,
        "monthly_operating_cost_inr": operating,
        "team_commercial_fee_monthly_inr": fee,
        "quote_revenue_inr": quote_revenue,
        "estimated_cost_inr": quote_estimated_cost,
        "planning_revenue_signal_inr": revenue,
        "gross_profit_inr": gross_profit.quantize(Decimal("0.01")),
        "net_profit_inr": net_profit.quantize(Decimal("0.01")),
        "gross_margin_percent": gross_margin,
        "net_margin_percent": net_margin,
        "quarterly_revenue_signal_inr": period_quarter_revenue,
        "quarter_quote_awards_inr": quote_quarter,
        "quarter_retainer_accrued_inr": fee_quarter,
        "month_quote_awards_inr": quote_month,
    }


def _overhead_metrics(
    db: Session, *, fy_start: date, team_id: UUID | None = None
) -> dict:
    """Corporate / Management overhead pool ÷ delivery billable FTE (analytical CPR)."""
    from app.db.phase23_finance_team_scope_schema_sync import (
        ensure_corporate_shared_services_team,
    )
    from app.db.phase28_team_member_billable_schema_sync import is_corporate_team

    as_of = date.today()
    home = ensure_corporate_shared_services_team(db)

    overhead_salary = _salary_for_team(db, home.id, as_of=as_of).quantize(Decimal("0.01"))
    overhead_opex = _expense_sum(
        db,
        team_id=home.id,
        paid_by=ExpensePaidBy.prosohm,
        nature=CostNature.opex,
        fy_start=fy_start,
        as_of=as_of,
    ).quantize(Decimal("0.01"))
    pool = (overhead_salary + overhead_opex).quantize(Decimal("0.01"))
    n = company_delivery_billable_salary_headcount(db, as_of=as_of)
    cpr = (pool / Decimal(n)).quantize(Decimal("0.01")) if n else Decimal("0.00")

    team_n = 0
    allocated = Decimal("0.00")
    if team_id is not None:
        team = db.get(Team, team_id)
        if team is not None and not is_corporate_team(team):
            team_n = billable_salary_headcount(db, team_id, as_of=as_of)
            allocated = (cpr * Decimal(team_n)).quantize(Decimal("0.01"))

    return {
        # Compat: management_* mirrors corporate_* (single overhead home).
        "corporate_team_id": str(home.id),
        "corporate_team_name": home.name,
        "management_team_id": str(home.id),
        "management_team_name": home.name,
        "overhead_salary_inr": overhead_salary,
        "overhead_management_salary_inr": overhead_salary,
        "overhead_corporate_salary_inr": Decimal("0.00"),
        "overhead_opex_inr": overhead_opex,
        "overhead_pool_monthly_inr": pool,
        "billable_resource_count": n,
        "overhead_cost_per_resource_inr": cpr,
        "team_billable_resource_count": team_n,
        "allocated_overhead_for_filter_inr": allocated,
    }


def get_finance_dashboard(db: Session, *, team_id: UUID | None = None) -> dict:
    from app.services.finance.annual_plan_service import current_fy_label, current_fy_start

    base = get_base_currency(db)
    today = date.today()
    fy_start = current_fy_start(today)
    fy_label = current_fy_label(today)
    revenue, estimated_cost = _quote_revenue_cost(db, team_id=team_id)

    as_of = today
    if team_id is not None:
        salary_cost = _salary_for_team(db, team_id, as_of=as_of)
    else:
        salary_cost = _salary_for_users(db, None, as_of=as_of)
    prosohm_opex = _expense_sum(
        db, team_id=team_id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.opex, as_of=as_of
    )
    pass_through_opex = _expense_sum(
        db, team_id=team_id, paid_by=ExpensePaidBy.customer, nature=CostNature.opex, as_of=as_of
    )
    capex = _expense_sum(
        db, team_id=team_id, paid_by=ExpensePaidBy.prosohm, nature=CostNature.capex, as_of=as_of
    )
    team_fee_monthly = _team_fee_monthly(db, team_id=team_id, today=today)
    quote_month, quote_quarter = _quote_period_amounts(
        db, team_id=team_id, today=today, fy_start=fy_start
    )
    _, fee_quarter = _retainer_fee_for_period(
        db, team_id=team_id, today=today, fy_start=fy_start
    )

    planning_revenue = revenue + team_fee_monthly
    operating_cost = prosohm_opex + salary_cost + capex
    display_revenue = revenue + team_fee_monthly
    # Actual period revenue: quote awards in period + retainer accrued (not ×3 projection)
    period_monthly_revenue = (quote_month + team_fee_monthly).quantize(Decimal("0.01"))
    quarterly_revenue = (quote_quarter + fee_quarter).quantize(Decimal("0.01"))
    yearly_revenue = (display_revenue * Decimal("12")).quantize(Decimal("0.01"))
    quarterly_operating = (operating_cost * Decimal("3")).quantize(Decimal("0.01"))
    yearly_operating = (operating_cost * Decimal("12")).quantize(Decimal("0.01"))
    quarterly_salary = (salary_cost * Decimal("3")).quantize(Decimal("0.01"))
    gross_profit = display_revenue - estimated_cost
    gross_margin = (
        (gross_profit / display_revenue * 100) if display_revenue else Decimal("0.00")
    )
    net_profit = display_revenue - estimated_cost - operating_cost
    net_base = display_revenue
    net_margin = (net_profit / net_base * 100) if net_base else Decimal("0.00")

    from app.services.finance.renewal_budget_service import renewals_by_quarter_inr

    renewals_q = renewals_by_quarter_inr(db, fy_start=fy_start, team_id=team_id)
    renewals_fy = sum(renewals_q.values(), Decimal("0.00"))

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
    revenue_by_customer = _revenue_by_customer(
        db, team_id=team_id, today=today, fy_start=fy_start
    )
    revenue_by_stream = _revenue_by_stream(
        db, team_id=team_id, today=today, fy_start=fy_start
    )
    if team_id is None:
        teams = db.scalars(select(Team).where(Team.is_active.is_(True)).order_by(Team.name)).all()
        for team in teams:
            team_quote, team_est = _quote_revenue_cost(db, team_id=team.id)
            by_team.append(
                _team_rollups(
                    db,
                    team,
                    today=today,
                    quote_revenue=team_quote,
                    quote_estimated_cost=team_est,
                )
            )

    selected_team_name = None
    if team_id is not None:
        selected = db.get(Team, team_id)
        selected_team_name = selected.name if selected else None

    overhead = _overhead_metrics(db, fy_start=fy_start, team_id=team_id)

    return {
        "base_currency": base,
        "selected_team_id": str(team_id) if team_id else None,
        "selected_team_name": selected_team_name,
        "planning_fy_start": fy_start.isoformat(),
        "planning_fy_label": fy_label,
        "overhead": overhead,
        "revenue": {
            "monthly_revenue": period_monthly_revenue,
            "quarterly_revenue": quarterly_revenue,
            "yearly_revenue": yearly_revenue,
            "quote_pipeline_revenue": display_revenue,
            "revenue_forecast": yearly_revenue,
            "customer_revenue": revenue,
            "business_model_revenue": team_fee_monthly,
            "quote_revenue": revenue,
            "team_commercial_fee_monthly": team_fee_monthly,
            "team_commercial_fee_quarterly": (team_fee_monthly * Decimal("3")).quantize(
                Decimal("0.01")
            ),
        },
        "cost": {
            "salary_cost": salary_cost,
            "salary_cost_quarterly": quarterly_salary,
            "software_cost": Decimal("0.00"),
            "infrastructure_cost": Decimal("0.00"),
            "travel": Decimal("0.00"),
            "training": Decimal("0.00"),
            "capex": capex,
            "recurring_costs": prosohm_opex,
            "monthly_operating_cost": operating_cost,
            "quarterly_operating_cost": quarterly_operating,
            "annual_operating_cost": yearly_operating,
            "prosohm_opex": prosohm_opex,
            "pass_through_opex": pass_through_opex,
            "known_renewals_fy_inr": renewals_fy,
            "known_renewals_by_quarter": {k: str(v) for k, v in renewals_q.items()},
            "overhead_pool_monthly_inr": overhead["overhead_pool_monthly_inr"],
            "overhead_cost_per_resource_inr": overhead["overhead_cost_per_resource_inr"],
            "billable_resource_count": overhead["billable_resource_count"],
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
        "revenue_by_customer": revenue_by_customer,
        "revenue_by_stream": revenue_by_stream,
    }
