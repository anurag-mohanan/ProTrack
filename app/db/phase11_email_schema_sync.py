"""Email settings, templates, and notification archive schema sync."""

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.foundation import EmailSettings, EmailTemplate, NotificationSettings
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


def ensure_email_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "sqlite":
        _sqlite_add_column(
            engine,
            "notification_settings",
            "email_notifications_enabled",
            "BOOLEAN NOT NULL DEFAULT 1",
        )
        _sqlite_add_column(engine, "notifications", "is_archived", "BOOLEAN NOT NULL DEFAULT 0")
        _sqlite_add_column(
            engine,
            "user_preferences",
            "email_notifications_enabled",
            "BOOLEAN NOT NULL DEFAULT 1",
        )
    elif dialect == "postgresql":
        _pg_add_column(
            engine,
            "notification_settings",
            "email_notifications_enabled",
            "BOOLEAN NOT NULL DEFAULT TRUE",
        )
        _pg_add_column(engine, "notifications", "is_archived", "BOOLEAN NOT NULL DEFAULT FALSE")
        _pg_add_column(
            engine,
            "user_preferences",
            "email_notifications_enabled",
            "BOOLEAN NOT NULL DEFAULT TRUE",
        )

    session = sessionmaker(bind=engine)()
    try:
        if session.scalar(select(EmailSettings.id).limit(1)) is None:
            session.add(EmailSettings())

        existing_slugs = set(session.scalars(select(EmailTemplate.slug)).all())
        for template in DEFAULT_EMAIL_TEMPLATES:
            if template["slug"] not in existing_slugs:
                session.add(EmailTemplate(**template, is_system=True))

        settings = session.scalar(select(NotificationSettings).limit(1))
        if settings is not None and not hasattr(settings, "email_notifications_enabled"):
            pass

        session.commit()
    finally:
        session.close()
