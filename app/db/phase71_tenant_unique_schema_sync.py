"""Phase 71 — rebuild natural-key uniques as (tenant_id, …) (R10 M1b)."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.tenant_unique_constraints import TENANT_UNIQUE_SPECS

logger = logging.getLogger("protrack.phase71")


def _sqlite_table_exists(connection, table: str) -> bool:
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": table},
    ).fetchone()
    return row is not None


def _sqlite_unique_indexes(connection, table: str) -> list[tuple[str, tuple[str, ...], str]]:
    """Return (index_name, columns, origin) for unique indexes on table."""
    out: list[tuple[str, tuple[str, ...], str]] = []
    rows = connection.execute(text(f"PRAGMA index_list('{table}')")).fetchall()
    for row in rows:
        # seq, name, unique, origin, partial
        name = row[1]
        is_unique = bool(row[2])
        origin = row[3] if len(row) > 3 else "c"
        if not is_unique:
            continue
        cols = tuple(
            info[2]
            for info in connection.execute(text(f"PRAGMA index_info('{name}')")).fetchall()
        )
        out.append((name, cols, origin))
    return out


def _pg_table_exists(connection, table: str) -> bool:
    row = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=:n"
        ),
        {"n": table},
    ).fetchone()
    return row is not None


def _drop_sqlite_matching_uniques(
    connection, table: str, legacy_columns: tuple[str, ...]
) -> None:
    for name, cols, origin in _sqlite_unique_indexes(connection, table):
        if cols != legacy_columns:
            continue
        if origin == "pk":
            continue
        try:
            connection.execute(text(f'DROP INDEX IF EXISTS "{name}"'))
        except Exception as exc:
            logger.warning(
                "phase71: could not drop sqlite unique %s on %s (%s): %s",
                name,
                table,
                cols,
                exc,
            )


def _ensure_sqlite_unique(
    connection, table: str, name: str, columns: tuple[str, ...]
) -> None:
    existing = {idx[0] for idx in _sqlite_unique_indexes(connection, table)}
    # Already present under target name, or equivalent column set.
    for idx_name, cols, _origin in _sqlite_unique_indexes(connection, table):
        if cols == columns:
            return
    if name in existing:
        return
    col_sql = ", ".join(f'"{c}"' for c in columns)
    connection.execute(
        text(f'CREATE UNIQUE INDEX IF NOT EXISTS "{name}" ON "{table}" ({col_sql})')
    )


def _ensure_pg_unique(
    connection, table: str, name: str, columns: tuple[str, ...], legacy: tuple[str, ...]
) -> None:
    # Drop legacy unique constraints / indexes that match legacy column set.
    rows = connection.execute(
        text(
            """
            SELECT c.conname, array_agg(a.attname ORDER BY u.attposition) AS cols
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS u(attnum, attposition) ON true
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = u.attnum
            WHERE n.nspname = 'public'
              AND t.relname = :table
              AND c.contype = 'u'
            GROUP BY c.conname
            """
        ),
        {"table": table},
    ).fetchall()
    for conname, cols in rows:
        col_tuple = tuple(cols)
        if col_tuple == legacy or (
            col_tuple == columns and conname != name
        ):
            connection.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{conname}"'))

    # Also drop unique indexes not backed as constraints (SQLAlchemy ix_*).
    idx_rows = connection.execute(
        text(
            """
            SELECT i.relname AS index_name,
                   array_agg(a.attname ORDER BY x.n) AS cols
            FROM pg_class t
            JOIN pg_namespace ns ON t.relnamespace = ns.oid
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS x(attnum, n) ON true
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum
            WHERE ns.nspname = 'public'
              AND t.relname = :table
              AND ix.indisunique
              AND NOT ix.indisprimary
            GROUP BY i.relname
            """
        ),
        {"table": table},
    ).fetchall()
    for index_name, cols in idx_rows:
        col_tuple = tuple(cols)
        if col_tuple == legacy:
            connection.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))

    col_sql = ", ".join(f'"{c}"' for c in columns)
    connection.execute(
        text(
            f'DO $$ BEGIN '
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" UNIQUE ({col_sql}); '
            f'EXCEPTION WHEN duplicate_object THEN NULL; '
            f'WHEN unique_violation THEN NULL; END $$'
        )
    )


def ensure_phase71_tenant_unique_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        for spec in TENANT_UNIQUE_SPECS:
            if dialect == "sqlite":
                if not _sqlite_table_exists(connection, spec.table):
                    continue
                # Singleton specs: legacy_columns == ("tenant_id",) means create-only.
                if spec.legacy_columns != ("tenant_id",) or len(spec.columns) > 1:
                    _drop_sqlite_matching_uniques(
                        connection, spec.table, spec.legacy_columns
                    )
                _ensure_sqlite_unique(connection, spec.table, spec.name, spec.columns)
            else:
                if not _pg_table_exists(connection, spec.table):
                    continue
                if spec.legacy_columns != ("tenant_id",) or len(spec.columns) > 1:
                    _ensure_pg_unique(
                        connection,
                        spec.table,
                        spec.name,
                        spec.columns,
                        spec.legacy_columns,
                    )
                else:
                    # Singleton: only ensure constraint exists.
                    _ensure_pg_unique(
                        connection,
                        spec.table,
                        spec.name,
                        spec.columns,
                        (),  # nothing legacy to drop by column set
                    )
