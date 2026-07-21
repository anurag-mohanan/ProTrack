"""Phase 51 — Standardized organization departments + Managing Director at top.

Two jobs, both idempotent and safe to run on every startup:

1. **UUID normalization (SQLite only).** ``phase46`` seeded ``org_departments``
   via raw SQL using dashed UUID strings, while SQLAlchemy's ``Uuid`` type binds
   and stores the *un-dashed* 32-char hex form on SQLite. That mismatch breaks
   ORM primary-key operations (updates, ``session.get``) on department rows —
   which the new department CRUD / assignment endpoints rely on. We rewrite the
   department ids and every column that references them to the un-dashed form so
   ORM and raw rows agree. PostgreSQL uses native UUIDs and needs no fix.

2. **Standardization.** Normalizes the department display names to a single
   standardized list (Management, Engineering, Sales, Accounts, Human Resource,
   IT) — renaming the legacy "HR / Administration" → "Human Resource" and
   "Accounts / Finance" → "Accounts" while keeping the stable ``code`` and every
   member/team link. Also guarantees the Managing Director heads the Management
   department so the organization chart always has a company root.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# (code, name, description, colour, sort_order) — update by ``code``.
STANDARD_DEPARTMENTS: list[tuple[str, str, str, str, int]] = [
    ("management", "Management", "Executive and corporate leadership", "#455a64", 10),
    ("engineering", "Engineering", "Delivery teams, engineering, and design leadership", "#1565c0", 20),
    ("sales", "Sales", "Commercial and business development", "#6a1b9a", 30),
    ("accounts", "Accounts", "Accounting and finance operations", "#5d4037", 35),
    ("hr_admin", "Human Resource", "People operations and HR administration", "#00695c", 40),
    ("it", "IT", "Systems, platforms, and infrastructure", "#ef6c00", 50),
]

MANAGING_DIRECTOR_ROLE = "Managing Director"

# Un-dash any legacy dashed UUIDs so they match the ORM ``Uuid`` storage form.
_NORMALIZE_STATEMENTS = (
    "UPDATE roles SET org_department_id = REPLACE(org_department_id, '-', '') "
    "WHERE org_department_id LIKE '%-%'",
    "UPDATE users SET org_department_id = REPLACE(org_department_id, '-', '') "
    "WHERE org_department_id LIKE '%-%'",
    "UPDATE teams SET org_department_id = REPLACE(org_department_id, '-', '') "
    "WHERE org_department_id LIKE '%-%'",
    "UPDATE org_departments SET head_user_id = REPLACE(head_user_id, '-', '') "
    "WHERE head_user_id LIKE '%-%'",
    "UPDATE org_departments SET id = REPLACE(id, '-', '') WHERE id LIKE '%-%'",
)


def ensure_phase51_department_standardization(engine: Engine) -> None:
    """Normalize department UUIDs (SQLite), standardize names, set MD head."""
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            for statement in _NORMALIZE_STATEMENTS:
                connection.execute(text(statement))

        for code, name, description, colour, sort_order in STANDARD_DEPARTMENTS:
            connection.execute(
                text(
                    """
                    UPDATE org_departments
                    SET name = :name,
                        description = :description,
                        colour = :colour,
                        sort_order = :sort_order,
                        is_active = :is_active
                    WHERE code = :code
                    """
                ),
                {
                    "name": name,
                    "description": description,
                    "colour": colour,
                    "sort_order": sort_order,
                    "is_active": True,
                    "code": code,
                },
            )

        head_row = connection.execute(
            text("SELECT head_user_id FROM org_departments WHERE code = 'management'")
        ).fetchone()
        if head_row is not None and (head_row[0] is None or head_row[0] == ""):
            md_row = connection.execute(
                text(
                    """
                    SELECT u.id
                    FROM users u
                    JOIN roles r ON r.id = u.role_id
                    WHERE r.name = :md_role
                      AND u.is_deleted = 0
                      AND u.is_active = 1
                    ORDER BY u.first_name, u.last_name
                    LIMIT 1
                    """
                ),
                {"md_role": MANAGING_DIRECTOR_ROLE},
            ).fetchone()
            if md_row is not None:
                connection.execute(
                    text(
                        "UPDATE org_departments SET head_user_id = :uid "
                        "WHERE code = 'management'"
                    ),
                    {"uid": md_row[0]},
                )
