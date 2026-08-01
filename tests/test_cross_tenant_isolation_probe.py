"""Continuous cross-tenant isolation probe (SOC2 S11 / R10)."""

import uuid

from sqlalchemy import select

from app.core.request_context import set_tenant_id
from app.db.tenant_filter import register_tenant_filter, without_tenant_filter
from app.models.commercial import PROSOHM_TENANT_ID, Tenant
from app.models.models import Customer, Project
from app.services import tenant_service


def test_cross_tenant_projects_hidden(session):
    """Second tenant must not see Prosohm projects via ORM lists."""
    register_tenant_filter()
    tenant_service.ensure_prosohm_tenant(session)
    other_id = uuid.uuid4()
    session.add(
        Tenant(
            id=other_id,
            slug="probe-other",
            name="Probe Other",
            edition="trial",
            is_active=True,
        )
    )
    session.flush()

    set_tenant_id(PROSOHM_TENANT_ID)
    prosohm_projects = list(
        session.scalars(
            select(Project).where(Project.is_deleted.is_(False)).limit(5)
        ).all()
    )
    assert prosohm_projects, "seed expects at least one Prosohm project"

    set_tenant_id(other_id)
    leaked = list(
        session.scalars(
            select(Project).where(Project.id == prosohm_projects[0].id)
        ).all()
    )
    assert leaked == []

    # Opt-out still sees rows (ops/admin scripts)
    with without_tenant_filter():
        found = session.get(Project, prosohm_projects[0].id)
        assert found is not None

    set_tenant_id(None)


def test_cross_tenant_customer_isolation(session):
    register_tenant_filter()
    tenant_service.ensure_prosohm_tenant(session)
    other_id = uuid.uuid4()
    with without_tenant_filter():
        session.add(
            Tenant(
                id=other_id,
                slug="probe-cust",
                name="Probe Cust",
                edition="trial",
                is_active=True,
            )
        )
        session.flush()
        foreign = Customer(
            code="PROBE-X",
            name="Foreign Customer",
            tenant_id=other_id,
        )
        session.add(foreign)
        session.flush()
        foreign_id = foreign.id

    set_tenant_id(PROSOHM_TENANT_ID)
    assert session.scalar(select(Customer).where(Customer.id == foreign_id)) is None

    set_tenant_id(other_id)
    assert session.scalar(select(Customer).where(Customer.id == foreign_id)) is not None
    set_tenant_id(None)
