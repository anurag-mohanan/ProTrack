"""R10 M1c — ORM tenant query filter."""

import uuid

from sqlalchemy import select

from app.core.request_context import set_tenant_id
from app.db.tenant_filter import (
    register_tenant_filter,
    resolve_effective_tenant_id,
    without_tenant_filter,
)
from app.models.commercial import PROSOHM_TENANT_ID, Tenant
from app.models.models import Role, User
from app.services import tenant_service
from tests.conftest import IDS


def test_filter_registered_and_default_prosohm():
    register_tenant_filter()
    set_tenant_id(None)
    assert resolve_effective_tenant_id() == PROSOHM_TENANT_ID


def test_orm_hides_other_tenant_users(session):
    register_tenant_filter()
    set_tenant_id(None)
    tenant_service.ensure_prosohm_tenant(session)
    other_id = uuid.uuid4()
    session.add(
        Tenant(
            id=other_id,
            slug="m1c-other",
            name="M1c Other",
            edition="trial",
            is_active=True,
        )
    )
    session.flush()

    role = session.get(Role, IDS["role_admin"])
    assert role is not None
    foreign = User(
        role_id=role.id,
        email="foreign@m1c.test",
        password_hash="x",
        first_name="Foreign",
        last_name="User",
        is_active=True,
        tenant_id=other_id,
    )
    try:
        with without_tenant_filter():
            session.add(foreign)
            session.flush()
            foreign_id = foreign.id
            session.expunge(foreign)

        set_tenant_id(PROSOHM_TENANT_ID)
        hidden = session.scalar(select(User).where(User.id == foreign_id))
        assert hidden is None
        emails = {
            u.email
            for u in session.scalars(
                select(User).where(User.email == "foreign@m1c.test")
            ).all()
        }
        assert emails == set()

        set_tenant_id(other_id)
        found = session.scalar(select(User).where(User.id == foreign_id))
        assert found is not None
        assert found.email == "foreign@m1c.test"
    finally:
        set_tenant_id(None)


def test_without_tenant_filter_sees_all(session):
    register_tenant_filter()
    set_tenant_id(None)
    tenant_service.ensure_prosohm_tenant(session)
    other_id = uuid.uuid4()
    session.add(
        Tenant(
            id=other_id,
            slug="m1c-optout",
            name="M1c Optout",
            edition="trial",
            is_active=True,
        )
    )
    session.flush()
    role = session.get(Role, IDS["role_admin"])
    foreign = User(
        role_id=role.id,
        email="optout@m1c.test",
        password_hash="x",
        first_name="Opt",
        last_name="Out",
        is_active=True,
        tenant_id=other_id,
    )
    try:
        with without_tenant_filter():
            session.add(foreign)
            session.flush()
            foreign_id = foreign.id
            session.expunge(foreign)

        set_tenant_id(PROSOHM_TENANT_ID)
        with without_tenant_filter():
            assert (
                session.scalar(select(User).where(User.id == foreign_id)) is not None
            )
    finally:
        set_tenant_id(None)


def test_flush_rejects_cross_tenant_write(session):
    register_tenant_filter()
    set_tenant_id(None)
    tenant_service.ensure_prosohm_tenant(session)
    other_id = uuid.uuid4()
    session.add(
        Tenant(
            id=other_id,
            slug="m1c-write",
            name="M1c Write",
            edition="trial",
            is_active=True,
        )
    )
    session.flush()
    role = session.get(Role, IDS["role_admin"])
    set_tenant_id(PROSOHM_TENANT_ID)
    bad = User(
        role_id=role.id,
        email="badwrite@m1c.test",
        password_hash="x",
        first_name="Bad",
        last_name="Write",
        is_active=True,
        tenant_id=other_id,
    )
    session.add(bad)
    try:
        try:
            session.flush()
            raised = False
        except ValueError as exc:
            raised = True
            assert "does not match effective tenant" in str(exc)
            session.rollback()
        assert raised
    finally:
        set_tenant_id(None)
