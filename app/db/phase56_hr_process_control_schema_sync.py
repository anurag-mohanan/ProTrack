"""Phase 56 — HR Process Control (notification enum + email template seed).

Adds ``new_hire_onboarding`` to PostgreSQL ``notification_type`` enum.
Idempotent for SQLite and PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def _ensure_pg_enum_value(engine: Engine, enum_name: str, value: str) -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                """
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = :enum_name AND e.enumlabel = :value
                """
            ),
            {"enum_name": enum_name, "value": value},
        ).fetchone()
        if exists:
            return
        connection.execute(
            text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
        )


def _ensure_email_template(engine: Engine) -> None:
    session = sessionmaker(bind=engine)()
    try:
        from app.services.email_template_defaults import DEFAULT_EMAIL_TEMPLATES
        from app.models.foundation import EmailTemplate
        from sqlalchemy import select

        seed = next(
            (row for row in DEFAULT_EMAIL_TEMPLATES if row["slug"] == "new_hire_onboarding"),
            None,
        )
        if seed is None:
            return
        existing = session.scalar(
            select(EmailTemplate).where(EmailTemplate.slug == seed["slug"])
        )
        if existing is None:
            session.add(
                EmailTemplate(
                    slug=seed["slug"],
                    name=seed["name"],
                    description=seed.get("description"),
                    subject=seed["subject"],
                    body_html=seed["body_html"],
                    body_text=seed.get("body_text"),
                    is_enabled=True,
                    is_system=True,
                )
            )
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_phase56_hr_process_control_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "postgresql":
        _ensure_pg_enum_value(engine, "notification_type", "new_hire_onboarding")
    _ensure_email_template(engine)
