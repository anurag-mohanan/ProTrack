"""Phase 32 — Budget quarterly columns + team commercial skill fee bands."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _sqlite_has_table(engine: Engine, table_name: str) -> bool:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
    return row is not None


def ensure_phase32_finance_quarterly_fee_bands_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    budget_cols = [
        "q1_allocated",
        "q2_allocated",
        "q3_allocated",
        "q4_allocated",
        "q1_forecast",
        "q2_forecast",
        "q3_forecast",
        "q4_forecast",
    ]
    with engine.begin() as connection:
        for col in budget_cols:
            if dialect == "sqlite":
                if not _sqlite_has_column(engine, "budgets", col):
                    connection.execute(
                        text(f"ALTER TABLE budgets ADD COLUMN {col} NUMERIC(14, 2) DEFAULT 0")
                    )
            else:
                connection.execute(
                    text(
                        f"ALTER TABLE budgets ADD COLUMN IF NOT EXISTS {col} NUMERIC(14, 2) DEFAULT 0"
                    )
                )

        # Even-split legacy FY allocated into quarters when all quarter cols are zero.
        connection.execute(
            text(
                """
                UPDATE budgets
                SET
                  q1_allocated = ROUND(allocated / 4.0, 2),
                  q2_allocated = ROUND(allocated / 4.0, 2),
                  q3_allocated = ROUND(allocated / 4.0, 2),
                  q4_allocated = allocated - 3 * ROUND(allocated / 4.0, 2),
                  q1_forecast = ROUND(COALESCE(forecast, allocated) / 4.0, 2),
                  q2_forecast = ROUND(COALESCE(forecast, allocated) / 4.0, 2),
                  q3_forecast = ROUND(COALESCE(forecast, allocated) / 4.0, 2),
                  q4_forecast = COALESCE(forecast, allocated)
                    - 3 * ROUND(COALESCE(forecast, allocated) / 4.0, 2)
                WHERE COALESCE(q1_allocated, 0) = 0
                  AND COALESCE(q2_allocated, 0) = 0
                  AND COALESCE(q3_allocated, 0) = 0
                  AND COALESCE(q4_allocated, 0) = 0
                  AND COALESCE(allocated, 0) <> 0
                """
            )
        )

        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "team_commercial_fee_bands"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE team_commercial_fee_bands (
                          id CHAR(36) NOT NULL PRIMARY KEY,
                          terms_id CHAR(36) NOT NULL,
                          skill_level VARCHAR(32),
                          fee_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                          currency_code VARCHAR(3) NOT NULL DEFAULT 'INR',
                          base_fee_inr NUMERIC(14, 2) NOT NULL DEFAULT 0,
                          fx_rate NUMERIC(18, 8) NOT NULL DEFAULT 1,
                          notes TEXT,
                          created_at DATETIME,
                          updated_at DATETIME,
                          FOREIGN KEY(terms_id) REFERENCES team_commercial_terms(id),
                          FOREIGN KEY(currency_code) REFERENCES currencies(code)
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_team_commercial_fee_bands_terms "
                        "ON team_commercial_fee_bands(terms_id)"
                    )
                )
        else:
            insp = inspect(engine)
            if "team_commercial_fee_bands" not in insp.get_table_names():
                connection.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS team_commercial_fee_bands (
                          id UUID PRIMARY KEY,
                          terms_id UUID NOT NULL REFERENCES team_commercial_terms(id),
                          skill_level VARCHAR(32),
                          fee_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
                          currency_code VARCHAR(3) NOT NULL DEFAULT 'INR'
                            REFERENCES currencies(code),
                          base_fee_inr NUMERIC(14, 2) NOT NULL DEFAULT 0,
                          fx_rate NUMERIC(18, 8) NOT NULL DEFAULT 1,
                          notes TEXT,
                          created_at TIMESTAMP,
                          updated_at TIMESTAMP
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_team_commercial_fee_bands_terms "
                        "ON team_commercial_fee_bands(terms_id)"
                    )
                )
