"""R10 tenant config pack — branding façade + terminology/numbering."""

from app.services import tenant_pack_service, tenant_service
from tests.conftest import login


def test_tenant_pack_includes_branding_and_catalog(client, session):
    headers = login(client, "admin@prosohm.com")
    response = client.get("/api/v1/commercial/me/pack", headers=headers)
    assert response.status_code == 200, response.text
    pack = response.json()
    assert pack["slug"] == "prosohm"
    assert pack["terminology"]["project"] == "Project"
    assert pack["terminology"]["tool_number"] == "Tool number"
    assert "part_description" in pack["terminology"]
    assert pack["terminology_catalog"]["quote"] == "Quote"
    assert pack["numbering_policy"]["stream_prefix_enabled"] is True
    assert "primary_color" in pack["branding"]
    assert pack["branding"]["theme_preset"]
    assert pack["company"]["company_name"]
    assert pack["sources"]["branding"] == "branding_settings"


def test_patch_terminology(client, session):
    headers = login(client, "admin@prosohm.com")
    patched = client.patch(
        "/api/v1/commercial/me/terminology",
        headers=headers,
        json={"terminology": {"tool_number": "Tool #", "project": "Job"}},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["terminology"]["tool_number"] == "Tool #"
    assert body["terminology"]["project"] == "Job"
    # catalog keys still present
    assert body["terminology"]["timesheet"] == "Timesheet"

    me = client.get("/api/v1/commercial/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["terminology"]["tool_number"] == "Tool #"


def test_patch_numbering(client):
    headers = login(client, "admin@prosohm.com")
    patched = client.patch(
        "/api/v1/commercial/me/numbering",
        headers=headers,
        json={"numbering_policy": {"quote_number_prefix": "QT", "stream_prefix_enabled": False}},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["numbering_policy"]["quote_number_prefix"] == "QT"
    assert body["numbering_policy"]["stream_prefix_enabled"] is False


def test_ensure_fills_missing_keys(session):
    tenant = tenant_service.ensure_prosohm_tenant(session)
    tenant.terminology_json = '{"project": "Project"}'
    session.add(tenant)
    session.flush()
    tenant_pack_service.ensure_tenant_config_defaults(session, tenant)
    session.commit()
    data = tenant_service.parse_json_dict(tenant.terminology_json)
    assert data["project"] == "Project"
    assert data["tool_number"] == "Tool number"
    assert data["quote"] == "Quote"
