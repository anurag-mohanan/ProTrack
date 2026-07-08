"""Email communication center schema sync."""

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.foundation import EmailSettings, EmailTemplate
from app.services.email.providers.zoho_provider import ZohoProvider
from app.services.email_template_defaults import DEFAULT_EMAIL_TEMPLATES


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


def ensure_email_communication_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    email_settings_columns = [
        ("provider_type", "VARCHAR(32) NOT NULL DEFAULT 'zoho'"),
        ("reply_to_email", "VARCHAR(255)"),
        ("company_signature", "TEXT"),
        ("connection_status", "VARCHAR(32)"),
        ("connection_checked_at", "TIMESTAMP"),
        ("connection_message", "TEXT"),
    ]
    preference_columns = [
        ("email_assignment_enabled", "BOOLEAN NOT NULL DEFAULT 1"),
        ("email_reminder_enabled", "BOOLEAN NOT NULL DEFAULT 1"),
        ("email_ai_insights_enabled", "BOOLEAN NOT NULL DEFAULT 1"),
        ("email_daily_summary_enabled", "BOOLEAN NOT NULL DEFAULT 1"),
        ("email_weekly_summary_enabled", "BOOLEAN NOT NULL DEFAULT 1"),
        ("email_monthly_report_enabled", "BOOLEAN NOT NULL DEFAULT 1"),
    ]

    add_column = _sqlite_add_column if dialect == "sqlite" else _pg_add_column
    for column, definition in email_settings_columns:
        add_column(engine, "email_settings", column, definition)
    for column, definition in preference_columns:
        add_column(engine, "user_preferences", column, definition)

    session = sessionmaker(bind=engine)()
    try:
        settings = session.scalar(select(EmailSettings).limit(1))
        if settings is None:
            settings = EmailSettings()
            ZohoProvider.apply_defaults(settings)
            session.add(settings)
        elif not settings.smtp_host:
            ZohoProvider.apply_defaults(settings)
            session.add(settings)

        existing_slugs = set(session.scalars(select(EmailTemplate.slug)).all())
        for template in DEFAULT_EMAIL_TEMPLATES:
            if template["slug"] not in existing_slugs:
                session.add(EmailTemplate(**template, is_system=True))

        session.commit()
    finally:
        session.close()
