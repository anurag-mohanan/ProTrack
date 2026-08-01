"""R10 M1b — tenant-scoped unique constraints."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.phase71_tenant_unique_schema_sync import ensure_phase71_tenant_unique_foundation
from app.db.tenant_unique_constraints import TENANT_UNIQUE_SPECS
from app.models.commercial import PROSOHM_TENANT_ID, Tenant
from app.models.models import Role, User
from app.services import tenant_service
from tests.conftest import IDS


def test_tenant_unique_catalog_covers_core_keys():
    names = {s.name for s in TENANT_UNIQUE_SPECS}
    assert "uq_users_tenant_email" in names
    assert "uq_projects_tenant_tool_number" in names
    assert "uq_roles_tenant_name" in names
    assert "uq_company_settings_tenant" in names


def test_phase71_idempotent(test_engine):
    ensure_phase71_tenant_unique_foundation(test_engine)
    ensure_phase71_tenant_unique_foundation(test_engine)


def test_same_email_allowed_across_tenants(session):
    from app.db.tenant_filter import without_tenant_filter

    tenant_service.ensure_prosohm_tenant(session)
    other = Tenant(
        id=uuid.uuid4(),
        slug="acme-demo",
        name="Acme Demo",
        edition="trial",
        is_active=True,
    )
    session.add(other)
    session.flush()

    role = session.get(Role, IDS["role_admin"])
    assert role is not None

    twin = User(
        role_id=role.id,
        email="admin@prosohm.com",  # same as seeded Prosohm admin
        password_hash="x",
        first_name="Acme",
        last_name="Admin",
        is_active=True,
        tenant_id=other.id,
    )
    with without_tenant_filter():
        session.add(twin)
        session.flush()
    assert twin.tenant_id == other.id
    assert twin.email == "admin@prosohm.com"


def test_same_email_rejected_within_tenant(session):
    tenant_service.ensure_prosohm_tenant(session)
    role = session.get(Role, IDS["role_admin"])
    assert role is not None
    dup = User(
        role_id=role.id,
        email="admin@prosohm.com",
        password_hash="x",
        first_name="Dup",
        last_name="User",
        is_active=True,
        tenant_id=PROSOHM_TENANT_ID,
    )
    session.add(dup)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
