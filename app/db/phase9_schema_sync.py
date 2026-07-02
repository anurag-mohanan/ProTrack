"""Phase 9 — company branding, user preferences, extended company profile."""

from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.models.foundation import BrandingSettings, CompanySettings, UserPreferences


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    if not _sqlite_has_column(engine, table, column):
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def _pg_add_column(engine: Engine, table: str, column: str, definition: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")
        )


def ensure_phase9_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    company_columns = [
        ("company_short_name", "VARCHAR(80)"),
        ("email", "VARCHAR(255)"),
    ]
    user_columns = [
        ("phone", "VARCHAR(50)"),
        ("designation", "VARCHAR(100)"),
        ("manager_id", "BLOB" if dialect == "sqlite" else "UUID"),
    ]

    if dialect == "sqlite":
        for column, definition in company_columns:
            _sqlite_add_column(engine, "company_settings", column, definition)
        for column, definition in user_columns:
            _sqlite_add_column(engine, "users", column, definition)
        return

    if dialect == "postgresql":
        for column, definition in company_columns:
            _pg_add_column(engine, "company_settings", column, definition)
        for column, definition in user_columns:
            _pg_add_column(engine, "users", column, definition)


DEFAULT_BRANDING = {
    "theme_preset": "prosohm_professional",
    "primary_color": "#0066B3",
    "secondary_color": "#1E293B",
    "accent_color": "#0EA5E9",
    "success_color": "#16A34A",
    "warning_color": "#D97706",
    "danger_color": "#DC2626",
    "sidebar_color": "#0F172A",
    "header_color": "#FFFFFF",
    "button_style": "rounded",
    "border_radius": 12,
    "card_style": "elevated",
    "density": "default",
}


def ensure_phase9_seed_data(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        if session.scalar(select(BrandingSettings.id).limit(1)) is None:
            session.add(BrandingSettings(**DEFAULT_BRANDING))

        company = session.scalar(select(CompanySettings).limit(1))
        if company is not None and not company.company_short_name:
            company.company_short_name = company.company_name.split()[0]

        session.commit()
    finally:
        session.close()


def ensure_phase9_foundation(engine: Engine) -> None:
    ensure_phase9_columns(engine)
    ensure_phase9_seed_data(engine)
