"""Phase 15 — working models master data, FK columns, and project backfill."""

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import WorkingModelCode
from app.models.models import Project, WorkingModel


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


def _ensure_fk_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    uuid_type = "BLOB" if dialect == "sqlite" else "UUID"
    columns = [
        ("customers", "default_working_model_id", uuid_type),
        ("users", "default_working_model_id", uuid_type),
        ("projects", "working_model_id", uuid_type),
    ]
    if dialect == "sqlite":
        for table, column, definition in columns:
            _sqlite_add_column(engine, table, column, definition)
        return
    if dialect == "postgresql":
        for table, column, definition in columns:
            _pg_add_column(engine, table, column, definition)


SEED_WORKING_MODELS: list[dict] = [
    {
        "code": "project_based",
        "strategy_key": WorkingModelCode.project_based,
        "name": "Project Based (Fixed Fee)",
        "description": "Fixed-fee engagements tracked against quoted hours and milestones.",
        "sort_order": 0,
    },
    {
        "code": "time_materials",
        "strategy_key": WorkingModelCode.time_materials,
        "name": "Time & Materials (Hourly)",
        "description": "Hourly billing focused on billable utilization and approved hours.",
        "sort_order": 1,
    },
    {
        "code": "retainer",
        "strategy_key": WorkingModelCode.retainer,
        "name": "Retainer / Subscription",
        "description": "Monthly capacity retainer with consumption and remaining hours.",
        "sort_order": 2,
    },
    {
        "code": "overheads",
        "strategy_key": WorkingModelCode.overheads,
        "name": "Overheads",
        "description": (
            "Management and non-designer resources (Engineering Manager, HR, "
            "Office Administrator, and similar) tracked as overhead cost — not "
            "project fixed-fee or T&M delivery billing."
        ),
        "sort_order": 3,
    },
]


def _seed_working_models(session: Session) -> dict[str, WorkingModel]:
    by_code: dict[str, WorkingModel] = {}
    for index, seed in enumerate(SEED_WORKING_MODELS):
        existing = session.scalar(
            select(WorkingModel).where(WorkingModel.code == seed["code"])
        )
        if existing is None:
            existing = WorkingModel(
                code=seed["code"],
                strategy_key=seed["strategy_key"],
                name=seed["name"],
                description=seed["description"],
                sort_order=seed.get("sort_order", index),
                is_active=True,
                is_archived=False,
            )
            session.add(existing)
            session.flush()
        else:
            existing.name = seed["name"]
            existing.description = seed["description"]
            existing.strategy_key = seed["strategy_key"]
            if existing.sort_order == 0 and seed.get("sort_order") is not None:
                existing.sort_order = seed["sort_order"]
        by_code[existing.code] = existing
    return by_code


def _backfill_project_working_models(session: Session, models_by_code: dict[str, WorkingModel]) -> None:
    default_model = models_by_code.get("project_based")
    if default_model is None:
        return
    projects = session.scalars(
        select(Project).where(Project.working_model_id.is_(None))
    ).all()
    for project in projects:
        project.working_model_id = default_model.id
        session.add(project)


def ensure_phase15_working_model_foundation(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine, tables=[WorkingModel.__table__])
    _ensure_fk_columns(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        models_by_code = _seed_working_models(session)
        _backfill_project_working_models(session, models_by_code)
        session.commit()
