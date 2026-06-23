"""Apply lightweight schema updates for databases created before MVP columns."""

from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.models import Project, TimesheetEntry


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _backfill_project_actual_hours(session: Session) -> None:
    project_ids = session.scalars(select(Project.id)).all()
    for project_id in project_ids:
        total = session.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                TimesheetEntry.project_id == project_id
            )
        )
        project = session.get(Project, project_id)
        if project is not None:
            project.actual_hours = Decimal(str(total or 0))
            session.add(project)
    session.commit()


def ensure_project_actual_hours(engine: Engine) -> None:
    dialect = engine.dialect.name

    if dialect == "sqlite":
        if not _sqlite_has_column(engine, "projects", "actual_hours"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE projects "
                        "ADD COLUMN actual_hours NUMERIC(8, 2) NOT NULL DEFAULT 0"
                    )
                )
            session = sessionmaker(bind=engine)()
            try:
                _backfill_project_actual_hours(session)
            finally:
                session.close()
        return

    if dialect == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN IF NOT EXISTS actual_hours NUMERIC(8, 2) NOT NULL DEFAULT 0"
                )
            )
        session = sessionmaker(bind=engine)()
        try:
            _backfill_project_actual_hours(session)
        finally:
            session.close()
