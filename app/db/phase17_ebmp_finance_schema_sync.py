"""Phase 17 — EBMP Financial Planning foundation + HR roles."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import AiForecastKind, CostFrequency, CostNature
from app.models.finance import (
    AiForecastPlaceholder,
    CompanyFinanceSettings,
    CostCentre,
    Currency,
    FxRate,
)
from app.models.models import Role


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _ensure_user_module_actions(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "users", "module_actions"):
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN module_actions TEXT"))
        return
    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS module_actions TEXT")
            )


SEED_CURRENCIES = [
    {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "is_base": True},
    {"code": "USD", "name": "US Dollar", "symbol": "$", "is_base": False},
    {"code": "EUR", "name": "Euro", "symbol": "€", "is_base": False},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "is_base": False},
    {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ", "is_base": False},
    {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$", "is_base": False},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥", "is_base": False},
]

SEED_COST_CENTRES = [
    ("EMP_SALARY", "Employee Salary", CostNature.opex, CostFrequency.monthly),
    ("EMP_HOURLY", "Employee Hourly Cost", CostNature.opex, CostFrequency.monthly),
    ("CONTRACTOR", "Contractor Cost", CostNature.opex, CostFrequency.monthly),
    ("SW_LICENSES", "Software Licenses", CostNature.opex, CostFrequency.yearly),
    ("SW_RENEWALS", "Software Renewals", CostNature.opex, CostFrequency.yearly),
    ("HARDWARE", "Hardware", CostNature.capex, CostFrequency.one_time),
    ("SERVERS", "Servers", CostNature.capex, CostFrequency.one_time),
    ("CLOUD", "Cloud", CostNature.opex, CostFrequency.monthly),
    ("TRAINING", "Training", CostNature.opex, CostFrequency.yearly),
    ("TRAVEL", "Travel", CostNature.opex, CostFrequency.one_time),
    ("RENT", "Rent", CostNature.opex, CostFrequency.monthly),
    ("UTILITIES", "Utilities", CostNature.opex, CostFrequency.monthly),
    ("INSURANCE", "Insurance", CostNature.opex, CostFrequency.yearly),
    ("TAXES", "Taxes", CostNature.opex, CostFrequency.yearly),
    ("OFFICE", "Office Expenses", CostNature.opex, CostFrequency.monthly),
    ("MAINTENANCE", "Maintenance", CostNature.opex, CostFrequency.monthly),
    ("INTERNET", "Internet", CostNature.opex, CostFrequency.monthly),
    ("MISC", "Miscellaneous", CostNature.opex, CostFrequency.monthly),
]

SEED_AI_PLACEHOLDERS = [
    (AiForecastKind.revenue_forecast, "Revenue Forecast", "Placeholder for AI revenue forecast"),
    (AiForecastKind.capacity_forecast, "Capacity Forecast", "Placeholder for AI capacity forecast"),
    (AiForecastKind.profit_forecast, "Profit Forecast", "Placeholder for AI profit forecast"),
    (AiForecastKind.underquoted_projects, "Underquoted Projects", "Projects likely underquoted"),
    (AiForecastKind.overquoted_projects, "Overquoted Projects", "Projects likely overquoted"),
    (AiForecastKind.customer_profitability, "Customer Profitability", "AI customer margin insights"),
    (AiForecastKind.employee_productivity, "Employee Productivity", "AI productivity insights"),
    (
        AiForecastKind.software_renewal_prediction,
        "Software Renewal Prediction",
        "Upcoming renewal risk",
    ),
    (AiForecastKind.budget_risk, "Budget Risk", "Budgets at risk of overrun"),
    (AiForecastKind.cash_flow_trend, "Cash Flow Trend", "Cash flow trend placeholder"),
]


def _seed_finance(session: Session) -> None:
    for row in SEED_CURRENCIES:
        existing = session.get(Currency, row["code"])
        if existing is None:
            session.add(
                Currency(
                    code=row["code"],
                    name=row["name"],
                    symbol=row["symbol"],
                    is_active=True,
                    is_base=row["is_base"],
                )
            )
        else:
            existing.name = row["name"]
            existing.symbol = row["symbol"]
            existing.is_base = row["is_base"]
            existing.is_active = True
    session.flush()

    # Seed common FX rates to INR once (early effective date so FY-start
    # commercial terms / expenses convert). Do not reseed every calendar day.
    from app.db.phase27_fx_rate_backfill import DEFAULT_RATES_TO_INR, SEED_FX_EFFECTIVE

    for code, rate in DEFAULT_RATES_TO_INR:
        existing = session.scalar(
            select(FxRate)
            .where(
                FxRate.from_currency == code,
                FxRate.to_currency == "INR",
            )
            .limit(1)
        )
        if existing is None:
            session.add(
                FxRate(
                    from_currency=code,
                    to_currency="INR",
                    rate=rate,
                    effective_date=SEED_FX_EFFECTIVE,
                    source="seed",
                )
            )

    settings = session.scalar(
        select(CompanyFinanceSettings).where(CompanyFinanceSettings.is_active.is_(True))
    )
    if settings is None:
        session.add(
            CompanyFinanceSettings(
                base_currency="INR",
                display_name="Company Default",
                is_active=True,
            )
        )

    for index, (code, name, nature, frequency) in enumerate(SEED_COST_CENTRES):
        existing = session.scalar(select(CostCentre).where(CostCentre.code == code))
        if existing is None:
            session.add(
                CostCentre(
                    code=code,
                    name=name,
                    nature=nature,
                    default_frequency=frequency,
                    sort_order=index,
                    is_active=True,
                )
            )

    for kind, title, description in SEED_AI_PLACEHOLDERS:
        existing = session.scalar(
            select(AiForecastPlaceholder).where(AiForecastPlaceholder.kind == kind)
        )
        if existing is None:
            session.add(
                AiForecastPlaceholder(
                    kind=kind,
                    title=title,
                    description=description,
                    is_active=True,
                )
            )


def _seed_hr_roles(session: Session) -> None:
    for name, description in (
        ("HR", "Human Resources — view teams, users, leave, productivity, timesheets"),
        (
            "Office Administrator",
            "Office administration — timesheet completion monitoring and HR reports",
        ),
    ):
        existing = session.scalar(select(Role).where(Role.name == name))
        if existing is None:
            session.add(Role(name=name, description=description))
        elif not existing.description:
            existing.description = description


def ensure_phase17_ebmp_finance_foundation(engine: Engine) -> None:
    _ensure_user_module_actions(engine)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        _seed_hr_roles(session)
        _seed_finance(session)
        session.commit()
    finally:
        session.close()
