"""R10 OIDC spike — status, link-only login, testing mode."""

import os

import pytest

from app.core.oidc import make_state, new_nonce, oidc_available
from app.models.models import User
from app.services import oidc_service
from tests.conftest import IDS, login


def test_oidc_status_disabled_by_default(client):
    response = client.get("/api/v1/auth/oidc/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["oidc_enabled_env"] is False


def test_oidc_login_404_when_disabled(client):
    response = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 404


def test_resolve_user_link_only(session):
    user, reason = oidc_service.resolve_user_for_oidc(
        session, subject="entra-oid-1", email="admin@prosohm.com"
    )
    assert reason is None
    assert user is not None
    assert user.email == "admin@prosohm.com"
    assert user.sso_subject == "entra-oid-1"
    session.commit()

    again, reason2 = oidc_service.resolve_user_for_oidc(
        session, subject="entra-oid-1", email="admin@prosohm.com"
    )
    assert reason2 is None
    assert again is not None
    assert again.id == user.id

    missing, miss_reason = oidc_service.resolve_user_for_oidc(
        session, subject="unknown", email="nobody@example.com"
    )
    assert missing is None
    assert miss_reason == "no_local_user"


@pytest.fixture
def oidc_testing_env(monkeypatch):
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("OIDC_TESTING", "true")
    # Clear discovery cache between tests
    import app.core.oidc as oidc_mod

    oidc_mod._discovery_cache = None
    yield
    oidc_mod._discovery_cache = None


def test_oidc_testing_callback_issues_token(client, session, oidc_testing_env):
    assert oidc_available() is True
    # Ensure feature.sso is on (enterprise seed)
    from app.models.commercial import PROSOHM_TENANT_ID
    from app.services import feature_flag_service, tenant_service

    tenant_service.ensure_prosohm_tenant(session)
    feature_flag_service.ensure_tenant_flags(session, PROSOHM_TENANT_ID)
    session.commit()

    status = client.get("/api/v1/auth/oidc/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is True

    nonce = new_nonce()
    state = make_state(nonce)
    # Drive testing authorize → callback chain
    start = client.get(
        f"/api/v1/auth/oidc/testing-authorize"
        f"?state={state}&nonce={nonce}&email=admin@prosohm.com&sub=entra-test-1",
        follow_redirects=False,
    )
    assert start.status_code == 302
    callback_url = start.headers["location"]
    assert "/auth/oidc/callback" in callback_url

    finish = client.get(callback_url, follow_redirects=False)
    assert finish.status_code == 302
    location = finish.headers["location"]
    assert "/login/sso#" in location
    assert "access_token=" in location

    session.expire_all()
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    assert admin.sso_subject == "entra-test-1"


def test_password_login_still_works(client):
    headers = login(client, "admin@prosohm.com")
    assert "Authorization" in headers
