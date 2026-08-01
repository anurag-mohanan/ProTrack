"""History CSV import packs + tenant create."""

from app.models.commercial import PROSOHM_TENANT_ID
from app.services import feature_flag_service, history_import_service, tenant_service
from tests.conftest import login


def _ensure(session):
    tenant_service.ensure_prosohm_tenant(session)
    feature_flag_service.ensure_tenant_flags(session, PROSOHM_TENANT_ID)
    session.commit()


def test_history_packs_and_employment_dry_run(client, session):
    _ensure(session)
    headers = login(client, "admin@prosohm.com")
    packs = client.get("/api/v1/imports/history/packs", headers=headers)
    assert packs.status_code == 200
    ids = {p["id"] for p in packs.json()}
    assert "employment" in ids
    assert "compensation" in ids
    assert "expenses" in ids

    template = client.get(
        "/api/v1/imports/history/packs/employment/template", headers=headers
    )
    assert template.status_code == 200
    assert "email" in template.text

    csv_body = (
        "email,joining_date,leaving_date,first_job_date,employment_type,designation\n"
        "admin@prosohm.com,2020-01-15,,,full_time,Administrator\n"
    )
    dry = client.post(
        "/api/v1/imports/history/packs/employment/import",
        headers=headers,
        files={"file": ("emp.csv", csv_body, "text/csv")},
        data={"dry_run": "true"},
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["updated"] == 1
    assert dry.json()["dry_run"] is True

    committed = client.post(
        "/api/v1/imports/history/packs/employment/import",
        headers=headers,
        files={"file": ("emp.csv", csv_body, "text/csv")},
        data={"dry_run": "false"},
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["updated"] == 1


def test_create_tenant(client, session):
    _ensure(session)
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/commercial/tenants",
        headers=headers,
        json={
            "slug": "acme-molds",
            "name": "Acme Molds",
            "edition": "business",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["slug"] == "acme-molds"
    assert body["edition"] == "business"

    listed = client.get("/api/v1/commercial/tenants", headers=headers)
    assert listed.status_code == 200
    assert any(t["slug"] == "acme-molds" for t in listed.json())

    dup = client.post(
        "/api/v1/commercial/tenants",
        headers=headers,
        json={"slug": "acme-molds", "name": "Dup", "edition": "trial"},
    )
    assert dup.status_code == 422
