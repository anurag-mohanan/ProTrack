"""Managing Director / executive-tier access profile (phase 52).

The MD (and the Director tier) are seeded into the role hierarchy but were
previously unwired into access control, so an MD login fell back to
Designer-level access. These tests lock in the executive profile: company-wide
visibility, financial-field access, top-level (level-2) compensation approval,
and the org chart — but NOT Admin's destructive / system-administration powers.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.access_control import (
    EXECUTIVE_MODULES,
    MODULE_FINANCIAL_PLANNING,
    MODULE_HUMAN_RESOURCES,
    MODULE_REPORTS_ANALYTICS,
    MODULE_SYSTEM_ADMINISTRATION,
    SPECIAL_BUDGET_APPROVAL,
    SPECIAL_FINANCIAL_APPROVAL,
    SPECIAL_MANAGE_USERS,
    SPECIAL_VIEW_SALARY,
    resolve_user_modules,
    resolve_user_special_permissions,
)
from app.core.field_security import (
    can_view_budget,
    can_view_cost,
    can_view_profitability,
    can_view_salary,
)
from app.core.permissions import (
    can_access_administration,
    can_manage_users,
    is_admin,
)
from app.core.security import hash_password
from app.core.team_access import (
    get_accessible_team_ids,
    user_can_view_organization_chart,
)
from app.models.models import Role, User
from app.services.compensation_change_service import can_approve_l2
from tests.conftest import DEFAULT_PASSWORD, IDS, login

MD_ROLE = "Managing Director"


def _make_md(session, email: str = "md.access@prosohm.com") -> User:
    role = session.scalar(select(Role).where(Role.name == MD_ROLE))
    assert role is not None, "phase49 should seed the Managing Director role"
    md = User(
        id=uuid.uuid4(),
        role_id=role.id,
        email=email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        first_name="Maya",
        last_name="Chief",
        designation=MD_ROLE,
        is_active=True,
    )
    session.add(md)
    session.commit()
    session.refresh(md)
    return md


# ---------------------------------------------------------------------------
# Module / special resolution
# ---------------------------------------------------------------------------
def test_md_resolves_full_executive_module_set(session):
    md = _make_md(session)
    modules = set(resolve_user_modules(md, MD_ROLE))
    assert modules == set(EXECUTIVE_MODULES)
    # Company cockpit modules present…
    assert MODULE_FINANCIAL_PLANNING in modules
    assert MODULE_HUMAN_RESOURCES in modules
    assert MODULE_REPORTS_ANALYTICS in modules
    # …but system administration stays with Admin / IT.
    assert MODULE_SYSTEM_ADMINISTRATION not in modules


def test_md_resolves_executive_specials_without_admin_powers(session):
    md = _make_md(session)
    specials = set(resolve_user_special_permissions(md, MD_ROLE))
    assert SPECIAL_FINANCIAL_APPROVAL in specials
    assert SPECIAL_BUDGET_APPROVAL in specials
    assert SPECIAL_VIEW_SALARY in specials
    # MD is an oversight authority, not a user administrator.
    assert SPECIAL_MANAGE_USERS not in specials


def test_md_is_not_an_administrator(session):
    md = _make_md(session)
    assert is_admin(session, md) is False
    assert can_manage_users(session, md) is False
    assert can_access_administration(session, md) is False


# ---------------------------------------------------------------------------
# Field-level financial visibility
# ---------------------------------------------------------------------------
def test_md_sees_all_financial_fields(session):
    md = _make_md(session)
    assert can_view_salary(md, MD_ROLE) is True
    assert can_view_cost(md, MD_ROLE) is True
    assert can_view_budget(md, MD_ROLE) is True
    assert can_view_profitability(md, MD_ROLE) is True


# ---------------------------------------------------------------------------
# Company-wide scope + organization chart
# ---------------------------------------------------------------------------
def test_md_has_company_wide_team_scope(session):
    md = _make_md(session)
    # None == unrestricted (whole company).
    assert get_accessible_team_ids(session, md) is None


def test_md_can_view_organization_chart(session):
    md = _make_md(session)
    assert user_can_view_organization_chart(session, md) is True


# ---------------------------------------------------------------------------
# Compensation — level-2 (final) approval authority
# ---------------------------------------------------------------------------
def test_md_can_give_level_2_compensation_approval(session):
    md = _make_md(session)
    employee = session.get(User, IDS["user_binil"])
    assert employee is not None
    assert can_approve_l2(session, md, employee) is True


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------
def test_md_me_endpoint_reports_executive_access(client, session):
    md = _make_md(session, email="md.api@prosohm.com")
    headers = login(client, "md.api@prosohm.com")

    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    # /me returns the resolved module set under ``module_access``.
    modules = set(payload["module_access"])
    assert MODULE_FINANCIAL_PLANNING in modules
    assert MODULE_HUMAN_RESOURCES in modules
    assert MODULE_REPORTS_ANALYTICS in modules
    assert MODULE_SYSTEM_ADMINISTRATION not in modules
    assert payload["can_view_organization_chart"] is True
    assert md.email == "md.api@prosohm.com"


def test_md_can_open_finance_dashboard(client, session):
    _make_md(session, email="md.finance@prosohm.com")
    headers = login(client, "md.finance@prosohm.com")
    response = client.get("/api/v1/finance/dashboard", headers=headers)
    assert response.status_code == 200, response.text


def test_md_cannot_create_org_department(client, session):
    """System-administration writes remain Admin-only, even for the MD."""
    _make_md(session, email="md.noadmin@prosohm.com")
    headers = login(client, "md.noadmin@prosohm.com")
    response = client.post(
        "/api/v1/org-departments",
        headers=headers,
        json={"code": "md_probe", "name": "MD Probe Dept"},
    )
    assert response.status_code == 403, response.text
