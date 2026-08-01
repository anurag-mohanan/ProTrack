"""R10 M1 — tenant_id backfill on business tables."""

from uuid import UUID

from sqlalchemy import text

from app.db.tenant_scoped_tables import TENANT_SCOPED_TABLES
from app.models.commercial import PROSOHM_TENANT_ID
from app.models.models import Customer, Project, Role, User
from app.services import tenant_service


def _as_uuid(value) -> UUID:
    if isinstance(value, UUID):
        return value
    raw = str(value).replace("-", "")
    if len(raw) == 32:
        return UUID(raw)
    return UUID(str(value))


def test_phase70_backfills_core_tables(test_engine, session):
    tenant_service.ensure_prosohm_tenant(session)
    session.commit()

    from app.db.phase70_tenant_id_schema_sync import ensure_phase70_tenant_id_foundation

    ensure_phase70_tenant_id_foundation(test_engine)

    assert "users" in TENANT_SCOPED_TABLES
    for table in ("users", "projects", "customers", "roles"):
        nulls = session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL")
        ).scalar()
        assert nulls == 0, f"{table} still has null tenant_id"
        sample = session.execute(
            text(f"SELECT tenant_id FROM {table} LIMIT 5")
        ).fetchall()
        for (tid,) in sample:
            assert _as_uuid(tid) == PROSOHM_TENANT_ID, (
                f"{table} tenant_id={tid!r} expected {PROSOHM_TENANT_ID}"
            )


def test_orm_default_tenant_on_create(session):
    tenant_service.ensure_prosohm_tenant(session)
    role = Role(name="M1 Tenant Probe Role", description="probe")
    session.add(role)
    session.flush()
    assert role.tenant_id == PROSOHM_TENANT_ID

    customer = Customer(name="M1 Probe Customer", code="M1PROBE")
    session.add(customer)
    session.flush()
    assert customer.tenant_id == PROSOHM_TENANT_ID


def test_seeded_users_are_prosohm_tenant(session):
    users = session.query(User).all()
    assert users
    assert all(u.tenant_id == PROSOHM_TENANT_ID for u in users)
    projects = session.query(Project).all()
    assert projects
    assert all(p.tenant_id == PROSOHM_TENANT_ID for p in projects)
