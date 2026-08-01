"""R10 commercial spine — tenant + feature flags."""

from app.core.editions import FLAG_CATALOG
from app.models.commercial import PROSOHM_TENANT_ID
from app.services import feature_flag_service, tenant_service
from tests.conftest import login


def test_prosohm_tenant_seeded_and_enterprise_flags_on(client, session):
    headers = login(client, "admin@prosohm.com")

    me = client.get("/api/v1/commercial/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["slug"] == "prosohm"
    assert body["edition"] == "enterprise"
    assert body["id"] == str(PROSOHM_TENANT_ID)
    assert body["terminology"].get("project") == "Project"

    tenants = client.get("/api/v1/commercial/tenants", headers=headers)
    assert tenants.status_code == 200
    assert any(t["slug"] == "prosohm" for t in tenants.json())

    flags = client.get(
        f"/api/v1/commercial/tenants/{PROSOHM_TENANT_ID}/flags",
        headers=headers,
    )
    assert flags.status_code == 200, flags.text
    rows = flags.json()
    assert len(rows) == len(FLAG_CATALOG)
    assert all(row["enabled"] is True for row in rows)

    # Override one flag OFF then ON
    key = "module.ai"
    off = client.patch(
        f"/api/v1/commercial/tenants/{PROSOHM_TENANT_ID}/flags/{key}",
        headers=headers,
        json={"enabled": False},
    )
    assert off.status_code == 200
    assert off.json()["enabled"] is False
    session.expire_all()
    assert feature_flag_service.is_enabled(session, key, tenant_id=PROSOHM_TENANT_ID) is False

    on = client.patch(
        f"/api/v1/commercial/tenants/{PROSOHM_TENANT_ID}/flags/{key}",
        headers=headers,
        json={"enabled": True},
    )
    assert on.status_code == 200
    assert on.json()["enabled"] is True


def test_edition_catalog(client):
    headers = login(client, "admin@prosohm.com")
    catalog = client.get("/api/v1/commercial/editions", headers=headers)
    assert catalog.status_code == 200
    data = catalog.json()
    assert "enterprise" in data["editions"]
    assert "module.finance" in data["flag_catalog"]
    assert data["defaults_by_edition"]["trial"]["module.finance"] is False
    assert data["defaults_by_edition"]["enterprise"]["module.finance"] is True


def test_ensure_prosohm_idempotent(session):
    a = tenant_service.ensure_prosohm_tenant(session)
    b = tenant_service.ensure_prosohm_tenant(session)
    session.commit()
    assert a.id == b.id == PROSOHM_TENANT_ID
