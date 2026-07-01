"""Phase 8 schema migrations."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


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


def ensure_phase8_columns(engine: Engine) -> None:
    dialect = engine.dialect.name
    folder_columns = [
        ("project_folder_path", "VARCHAR(500)"),
        ("cad_folder_path", "VARCHAR(500)"),
        ("released_folder_path", "VARCHAR(500)"),
    ]

    if dialect == "sqlite":
        for column, definition in folder_columns:
            _sqlite_add_column(engine, "projects", column, definition)
        return

    if dialect == "postgresql":
        for column, definition in folder_columns:
            _pg_add_column(engine, "projects", column, definition)


def ensure_phase8_foundation(engine: Engine) -> None:
    ensure_phase8_columns(engine)
