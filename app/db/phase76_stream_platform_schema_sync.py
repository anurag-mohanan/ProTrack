"""Phase 76 — Stream platform Phase A: CAD stream, project stream backfill, scope pref."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.engineering_stream_seed import ensure_engineering_streams
from app.models.models import Project, Stream, TaskType

MOLD_STREAM_NAME = "Mold Design"
CAD_STREAM_NAME = "CAD Development"


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_projects_portfolio_scope_column(engine: Engine) -> None:
    """Persist last-used projects portfolio scope (my_streams | my_teams | all)."""
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "user_preferences", "projects_portfolio_scope"):
                connection.execute(
                    text(
                        "ALTER TABLE user_preferences "
                        "ADD COLUMN projects_portfolio_scope VARCHAR(32) "
                        "NOT NULL DEFAULT 'my_streams'"
                    )
                )
        else:
            connection.execute(
                text(
                    "ALTER TABLE user_preferences "
                    "ADD COLUMN IF NOT EXISTS projects_portfolio_scope "
                    "VARCHAR(32) NOT NULL DEFAULT 'my_streams'"
                )
            )

CAD_TASK_TYPES: list[tuple[str, str]] = [
    ("Concept Design", "Early concept and ideation"),
    ("3D Modelling", "Solid / surface CAD modelling"),
    ("Detailing", "Drawing and detailing"),
    ("Design Review", "Design review and markups"),
    ("Change Incorporation", "ECO / design change incorporation"),
    ("Meeting", "Project meetings and coordination"),
]


def ensure_cad_development_stream(session: Session) -> Stream:
    """Ensure CAD Development stream exists with starter task types."""
    ensure_engineering_streams(session)
    stream = session.scalar(select(Stream).where(Stream.name == CAD_STREAM_NAME))
    if stream is None:
        # Fuzzy match near-duplicates
        for row in session.scalars(select(Stream)).all():
            if "cad" in row.name.lower() and "develop" in row.name.lower():
                stream = row
                break
    if stream is None:
        stream = Stream(
            name=CAD_STREAM_NAME,
            description="CAD / product design engineering stream",
            is_active=True,
            use_project_prefix=True,
            use_project_numbering=True,
            project_number_prefix="CAD",
            project_number_format="{prefix}-{seq:04d}",
            next_project_sequence=1,
        )
        session.add(stream)
        session.flush()
    elif not stream.is_active:
        stream.is_active = True

    existing = {
        row.name.strip().lower()
        for row in session.scalars(
            select(TaskType).where(TaskType.stream_id == stream.id)
        ).all()
    }
    for name, description in CAD_TASK_TYPES:
        if name.strip().lower() in existing:
            continue
        session.add(
            TaskType(
                stream_id=stream.id,
                name=name,
                description=description,
                is_billable=True,
                is_active=True,
            )
        )
    session.flush()
    return stream


def backfill_null_project_streams(session: Session) -> int:
    """Assign Mold Design stream to projects missing stream_id. Returns rows updated."""
    ensure_engineering_streams(session)
    mold = session.scalar(select(Stream).where(Stream.name == MOLD_STREAM_NAME))
    if mold is None:
        for row in session.scalars(select(Stream)).all():
            if "mold" in row.name.lower():
                mold = row
                break
    if mold is None:
        mold = Stream(
            name=MOLD_STREAM_NAME,
            description="Mold design engineering stream",
            is_active=True,
        )
        session.add(mold)
        session.flush()

    updated = 0
    for project in session.scalars(
        select(Project).where(Project.stream_id.is_(None))
    ).all():
        project.stream_id = mold.id
        updated += 1
    if updated:
        session.flush()
    return updated


def ensure_phase76_stream_platform_foundation(engine: Engine) -> None:
    ensure_projects_portfolio_scope_column(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        ensure_engineering_streams(session)
        ensure_cad_development_stream(session)
        backfill_null_project_streams(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
