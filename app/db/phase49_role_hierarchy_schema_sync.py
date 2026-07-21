"""Phase 49 — Role hierarchy and standardized roles per department.

Adds hierarchy placement columns to ``roles`` (``org_department_id``,
``rank``, ``parent_role_id``, ``is_active``), seeds an Accounts / Finance
org department, and get-or-creates a standardized role set for Engineering,
Sales, HR / Administration, Accounts, IT, and Management. Existing
permission-bearing roles (Engineering Manager, Design Leader, the legacy
Designer family, Admin, Read Only, Planning Board) are kept intact and simply
placed in the hierarchy — no renames, so access control is unaffected.

Lower ``rank`` = more senior (top of the chart). New Engineering roles are
aliased to their existing permission equivalents in ``app.core.access_control``
so they behave correctly everywhere without touching call sites.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# New org department introduced in this phase (upsert by code).
ACCOUNTS_DEPARTMENT = ("accounts", "Accounts / Finance", "Accounting and finance operations", "#5d4037", 35)

# (name, description, dept_code | None, rank, parent_name | None)
# get-or-create by name — covers both brand-new roles and placement of
# already-seeded roles. Order matters only for readability; parents are
# resolved by name after every role exists.
ROLE_SEED: list[tuple[str, str, str | None, int, str | None]] = [
    # Management
    ("Managing Director", "Company managing director", "management", 1, None),
    # Engineering
    ("Director of Engineering", "Heads the Engineering department", "engineering", 2, "Managing Director"),
    ("Engineering Manager", "Engineering delivery management", "engineering", 3, "Director of Engineering"),
    ("Design Leader", "Design leadership across teams", "engineering", 4, "Engineering Manager"),
    ("Team Leader", "Leads a delivery team", "engineering", 5, "Design Leader"),
    ("Senior Design Engineer", "Senior engineering design", "engineering", 6, "Team Leader"),
    ("Design Engineer", "Engineering design", "engineering", 7, "Senior Design Engineer"),
    ("Junior Design Engineer", "Junior engineering design", "engineering", 8, "Design Engineer"),
    ("Trainee Design Engineer", "Trainee engineering design", "engineering", 9, "Junior Design Engineer"),
    # Legacy Engineering roles retained for existing users / permissions
    ("Senior Designer", "Senior design work", "engineering", 20, "Design Leader"),
    ("Designer", "Design work and time logging", "engineering", 21, "Senior Designer"),
    ("Junior Designer", "Entry-level design work", "engineering", 22, "Designer"),
    ("Surfacer", "Surfacing specialist", "engineering", 23, "Design Leader"),
    # Sales
    ("Director of Sales", "Heads the Sales department", "sales", 2, "Managing Director"),
    ("Sales Manager", "Manages sales operations", "sales", 3, "Director of Sales"),
    ("Sales Executive", "Sales execution", "sales", 4, "Sales Manager"),
    ("Sales Assistant", "Sales support", "sales", 5, "Sales Executive"),
    # HR / Administration
    ("Director of HR", "Heads HR / Administration", "hr_admin", 2, "Managing Director"),
    ("HR Manager", "Manages HR operations", "hr_admin", 3, "Director of HR"),
    ("HR Executive", "HR execution", "hr_admin", 4, "HR Manager"),
    ("HR", "Human resources", "hr_admin", 5, "HR Manager"),
    ("Office Administrator", "Office administration", "hr_admin", 6, "HR Manager"),
    ("HR Assistant", "HR support", "hr_admin", 7, "HR Executive"),
    # Accounts / Finance
    ("Director of Accounts", "Heads Accounts / Finance", "accounts", 2, "Managing Director"),
    ("Accounts Manager", "Manages accounts operations", "accounts", 3, "Director of Accounts"),
    ("Senior Accountant", "Senior accounting", "accounts", 4, "Accounts Manager"),
    ("Accountant", "Accounting", "accounts", 5, "Senior Accountant"),
    ("Accounts Executive", "Accounts execution", "accounts", 6, "Accountant"),
    ("Accounts Assistant", "Accounts support", "accounts", 7, "Accounts Executive"),
    # IT
    ("Director of IT", "Heads the IT department", "it", 2, "Managing Director"),
    ("IT Manager", "Manages IT operations", "it", 3, "Director of IT"),
    ("System Administrator", "Systems and infrastructure administration", "it", 4, "IT Manager"),
    ("IT Executive", "IT execution", "it", 5, "System Administrator"),
    ("IT Support Engineer", "IT support", "it", 6, "IT Executive"),
    # Cross-cutting / system roles — no department, sorted last
    ("Admin", "Full system administration", None, 900, None),
    ("Read Only", "View-only access", None, 901, None),
    ("Planning Board", "Planning board wall account", None, 902, None),
]


def _sqlite_has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    with engine.connect() as connection:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _add_column_sqlite(connection, table: str, column: str, ddl: str, engine: Engine) -> None:
    if not _sqlite_has_column(engine, table, column):
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def ensure_phase49_role_hierarchy_columns(engine: Engine) -> None:
    """Add hierarchy columns to ``roles`` (safe to run before any seeding)."""
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            _add_column_sqlite(connection, "roles", "org_department_id", "CHAR(36) NULL", engine)
            _add_column_sqlite(connection, "roles", "rank", "INTEGER NOT NULL DEFAULT 100", engine)
            _add_column_sqlite(connection, "roles", "parent_role_id", "CHAR(36) NULL", engine)
            _add_column_sqlite(connection, "roles", "is_active", "BOOLEAN NOT NULL DEFAULT 1", engine)
        else:
            connection.execute(
                text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS org_department_id UUID NULL")
            )
            connection.execute(
                text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS rank INTEGER NOT NULL DEFAULT 100")
            )
            connection.execute(
                text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS parent_role_id UUID NULL")
            )
            connection.execute(
                text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
            )


def ensure_phase49_role_hierarchy_seed(engine: Engine) -> None:
    """Seed the Accounts department + standardized roles and place them.

    Uses the ORM (not raw SQL) so UUID primary keys are stored in the exact
    format SQLAlchemy expects — otherwise ``Session.get(Role, id)`` cannot
    resolve seeded roles. Get-or-create by name, so it composes with any
    pre-existing roles (app startup seeders or the test fixtures). Assumes the
    hierarchy columns already exist (see
    :func:`ensure_phase49_role_hierarchy_columns`).
    """
    from sqlalchemy.orm import sessionmaker

    from app.models.models import OrgDepartment, Role, User

    session = sessionmaker(bind=engine)()
    try:
        # --- Ensure the Accounts / Finance department exists (by code) ---
        code, name, description, colour, sort_order = ACCOUNTS_DEPARTMENT
        accounts = session.query(OrgDepartment).filter_by(code=code).one_or_none()
        if accounts is None:
            session.add(
                OrgDepartment(
                    code=code,
                    name=name,
                    description=description,
                    colour=colour,
                    sort_order=sort_order,
                    is_active=True,
                )
            )
            session.flush()

        dept_ids = {
            dept.code: dept.id for dept in session.query(OrgDepartment).all()
        }

        # --- Pass 1: get-or-create every seed role by name ---
        roles_by_name: dict[str, Role] = {}
        for role_name, role_desc, _dept_code, _rank, _parent in ROLE_SEED:
            role = session.query(Role).filter_by(name=role_name).one_or_none()
            if role is None:
                role = Role(name=role_name, description=role_desc)
                session.add(role)
            roles_by_name[role_name] = role
        session.flush()

        # Refresh the full name->role map so parents resolve to real rows.
        for role in session.query(Role).all():
            roles_by_name[role.name] = role

        # --- Pass 2: place each role in the hierarchy ---
        for role_name, _role_desc, dept_code, rank, parent_name in ROLE_SEED:
            role = roles_by_name[role_name]
            role.org_department_id = dept_ids.get(dept_code) if dept_code else None
            role.rank = rank
            role.parent_role_id = (
                roles_by_name[parent_name].id if parent_name else None
            )
            role.is_active = True

        # --- Managing Director heads the Management department when unset ---
        management = session.query(OrgDepartment).filter_by(code="management").one_or_none()
        if management is not None and management.head_user_id is None:
            md_role = roles_by_name.get("Managing Director")
            if md_role is not None:
                md_user = (
                    session.query(User)
                    .filter(
                        User.role_id == md_role.id,
                        User.is_deleted.is_(False),
                        User.is_active.is_(True),
                    )
                    .order_by(User.first_name, User.last_name)
                    .first()
                )
                if md_user is not None:
                    management.head_user_id = md_user.id

        session.commit()
    finally:
        session.close()


def ensure_phase49_role_hierarchy_foundation(engine: Engine) -> None:
    """Full phase 49: add columns then seed / place standardized roles."""
    ensure_phase49_role_hierarchy_columns(engine)
    ensure_phase49_role_hierarchy_seed(engine)
