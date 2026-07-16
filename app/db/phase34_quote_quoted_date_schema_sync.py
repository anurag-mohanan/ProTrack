"""Phase 34 — quotes.quoted_date for Annual Plan sales quarter placement."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_phase34_quote_quoted_date_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_column(engine, "quotes", "quoted_date"):
                connection.execute(text("ALTER TABLE quotes ADD COLUMN quoted_date DATE"))
            # Prefer revision start_date (PDF / import document date only).
            connection.execute(
                text(
                    """
                    UPDATE quotes
                    SET quoted_date = (
                        SELECT qr.start_date
                        FROM quote_revisions qr
                        WHERE qr.quote_id = quotes.id
                          AND qr.version = quotes.current_version
                          AND qr.revision = quotes.current_revision
                          AND qr.start_date IS NOT NULL
                        LIMIT 1
                    )
                    WHERE quoted_date IS NULL
                    """
                )
            )
        else:
            connection.execute(
                text("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS quoted_date DATE")
            )
            connection.execute(
                text(
                    """
                    UPDATE quotes
                    SET quoted_date = sub.d
                    FROM (
                        SELECT q.id AS quote_id,
                               qr.start_date AS d
                        FROM quotes q
                        JOIN quote_revisions qr
                          ON qr.quote_id = q.id
                         AND qr.version = q.current_version
                         AND qr.revision = q.current_revision
                        WHERE qr.start_date IS NOT NULL
                    ) AS sub
                    WHERE quotes.id = sub.quote_id
                      AND quotes.quoted_date IS NULL
                    """
                )
            )
