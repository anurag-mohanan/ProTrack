"""Phase 45 — performance review engine (templates + workflow columns)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services.performance_review_service import (
    DEFAULT_REVIEW_TEMPLATE,
    FORM_CODE,
    FORM_TITLE,
    RATING_SCALE,
)


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


def _add_column_sqlite(connection, table: str, column: str, ddl: str, engine: Engine) -> None:
    if not _sqlite_has_column(engine, table, column):
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def ensure_phase45_performance_review_engine_foundation(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            if not _sqlite_has_table(engine, "performance_review_templates"):
                connection.execute(
                    text(
                        """
                        CREATE TABLE performance_review_templates (
                            id CHAR(36) NOT NULL PRIMARY KEY,
                            code VARCHAR(64) NOT NULL,
                            name VARCHAR(200) NOT NULL,
                            version INTEGER NOT NULL DEFAULT 1,
                            kind VARCHAR(32) NOT NULL DEFAULT 'annual',
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            rating_scale_json TEXT NOT NULL DEFAULT '[]',
                            structure_json TEXT NOT NULL DEFAULT '[]',
                            created_by_id CHAR(36) NULL,
                            created_at DATETIME,
                            updated_at DATETIME,
                            UNIQUE (code, version),
                            FOREIGN KEY(created_by_id) REFERENCES users (id)
                        )
                        """
                    )
                )
            _add_column_sqlite(
                connection, "performance_review_cycles", "kind", "VARCHAR(32) NOT NULL DEFAULT 'annual'", engine
            )
            _add_column_sqlite(
                connection, "performance_review_cycles", "template_id", "CHAR(36) NULL", engine
            )
            _add_column_sqlite(
                connection,
                "performance_review_cycles",
                "calibration_required",
                "BOOLEAN NOT NULL DEFAULT 0",
                engine,
            )
            for col, ddl in (
                ("template_id", "CHAR(36) NULL"),
                ("template_version", "INTEGER NULL"),
                ("stage", "VARCHAR(32) NOT NULL DEFAULT 'self'"),
                ("self_submitted_at", "DATETIME NULL"),
                ("manager_submitted_at", "DATETIME NULL"),
                ("calibrated_at", "DATETIME NULL"),
                ("finalized_at", "DATETIME NULL"),
                ("calibrator_id", "CHAR(36) NULL"),
                ("calibration_notes", "TEXT NULL"),
                ("acknowledgement_signature", "VARCHAR(200) NULL"),
            ):
                _add_column_sqlite(connection, "performance_review_sheets", col, ddl, engine)
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS performance_review_templates (
                        id UUID PRIMARY KEY,
                        code VARCHAR(64) NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1,
                        kind VARCHAR(32) NOT NULL DEFAULT 'annual',
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        rating_scale_json TEXT NOT NULL DEFAULT '[]',
                        structure_json TEXT NOT NULL DEFAULT '[]',
                        created_by_id UUID NULL REFERENCES users(id),
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP,
                        UNIQUE (code, version)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE performance_review_cycles ADD COLUMN IF NOT EXISTS kind VARCHAR(32) NOT NULL DEFAULT 'annual'"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE performance_review_cycles ADD COLUMN IF NOT EXISTS template_id UUID NULL"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE performance_review_cycles ADD COLUMN IF NOT EXISTS calibration_required BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            for stmt in (
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS template_id UUID NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS template_version INTEGER NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS stage VARCHAR(32) NOT NULL DEFAULT 'self'",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS self_submitted_at TIMESTAMP NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS manager_submitted_at TIMESTAMP NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS calibrated_at TIMESTAMP NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS calibrator_id UUID NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS calibration_notes TEXT NULL",
                "ALTER TABLE performance_review_sheets ADD COLUMN IF NOT EXISTS acknowledgement_signature VARCHAR(200) NULL",
            ):
                connection.execute(text(stmt))

    _seed_annual_template_and_backfill(engine)


def _seed_annual_template_and_backfill(engine: Engine) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    structure = json.dumps(DEFAULT_REVIEW_TEMPLATE)
    scale = json.dumps(RATING_SCALE)
    template_id = str(uuid.uuid4())

    with engine.begin() as connection:
        existing = connection.execute(
            text(
                "SELECT id FROM performance_review_templates WHERE code = :code AND version = 1"
            ),
            {"code": FORM_CODE},
        ).fetchone()
        if existing is None:
            connection.execute(
                text(
                    """
                    INSERT INTO performance_review_templates
                    (id, code, name, version, kind, is_active, rating_scale_json, structure_json, created_at, updated_at)
                    VALUES (:id, :code, :name, 1, 'annual', 1, :scale, :structure, :now, :now)
                    """
                ),
                {
                    "id": template_id,
                    "code": FORM_CODE,
                    "name": FORM_TITLE,
                    "scale": scale,
                    "structure": structure,
                    "now": now,
                },
            )
        else:
            template_id = str(existing[0])

        # Backfill sheets missing template/stage
        sheets = connection.execute(
            text(
                """
                SELECT id, status, acknowledged_at, submitted_at, template_id, stage
                FROM performance_review_sheets
                WHERE is_active = 1
                """
            )
        ).fetchall()
        for row in sheets:
            sheet_id, status, acknowledged_at, submitted_at, tmpl, stage = row
            if acknowledged_at:
                mapped_stage = "acknowledged"
            elif status == "submitted" or submitted_at:
                mapped_stage = "final"
            else:
                mapped_stage = stage if stage not in (None, "") else "self"

            connection.execute(
                text(
                    """
                    UPDATE performance_review_sheets
                    SET template_id = COALESCE(template_id, :template_id),
                        template_version = COALESCE(template_version, 1),
                        stage = :stage
                    WHERE id = :id
                      AND (template_id IS NULL OR stage IS NULL OR stage = '' OR stage = 'self')
                    """
                ),
                {
                    "template_id": template_id,
                    "stage": mapped_stage,
                    "id": sheet_id,
                },
            )
            if tmpl is None:
                connection.execute(
                    text(
                        """
                        UPDATE performance_review_sheets
                        SET template_id = :template_id,
                            template_version = COALESCE(template_version, 1)
                        WHERE id = :id
                        """
                    ),
                    {"template_id": template_id, "id": sheet_id},
                )

        # Backfill cycles missing kind
        connection.execute(
            text(
                """
                UPDATE performance_review_cycles
                SET kind = 'annual'
                WHERE kind IS NULL OR kind = ''
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE performance_review_cycles
                SET template_id = :template_id
                WHERE template_id IS NULL
                """
            ),
            {"template_id": template_id},
        )
