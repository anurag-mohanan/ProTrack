"""R10 public API expand + webhook retries (ADR R10-008)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.models.commercial import PROSOHM_TENANT_ID
from app.models.integrations import WebhookDelivery
from app.services import api_key_service, feature_flag_service, tenant_service, webhook_service
from tests.conftest import login


def _ensure_flags(session):
    tenant_service.ensure_prosohm_tenant(session)
    feature_flag_service.ensure_tenant_flags(session, PROSOHM_TENANT_ID)
    session.commit()


def test_public_health_unauthenticated(client):
    response = client.get("/api/public/v1/health")
    assert response.status_code == 200
    assert response.json()["api"] == "public"


def test_public_projects_requires_api_key(client, session):
    _ensure_flags(session)
    denied = client.get("/api/public/v1/projects")
    assert denied.status_code == 401

    key, raw = api_key_service.create_api_key(session, name="Test key")
    session.commit()
    assert key.is_active

    ok = client.get(
        "/api/public/v1/projects",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert "items" in body
    assert body["count"] >= 1
    assert "execution_status" in body["items"][0]


def test_public_me_and_scoped_resources(client, session):
    _ensure_flags(session)
    _, raw = api_key_service.create_api_key(
        session,
        name="Broad key",
        scopes=["projects:read", "milestones:read", "users:read"],
    )
    session.commit()
    headers = {"Authorization": f"Bearer {raw}"}

    me = client.get("/api/public/v1/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["key_name"] == "Broad key"
    assert "milestones:read" in me.json()["scopes"]

    projects = client.get("/api/public/v1/projects", headers=headers).json()
    project_id = projects["items"][0]["id"]

    milestones = client.get(
        f"/api/public/v1/projects/{project_id}/milestones",
        headers=headers,
    )
    assert milestones.status_code == 200, milestones.text
    assert "items" in milestones.json()

    users = client.get("/api/public/v1/users", headers=headers)
    assert users.status_code == 200, users.text
    assert users.json()["count"] >= 1


def test_public_milestones_scope_required(client, session):
    _ensure_flags(session)
    _, raw = api_key_service.create_api_key(
        session, name="Projects only", scopes=["projects:read"]
    )
    session.commit()
    headers = {"Authorization": f"Bearer {raw}"}
    projects = client.get("/api/public/v1/projects", headers=headers).json()
    project_id = projects["items"][0]["id"]
    denied = client.get(
        f"/api/public/v1/projects/{project_id}/milestones",
        headers=headers,
    )
    assert denied.status_code == 403


def test_admin_create_and_revoke_api_key(client, session):
    _ensure_flags(session)
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/commercial/api-keys",
        headers=headers,
        json={"name": "UI key", "scopes": ["projects:read"]},
    )
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["raw_key"].startswith("pt_live_")
    key_id = data["id"]

    listed = client.get("/api/v1/commercial/api-keys", headers=headers)
    assert listed.status_code == 200
    assert any(row["id"] == key_id for row in listed.json())

    revoked = client.delete(f"/api/v1/commercial/api-keys/{key_id}", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["is_active"] is False


def test_webhook_create_and_ping_records_delivery(client, session):
    _ensure_flags(session)
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/commercial/webhooks",
        headers=headers,
        json={
            "name": "Test hook",
            "url": "https://hooks.example.test/protrack",
            "events": ["project.updated", "ping"],
        },
    )
    assert created.status_code == 200, created.text
    endpoint = created.json()
    assert endpoint["secret"]

    deliveries = webhook_service.emit_event(
        session,
        "ping",
        {"ok": True},
        deliver=False,
    )
    session.commit()
    assert deliveries
    assert deliveries[0].status == "pending"
    assert deliveries[0].event == "ping"
    assert deliveries[0].next_attempt_at is not None


def test_webhook_retry_schedules_backoff_then_process(client, session):
    _ensure_flags(session)
    headers = login(client, "admin@prosohm.com")
    created = client.post(
        "/api/v1/commercial/webhooks",
        headers=headers,
        json={
            "name": "Retry hook",
            "url": "https://hooks.example.test/retry",
            "events": ["ping"],
        },
    )
    assert created.status_code == 200, created.text

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "boom"

    with patch("app.services.webhook_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        deliveries = webhook_service.emit_event(session, "ping", {"n": 1}, deliver=True)
        session.commit()

    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.status == "pending"
    assert delivery.attempts == 1
    assert delivery.next_attempt_at is not None
    assert delivery.next_attempt_at > datetime.now(UTC).replace(tzinfo=None)

    # Not due yet — process should skip
    skipped = webhook_service.process_due_deliveries(session)
    session.commit()
    assert skipped == []

    # Make due and process successfully
    row = session.get(WebhookDelivery, delivery.id)
    row.next_attempt_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    session.add(row)
    session.commit()

    mock_ok = MagicMock()
    mock_ok.status_code = 200
    mock_ok.text = "ok"
    with patch("app.services.webhook_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_ok
        processed = client.post(
            "/api/v1/commercial/webhooks/process-retries",
            headers=headers,
        )
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert len(body) == 1
    assert body[0]["status"] == "delivered"
    assert body[0]["attempts"] == 2


def test_webhook_exhausts_to_dead(session):
    _ensure_flags(session)
    ep = webhook_service.create_endpoint(
        session,
        name="Dead hook",
        url="https://hooks.example.test/dead",
        events=["ping"],
    )
    session.flush()
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "down"

    with patch("app.services.webhook_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        deliveries = webhook_service.emit_event(session, "ping", {}, deliver=True)
        delivery = deliveries[0]
        delivery.max_attempts = 2
        session.add(delivery)
        session.flush()
        # Force due and attempt until dead
        for _ in range(5):
            delivery.next_attempt_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
                seconds=1
            )
            session.add(delivery)
            session.flush()
            webhook_service.process_due_deliveries(session, limit=10)
            session.refresh(delivery)
            if delivery.status == "dead":
                break

    assert delivery.status == "dead"
    assert delivery.attempts >= 2
