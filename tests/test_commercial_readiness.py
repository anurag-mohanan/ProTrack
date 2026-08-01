"""R10-010 commercial readiness hub + admin SSO gate."""

from app.models.commercial import PROSOHM_TENANT_ID
from app.services import (
    commercial_readiness_service,
    feature_flag_service,
    tenant_service,
)
from app.services.security_policy_service import get_effective_policy, update_policy
from tests.conftest import login


def _ensure(session):
    tenant_service.ensure_prosohm_tenant(session)
    feature_flag_service.ensure_tenant_flags(session, PROSOHM_TENANT_ID)
    commercial_readiness_service.ensure_trust_controls(session, PROSOHM_TENANT_ID)
    session.commit()


def test_readiness_summary_and_trust_seed(client, session):
    _ensure(session)
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/commercial/readiness/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trust_must_fix_open"] >= 1
    assert body["audit_retention_days"] >= 1
    assert any(d["path"].endswith("DPA_DRAFT.md") for d in body["documents"])


def test_signoff_and_partner_flow(client, session):
    _ensure(session)
    headers = login(client, "admin@prosohm.com")
    signed = client.post(
        "/api/v1/commercial/readiness/signoffs",
        headers=headers,
        json={
            "key": "vision_d_ceo",
            "signer_name": "Test CEO",
            "signer_role": "CEO",
        },
    )
    assert signed.status_code == 200, signed.text

    partner = client.post(
        "/api/v1/commercial/readiness/partners",
        headers=headers,
        json={
            "icp": "mold",
            "company_name": "Acme Molds",
            "status": "draft",
        },
    )
    assert partner.status_code == 200, partner.text
    partner_id = partner.json()["id"]

    advanced = client.patch(
        f"/api/v1/commercial/readiness/partners/{partner_id}",
        headers=headers,
        json={"status": "loi_sent"},
    )
    assert advanced.status_code == 200
    assert advanced.json()["status"] == "loi_sent"

    summary = client.get("/api/v1/commercial/readiness/summary", headers=headers).json()
    assert summary["vision_d_ceo_signed"] is True
    assert summary["partners_by_status"].get("loi_sent", 0) >= 1


def test_trust_check_patch_and_access_review(client, session):
    _ensure(session)
    headers = login(client, "admin@prosohm.com")
    patched = client.patch(
        "/api/v1/commercial/readiness/trust-checks/S5",
        headers=headers,
        json={"status": "done", "evidence_notes": "Runbook drafted"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "done"

    review = client.get("/api/v1/commercial/readiness/access-review", headers=headers)
    assert review.status_code == 200
    body = review.json()
    assert body["count"] >= 1
    assert any(item["email"] == "admin@prosohm.com" for item in body["items"])

    csv_resp = client.get(
        "/api/v1/commercial/readiness/access-review?format=csv",
        headers=headers,
    )
    assert csv_resp.status_code == 200
    assert "email" in csv_resp.text.splitlines()[0]


def test_admin_password_blocked_when_sso_required(client, session):
    _ensure(session)
    headers = login(client, "admin@prosohm.com")
    toggled = client.put(
        "/api/v1/commercial/readiness/require-sso-for-admins",
        headers=headers,
        json={"enabled": True},
    )
    assert toggled.status_code == 200, toggled.text
    assert toggled.json()["require_sso_for_admins"] is True
    assert get_effective_policy(session).require_sso_for_admins is True

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@prosohm.com", "password": "Password@123"},
    )
    assert blocked.status_code == 403
    assert "SSO" in blocked.json()["detail"]

    # Restore for other tests in process
    update_policy(session, {"require_sso_for_admins": False}, None)
