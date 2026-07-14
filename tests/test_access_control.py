"""Tests for module access and special permission resolution."""

import json

from app.core.access_control import (
    MODULE_CALENDAR,
    MODULE_DASHBOARD,
    MODULE_PLANNING_BOARD,
    MODULE_PROJECTS,
    MODULE_REPORTS,
    MODULE_TIMESHEETS,
    SPECIAL_CREATE_PROJECTS,
    default_modules_for_role,
    resolve_user_modules,
    resolve_user_special_permissions,
    serialize_module_access,
)
from app.models.models import User
from tests.conftest import DEFAULT_PASSWORD, IDS, login


def test_default_modules_for_designer(session):
    user = session.get(User, IDS["user_anurag"])
    modules = resolve_user_modules(user, "Designer")
    assert MODULE_DASHBOARD in modules
    assert MODULE_PROJECTS in modules
    assert MODULE_TIMESHEETS in modules
    assert MODULE_REPORTS not in modules
    assert MODULE_CALENDAR not in modules
    assert MODULE_PLANNING_BOARD not in modules


def test_default_modules_calendar_for_leaders_only():
    designer = default_modules_for_role("Designer")
    junior = default_modules_for_role("Junior Designer")
    senior = default_modules_for_role("Senior Designer")
    surfacer = default_modules_for_role("Surfacer")
    em = default_modules_for_role("Engineering Manager")
    dl = default_modules_for_role("Design Leader")

    for staff in (designer, junior, senior, surfacer):
        assert MODULE_CALENDAR not in staff
        assert MODULE_PLANNING_BOARD not in staff

    assert MODULE_CALENDAR in em
    assert MODULE_CALENDAR in dl
    assert MODULE_PLANNING_BOARD not in em
    assert MODULE_PLANNING_BOARD not in dl


def test_custom_module_access_overrides_defaults(session):
    user = session.get(User, IDS["user_anurag"])
    user.module_access = serialize_module_access([MODULE_DASHBOARD, MODULE_REPORTS])
    session.add(user)
    session.commit()

    modules = resolve_user_modules(user, "Designer")
    assert modules == [MODULE_DASHBOARD, MODULE_REPORTS]


def test_custom_special_permissions(session):
    user = session.get(User, IDS["user_anurag"])
    user.special_permissions = json.dumps([SPECIAL_CREATE_PROJECTS])
    session.add(user)
    session.commit()

    permissions = resolve_user_special_permissions(user, "Designer")
    assert permissions == [SPECIAL_CREATE_PROJECTS]


def test_auth_me_includes_resolved_access(client, session):
    user = session.get(User, IDS["user_anurag"])
    user.module_access = serialize_module_access([MODULE_DASHBOARD, MODULE_PROJECTS])
    user.special_permissions = json.dumps([SPECIAL_CREATE_PROJECTS])
    session.add(user)
    session.commit()

    headers = login(client, "anurag@prosohm.com")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert MODULE_DASHBOARD in payload["module_access"]
    assert MODULE_PROJECTS in payload["module_access"]
    assert SPECIAL_CREATE_PROJECTS in payload["special_permissions"]


def test_user_update_persists_module_access(client, session):
    admin_headers = login(client, "admin@prosohm.com")
    user_id = IDS["user_anurag"]
    update = client.patch(
        f"/api/v1/users/{user_id}",
        headers=admin_headers,
        json={
            "module_access": [MODULE_DASHBOARD, MODULE_REPORTS],
            "special_permissions": [SPECIAL_CREATE_PROJECTS],
        },
    )
    assert update.status_code == 200

    user = session.get(User, user_id)
    modules = resolve_user_modules(user, "Designer")
    assert modules == [MODULE_DASHBOARD, MODULE_REPORTS]
    permissions = resolve_user_special_permissions(user, "Designer")
    assert permissions == [SPECIAL_CREATE_PROJECTS]


def test_system_health_admin_only(client):
    designer_headers = login(client, "anurag@prosohm.com")
    denied = client.get("/api/v1/system/health", headers=designer_headers)
    assert denied.status_code == 403

    admin_headers = login(client, "admin@prosohm.com")
    allowed = client.get("/api/v1/system/health", headers=admin_headers)
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["backend_status"] == "ok"
    assert payload["release_candidate"]
