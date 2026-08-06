"""Phase 77 — Projects Command Center: workstreams, project links, saved views."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.workstream import ProjectSavedView, ProjectWorkstream, Workstream  # noqa: F401


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_projects_cc_preference_columns(engine: Engine) -> None:
    """Command Center layout / card visibility prefs on user_preferences."""
    dialect = engine.dialect.name
    columns = [
        ("projects_cc_layout", "VARCHAR(20) NOT NULL DEFAULT 'list'"),
        ("projects_cc_default_view_id", "CHAR(36)"),
        ("projects_cc_show_workstreams", "BOOLEAN NOT NULL DEFAULT 1"),
        ("projects_cc_show_teams", "BOOLEAN NOT NULL DEFAULT 1"),
        ("projects_cc_show_status", "BOOLEAN NOT NULL DEFAULT 1"),
    ]
    with engine.begin() as connection:
        if dialect == "sqlite":
            for name, ddl in columns:
                if not _sqlite_has_column(engine, "user_preferences", name):
                    connection.execute(
                        text(f"ALTER TABLE user_preferences ADD COLUMN {name} {ddl}")
                    )
        else:
            for name, ddl in columns:
                # Postgres: BOOLEAN DEFAULT true
                pg_ddl = ddl.replace("BOOLEAN NOT NULL DEFAULT 1", "BOOLEAN NOT NULL DEFAULT TRUE")
                pg_ddl = pg_ddl.replace("CHAR(36)", "UUID")
                connection.execute(
                    text(
                        f"ALTER TABLE user_preferences "
                        f"ADD COLUMN IF NOT EXISTS {name} {pg_ddl}"
                    )
                )


def ensure_workstream_color_column(engine: Engine) -> None:
    """Additive color accent for workstream section chrome."""
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "workstreams", "color"):
                connection.execute(
                    text("ALTER TABLE workstreams ADD COLUMN color VARCHAR(20)")
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE workstreams "
                    "ADD COLUMN IF NOT EXISTS color VARCHAR(20)"
                )
            )


def ensure_project_type_default_workstream_column(engine: Engine) -> None:
    """Map project types → default workstream for Command Center segregation."""
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "project_types", "default_workstream_id"):
                connection.execute(
                    text(
                        "ALTER TABLE project_types "
                        "ADD COLUMN default_workstream_id CHAR(36)"
                    )
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE project_types "
                    "ADD COLUMN IF NOT EXISTS default_workstream_id UUID "
                    "REFERENCES workstreams(id)"
                )
            )


def ensure_phase77_command_center_foundation(engine: Engine) -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Workstream.__table__,
            ProjectWorkstream.__table__,
            ProjectSavedView.__table__,
        ],
    )
    ensure_workstream_color_column(engine)
    ensure_project_type_default_workstream_column(engine)
    ensure_projects_cc_preference_columns(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        from app.db.workstream_seed import (
            ensure_project_type_workstream_defaults,
            ensure_workstream_catalog,
        )

        ensure_workstream_catalog(session)
        ensure_project_type_workstream_defaults(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
