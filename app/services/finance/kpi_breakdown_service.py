"""KPI card drill-down: ranked composition of finance dashboard totals."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import CostNature, ExpensePaidBy
from app.models.finance import CostCentre, EmployeeCostProfile, Expense
from app.models.models import Team, User
from app.services.finance.annual_plan_service import current_fy_start
from app.services.finance.billable_headcount import company_delivery_billable_salary_headcount
from app.services.finance.dashboard_service import (
    _expense_monthly_amount,
    _expense_sum,
    _overhead_metrics,
    _quote_period_amounts,
    _quote_revenue_cost,
    _retainer_fee_for_period,
    _salary_for_team,
    _salary_for_users,
    _team_fee_monthly,
    _user_ids_with_team_salary,
)
from app.services.finance.employment_cost import employment_salary_factor, expense_month_factor
from app.services.finance.fx_service import get_base_currency

# Catalogue centres used for “not spent enough” hints on overhead OpEx.
OPEX_CATALOGUE_CODES = (
    "RENT",
    "UTILITIES",
    "INTERNET",
    "OFFICE",
    "MAINTENANCE",
    "CLOUD",
    "SW_LICENSES",
    "SW_RENEWALS",
    "INSURANCE",
    "TRAINING",
    "TRAVEL",
)

VALID_METRICS = frozenset(
    {
        "operating_cost",
        "overhead_salaries",
        "overhead_opex",
        "overhead_pool",
        "overhead_cpr",
        "team_fees",
        "revenue_quarter",
    }
)


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole <= 0:
        return Decimal("0.00")
    return (part / whole * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _band(
    share_pct: Decimal, *, rank: int, total_lines: int, mode: str = "cost"
) -> str:
    """cost: concentrated spend; revenue: top contributors (never framed as spend)."""
    if mode == "revenue":
        if rank == 1 and share_pct > 0:
            return "leading"
        if share_pct <= Decimal("5"):
            return "thin"
        return "normal"
    if share_pct >= Decimal("20") or (total_lines > 0 and rank <= max(1, total_lines // 4)):
        return "high"
    if share_pct <= Decimal("5"):
        return "thin"
    return "normal"


def _salary_lines(
    db: Session,
    user_ids: set[UUID],
    *,
    as_of: date,
    team_label: str | None = None,
    team_id: UUID | None = None,
) -> list[dict]:
    from app.services.finance.employment_cost import (
        employment_salary_factor,
        primary_team_salary_factor,
    )

    if not user_ids:
        return []
    stmt = (
        select(EmployeeCostProfile, User)
        .join(User, User.id == EmployeeCostProfile.user_id)
        .where(
            EmployeeCostProfile.is_active.is_(True),
            User.requires_salary.is_(True),
            User.is_active.is_(True),
            EmployeeCostProfile.user_id.in_(user_ids),
        )
    )
    rows: list[dict] = []
    for profile, user in db.execute(stmt).all():
        if team_id is not None:
            factor = primary_team_salary_factor(
                db, user_id=user.id, team_id=team_id, as_of=as_of
            )
        else:
            factor = employment_salary_factor(user, as_of=as_of)
        if factor <= 0:
            continue
        amount = _q(_q(profile.base_monthly_salary_inr) * factor)
        if amount <= 0:
            continue
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email or str(user.id)
        rows.append(
            {
                "id": str(user.id),
                "label": name,
                "detail": team_label or "Salary",
                "amount_inr": amount,
                "kind": "salary",
            }
        )
    rows.sort(key=lambda r: r["amount_inr"], reverse=True)
    return rows


def _expense_lines(
    db: Session,
    *,
    team_ids: list[UUID],
    paid_by: ExpensePaidBy,
    nature: CostNature,
    fy_start: date,
    as_of: date,
) -> list[dict]:
    if not team_ids:
        return []
    stmt = select(Expense).where(
        Expense.is_active.is_(True),
        Expense.team_id.in_(team_ids),
        Expense.paid_by == paid_by,
        Expense.nature == nature,
        Expense.purchase_date.is_not(None),
        Expense.purchase_date >= fy_start,
    )
    centres = {
        row.id: row
        for row in db.scalars(select(CostCentre).where(CostCentre.is_active.is_(True))).all()
    }
    teams = {row.id: row for row in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()}
    rows: list[dict] = []
    for expense in db.scalars(stmt).all():
        factor = expense_month_factor(expense, as_of=as_of)
        if factor <= 0:
            continue
        amount = _q(_expense_monthly_amount(expense) * factor)
        if amount <= 0:
            continue
        centre = centres.get(expense.cost_centre_id)
        team = teams.get(expense.team_id) if expense.team_id else None
        code = (centre.code if centre else "") or ""
        freq = expense.frequency
        freq_label = freq.value if hasattr(freq, "value") else str(freq or "")
        rows.append(
            {
                "id": str(expense.id),
                "label": expense.name,
                "detail": " · ".join(
                    p
                    for p in (
                        centre.name if centre else None,
                        code or None,
                        team.name if team else None,
                        freq_label or None,
                    )
                    if p
                ),
                "amount_inr": amount,
                "kind": "expense",
                "category_code": code.upper() or None,
            }
        )
    rows.sort(key=lambda r: r["amount_inr"], reverse=True)
    return rows


def _annotate(
    lines: list[dict], total: Decimal, *, band_mode: str = "cost"
) -> list[dict]:
    out: list[dict] = []
    n = len(lines)
    for index, row in enumerate(lines):
        share = _pct(row["amount_inr"], total)
        out.append(
            {
                **row,
                "share_pct": share,
                "band": _band(
                    share, rank=index + 1, total_lines=n, mode=band_mode
                ),
                "amount_inr": _q(row["amount_inr"]),
            }
        )
    return out


def _empty_category_hints(db: Session, spent_codes: set[str]) -> list[dict]:
    hints: list[dict] = []
    for code in OPEX_CATALOGUE_CODES:
        if code in spent_codes:
            continue
        centre = db.scalar(select(CostCentre).where(CostCentre.code == code))
        if centre is None:
            continue
        hints.append(
            {
                "id": f"empty-{code}",
                "label": centre.name,
                "detail": f"{code} · no Prosohm OpEx booked this FY",
                "amount_inr": Decimal("0.00"),
                "share_pct": Decimal("0.0"),
                "band": "empty",
                "kind": "hint",
                "category_code": code,
            }
        )
    return hints


def get_kpi_breakdown(
    db: Session,
    *,
    metric: str,
    team_id: UUID | None = None,
) -> dict:
    key = (metric or "").strip().lower()
    if key not in VALID_METRICS:
        raise ProTrackValidationError(
            f"Unknown metric '{metric}'. Valid: {', '.join(sorted(VALID_METRICS))}"
        )

    today = date.today()
    fy_start = current_fy_start(today)
    base = get_base_currency(db)
    overhead = _overhead_metrics(db, fy_start=fy_start, team_id=team_id)

    if key == "overhead_salaries":
        from app.db.phase23_finance_team_scope_schema_sync import (
            ensure_corporate_shared_services_team,
        )

        home = ensure_corporate_shared_services_team(db)
        lines = _salary_lines(
            db,
            _user_ids_with_team_salary(db, home.id, as_of=today),
            as_of=today,
            team_label=home.name,
            team_id=home.id,
        )
        lines.sort(key=lambda r: r["amount_inr"], reverse=True)
        total = _q(overhead["overhead_salary_inr"])
        return {
            "metric": key,
            "title": "Corporate / Management salaries",
            "subtitle": "People on the overhead home team (monthly INR, employment-prorated).",
            "total_inr": total,
            "currency_code": base,
            "formula": "Sum of active salary profiles on Corporate / Management",
            "insights": _insights_from_lines(lines, total, subject="salary lines"),
            "groups": [
                {
                    "label": "Salary contributors",
                    "total_inr": total,
                    "lines": _annotate(lines, total),
                }
            ],
            "empty_hints": [],
        }

    if key == "overhead_opex":
        from app.db.phase23_finance_team_scope_schema_sync import (
            ensure_corporate_shared_services_team,
        )

        home = ensure_corporate_shared_services_team(db)
        lines = _expense_lines(
            db,
            team_ids=[home.id],
            paid_by=ExpensePaidBy.prosohm,
            nature=CostNature.opex,
            fy_start=fy_start,
            as_of=today,
        )
        total = _q(overhead["overhead_opex_inr"])
        spent = {str(r.get("category_code") or "") for r in lines if r.get("category_code")}
        empty = _empty_category_hints(db, spent)
        return {
            "metric": key,
            "title": "Overhead OpEx (Prosohm)",
            "subtitle": "Recurring HQ costs on Corporate / Management this FY — ranked high → low.",
            "total_inr": total,
            "currency_code": base,
            "formula": "FY-gated Prosohm OpEx × month factor on Corporate / Management",
            "insights": _insights_from_lines(lines, total, subject="OpEx lines")
            + (
                [f"{len(empty)} catalogue categories have no spend yet"]
                if empty
                else []
            ),
            "groups": [
                {
                    "label": "Expense lines",
                    "total_inr": total,
                    "lines": _annotate(lines, total),
                }
            ],
            "empty_hints": empty,
        }

    if key in {"overhead_pool", "overhead_cpr"}:
        from app.db.phase23_finance_team_scope_schema_sync import (
            ensure_corporate_shared_services_team,
        )

        home = ensure_corporate_shared_services_team(db)
        salary_lines = _salary_lines(
            db,
            _user_ids_with_team_salary(db, home.id, as_of=today),
            as_of=today,
            team_id=home.id,
        )
        opex_lines = _expense_lines(
            db,
            team_ids=[home.id],
            paid_by=ExpensePaidBy.prosohm,
            nature=CostNature.opex,
            fy_start=fy_start,
            as_of=today,
        )
        pool = _q(overhead["overhead_pool_monthly_inr"])
        n = int(overhead["billable_resource_count"] or 0)
        cpr = _q(overhead["overhead_cost_per_resource_inr"])
        salary_total = _q(overhead["overhead_salary_inr"])
        opex_total = _q(overhead["overhead_opex_inr"])
        title = "Overhead pool / month" if key == "overhead_pool" else "Cost per billable resource"
        formula = (
            "Pool = overhead salaries + overhead OpEx"
            if key == "overhead_pool"
            else f"CPR = pool ÷ delivery billable FTE ({n})"
        )
        insights = [
            f"Salaries {salary_total} ({_pct(salary_total, pool)}% of pool)",
            f"OpEx {opex_total} ({_pct(opex_total, pool)}% of pool)",
        ]
        if key == "overhead_cpr":
            insights.append(f"Delivery billable FTE = {n}")
            insights.append(f"CPR = {cpr} {base}")
        return {
            "metric": key,
            "title": title,
            "subtitle": "Composition of the overhead burden rate used in P&L analytics.",
            "total_inr": cpr if key == "overhead_cpr" else pool,
            "currency_code": base,
            "formula": formula,
            "insights": insights,
            "groups": [
                {
                    "label": "Salaries",
                    "total_inr": salary_total,
                    "lines": _annotate(salary_lines[:25], salary_total or Decimal("1")),
                },
                {
                    "label": "OpEx",
                    "total_inr": opex_total,
                    "lines": _annotate(opex_lines[:25], opex_total or Decimal("1")),
                },
            ],
            "empty_hints": [],
            "meta": {
                "pool_inr": pool,
                "billable_fte": n,
                "cpr_inr": cpr,
            },
        }

    if key == "operating_cost":
        user_ids = _user_ids_with_team_salary(db, team_id, as_of=today) if team_id else None
        # Company-wide: all salary users (user_ids None)
        if user_ids is None:
            salary_lines = _salary_lines(
                db,
                {
                    row
                    for row in db.scalars(
                        select(User.id).where(
                            User.is_active.is_(True), User.requires_salary.is_(True)
                        )
                    ).all()
                },
                as_of=today,
            )
        else:
            salary_lines = _salary_lines(
                db, user_ids, as_of=today, team_id=team_id
            )
        team_ids = [team_id] if team_id else [
            t.id for t in db.scalars(select(Team).where(Team.is_active.is_(True))).all()
        ]
        opex_lines = _expense_lines(
            db,
            team_ids=team_ids,
            paid_by=ExpensePaidBy.prosohm,
            nature=CostNature.opex,
            fy_start=fy_start,
            as_of=today,
        )
        capex_lines = _expense_lines(
            db,
            team_ids=team_ids,
            paid_by=ExpensePaidBy.prosohm,
            nature=CostNature.capex,
            fy_start=fy_start,
            as_of=today,
        )
        salary_total = (
            _salary_for_team(db, team_id, as_of=today)
            if team_id
            else _salary_for_users(db, None, as_of=today)
        )
        opex_total = _expense_sum(
            db,
            team_id=team_id,
            paid_by=ExpensePaidBy.prosohm,
            nature=CostNature.opex,
            as_of=today,
        )
        capex_total = _expense_sum(
            db,
            team_id=team_id,
            paid_by=ExpensePaidBy.prosohm,
            nature=CostNature.capex,
            as_of=today,
        )
        total = _q(salary_total + opex_total + capex_total)
        return {
            "metric": key,
            "title": "Operating cost / month",
            "subtitle": "Salaries + team-assigned Prosohm OpEx (software) + CapEx (hardware) in the current filter.",
            "total_inr": total,
            "currency_code": base,
            "formula": "Operating = salaries + OpEx + CapEx",
            "insights": _insights_from_lines(
                salary_lines[:4] + opex_lines[:3] + capex_lines[:3],
                total,
                subject="cost drivers",
            ),
            "groups": [
                {
                    "label": "Salaries",
                    "total_inr": _q(salary_total),
                    "lines": _annotate(salary_lines[:30], _q(salary_total) or Decimal("1")),
                },
                {
                    "label": "Prosohm OpEx (software / overheads)",
                    "total_inr": _q(opex_total),
                    "lines": _annotate(opex_lines[:30], _q(opex_total) or Decimal("1")),
                },
                {
                    "label": "Prosohm CapEx (hardware)",
                    "total_inr": _q(capex_total),
                    "lines": _annotate(capex_lines[:30], _q(capex_total) or Decimal("1")),
                },
            ],
            "empty_hints": [],
        }

    if key == "team_fees":
        from app.models.finance import TeamCommercialTerms
        from app.models.models import WorkingModel
        from app.services.finance.commercial_fee_rules import uses_flat_customer_fee
        from app.services.finance.dashboard_service import _normalize_monthly_fee
        from app.models.enums import WorkingModelCode
        from app.services.finance.billable_headcount import (
            billable_salary_counts_by_skill,
            billable_salary_headcount,
        )

        stmt = select(TeamCommercialTerms).where(TeamCommercialTerms.is_active.is_(True))
        if team_id is not None:
            stmt = stmt.where(TeamCommercialTerms.team_id == team_id)
        lines: list[dict] = []
        for term in db.scalars(stmt).all():
            if term.effective_from and term.effective_from > today:
                continue
            if term.effective_to and term.effective_to < today:
                continue
            model = db.get(WorkingModel, term.working_model_id)
            strategy = model.strategy_key if model is not None else None
            if not uses_flat_customer_fee(strategy):
                continue
            team = db.get(Team, term.team_id)
            is_retainer = strategy == WorkingModelCode.retainer or (
                hasattr(strategy, "value") and strategy.value == WorkingModelCode.retainer.value
            )
            bands = list(getattr(term, "fee_bands", None) or [])
            if is_retainer and bands:
                counts = billable_salary_counts_by_skill(db, term.team_id)
                band_map = {
                    (band.skill_level or ""): _q(band.base_fee_inr) for band in bands
                }
                default_rate = band_map.get("") or _q(term.base_fee_inr)
                period_amount = Decimal("0.00")
                for skill, count in counts.items():
                    rate = band_map.get(skill, default_rate)
                    period_amount += rate * Decimal(count)
            elif is_retainer:
                count = billable_salary_headcount(db, term.team_id)
                period_amount = _q(term.base_fee_inr) * Decimal(count)
            else:
                period_amount = _q(term.base_fee_inr)
            monthly = _normalize_monthly_fee(period_amount, term.billing_period)
            if monthly <= 0:
                continue
            lines.append(
                {
                    "id": str(term.id),
                    "label": team.name if team else str(term.team_id),
                    "detail": model.name if model else "Commercial fee",
                    "amount_inr": _q(monthly),
                    "kind": "fee",
                }
            )
        lines.sort(key=lambda r: r["amount_inr"], reverse=True)
        total = _team_fee_monthly(db, team_id=team_id, today=today)
        return {
            "metric": key,
            "title": "Team fees / month",
            "subtitle": "Retainer / subscription commercial terms normalized to monthly INR.",
            "total_inr": _q(total),
            "currency_code": base,
            "formula": "Sum of active flat customer fee terms (monthly equivalent)",
            "insights": _insights_from_lines(lines, _q(total), subject="fee lines"),
            "groups": [
                {
                    "label": "Commercial fees",
                    "total_inr": _q(total),
                    "lines": _annotate(lines, _q(total) or Decimal("1"), band_mode="revenue"),
                }
            ],
            "empty_hints": [],
        }

    # revenue_quarter — actual awards in FY quarter + retainer accrued (not monthly × 3)
    fy_start = current_fy_start(today)
    quote_month, quote_quarter = _quote_period_amounts(
        db, team_id=team_id, today=today, fy_start=fy_start
    )
    fee_month, fee_quarter = _retainer_fee_for_period(
        db, team_id=team_id, today=today, fy_start=fy_start
    )
    quarterly = _q(quote_quarter + fee_quarter)
    lines = [
        {
            "id": "quotes_quarter",
            "label": "Awarded quotes this FY quarter",
            "detail": "Sum by quoted date (project / quote model — actual, not projected)",
            "amount_inr": _q(quote_quarter),
            "kind": "revenue",
        },
        {
            "id": "fees_quarter",
            "label": "Retainer / fixed fees accrued this quarter",
            "detail": "Monthly commercial fee × months elapsed in quarter",
            "amount_inr": _q(fee_quarter),
            "kind": "revenue",
        },
        {
            "id": "quotes_month",
            "label": "Awarded quotes this month (reference)",
            "detail": "Quoted date in current calendar month",
            "amount_inr": _q(quote_month),
            "kind": "revenue",
        },
        {
            "id": "fees_month",
            "label": "Retainer fee this month (reference)",
            "detail": "Active flat customer fee terms",
            "amount_inr": _q(fee_month),
            "kind": "revenue",
        },
    ]
    return {
        "metric": key,
        "title": "Revenue / quarter (actual)",
        "subtitle": (
            "Quote awards dated in the current FY quarter plus retainer fees accrued "
            "for months elapsed — not a 3× monthly projection."
        ),
        "total_inr": quarterly,
        "currency_code": base,
        "formula": (
            "Σ quotes with quoted_date in current FY quarter "
            "+ (retainer monthly × months elapsed in quarter)"
        ),
        "insights": [
            f"Quarter-to-date actual {quarterly} {base}",
            f"This month awards {quote_month} {base} + retainer {fee_month} {base}",
        ],
        "groups": [
            {
                "label": "Quarter-to-date building blocks",
                "total_inr": quarterly,
                "lines": _annotate(
                    [lines[0], lines[1]],
                    quarterly or Decimal("1"),
                    band_mode="revenue",
                ),
            }
        ],
        "empty_hints": [],
    }


def _insights_from_lines(lines: list[dict], total: Decimal, *, subject: str) -> list[str]:
    if not lines or total <= 0:
        return [f"No {subject} contributing yet"]
    top = lines[0]
    share = _pct(top["amount_inr"], total)
    insights = [f"Largest: {top['label']} ({share}% of total)"]
    if len(lines) >= 3:
        top3 = sum((r["amount_inr"] for r in lines[:3]), Decimal("0"))
        insights.append(f"Top 3 drivers = {_pct(top3, total)}% of total")
    return insights
