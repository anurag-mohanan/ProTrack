"""Outbound webhooks — register endpoints, emit signed events, retry with backoff."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.request_context import get_tenant_id
from app.models.commercial import PROSOHM_TENANT_ID
from app.models.integrations import WebhookDelivery, WebhookEndpoint

def _utc_now() -> datetime:
    """Naive UTC for SQLite-friendly DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)

KNOWN_EVENTS = (
    "project.created",
    "project.updated",
    "project.completed",
    "milestone.updated",
    "ping",
)

DEFAULT_MAX_ATTEMPTS = 5
STATUS_PENDING = "pending"
STATUS_DELIVERED = "delivered"
STATUS_DEAD = "dead"


def _dump(data: list | dict) -> str:
    return json.dumps(data, ensure_ascii=True, default=str)


def parse_events(row: WebhookEndpoint) -> list[str]:
    try:
        data = json.loads(row.events_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def backoff_seconds(attempt_number: int) -> int:
    """Exponential backoff after attempt N (1-based): 60, 120, 240, … capped at 1h."""
    n = max(1, attempt_number)
    return min(60 * (2 ** (n - 1)), 3600)


def create_endpoint(
    db: Session,
    *,
    name: str,
    url: str,
    events: list[str] | None = None,
    description: str | None = None,
    tenant_id: UUID | None = None,
) -> WebhookEndpoint:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    selected = [e for e in (events or ["project.updated"]) if e in KNOWN_EVENTS]
    if not selected:
        selected = ["project.updated"]
    row = WebhookEndpoint(
        name=name.strip() or "Webhook",
        url=url.strip(),
        secret=secrets.token_urlsafe(24),
        events_json=_dump(selected),
        is_active=True,
        description=description,
        tenant_id=tid,
    )
    db.add(row)
    db.flush()
    return row


def list_endpoints(db: Session, tenant_id: UUID | None = None) -> list[WebhookEndpoint]:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    return list(
        db.scalars(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.tenant_id == tid)
            .order_by(WebhookEndpoint.created_at.desc())
        ).all()
    )


def deactivate_endpoint(
    db: Session, endpoint_id: UUID, tenant_id: UUID | None = None
) -> WebhookEndpoint | None:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    row = db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.tenant_id == tid,
        )
    )
    if row is None:
        return None
    row.is_active = False
    db.add(row)
    db.flush()
    return row


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def emit_event(
    db: Session,
    event: str,
    payload: dict[str, Any],
    *,
    tenant_id: UUID | None = None,
    deliver: bool = True,
) -> list[WebhookDelivery]:
    """Create delivery rows and optionally attempt delivery immediately."""
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    endpoints = [
        ep
        for ep in list_endpoints(db, tid)
        if ep.is_active and (event in parse_events(ep) or event == "ping")
    ]
    envelope = {
        "id": str(secrets.token_hex(8)),
        "event": event,
        "created_at": _utc_now().isoformat() + "Z",
        "tenant_id": str(tid),
        "data": payload,
    }
    body = json.dumps(envelope, ensure_ascii=True, default=str).encode("utf-8")
    now = _utc_now()
    deliveries: list[WebhookDelivery] = []
    for ep in endpoints:
        if event != "ping" and event not in parse_events(ep):
            continue
        delivery = WebhookDelivery(
            endpoint_id=ep.id,
            event=event,
            payload_json=body.decode("utf-8"),
            status=STATUS_PENDING,
            attempts=0,
            max_attempts=DEFAULT_MAX_ATTEMPTS,
            next_attempt_at=now,
            tenant_id=tid,
        )
        db.add(delivery)
        db.flush()
        if deliver:
            _attempt_delivery(db, ep, delivery, body)
        deliveries.append(delivery)
    return deliveries


def _attempt_delivery(
    db: Session, endpoint: WebhookEndpoint, delivery: WebhookDelivery, body: bytes
) -> None:
    delivery.attempts = (delivery.attempts or 0) + 1
    max_attempts = delivery.max_attempts or DEFAULT_MAX_ATTEMPTS
    signature = sign_payload(endpoint.secret, body)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ProTrack-Webhooks/1.0",
        "X-ProTrack-Event": delivery.event,
        "X-ProTrack-Signature": signature,
        "X-ProTrack-Delivery": str(delivery.id),
        "X-ProTrack-Attempt": str(delivery.attempts),
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(endpoint.url, content=body, headers=headers)
        delivery.http_status = response.status_code
        if 200 <= response.status_code < 300:
            delivery.status = STATUS_DELIVERED
            delivery.delivered_at = _utc_now()
            delivery.last_error = None
            delivery.next_attempt_at = None
        else:
            _schedule_or_dead(
                delivery,
                max_attempts,
                f"HTTP {response.status_code}: {response.text[:500]}",
            )
    except Exception as exc:
        logger.warning("Webhook delivery failed endpoint=%s: %s", endpoint.id, exc)
        _schedule_or_dead(delivery, max_attempts, str(exc)[:500])
    db.add(delivery)
    db.flush()


def _schedule_or_dead(
    delivery: WebhookDelivery, max_attempts: int, error: str
) -> None:
    delivery.last_error = error
    if delivery.attempts >= max_attempts:
        delivery.status = STATUS_DEAD
        delivery.next_attempt_at = None
        return
    delivery.status = STATUS_PENDING
    delivery.next_attempt_at = _utc_now() + timedelta(
        seconds=backoff_seconds(delivery.attempts)
    )


def process_due_deliveries(
    db: Session,
    *,
    limit: int = 50,
    tenant_id: UUID | None = None,
) -> list[WebhookDelivery]:
    """Attempt pending deliveries whose next_attempt_at is due."""
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    now = _utc_now()
    rows = list(
        db.scalars(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.tenant_id == tid,
                WebhookDelivery.status == STATUS_PENDING,
                or_(
                    WebhookDelivery.next_attempt_at.is_(None),
                    WebhookDelivery.next_attempt_at <= now,
                ),
            )
            .order_by(WebhookDelivery.created_at.asc())
            .limit(limit)
        ).all()
    )
    processed: list[WebhookDelivery] = []
    for delivery in rows:
        endpoint = db.get(WebhookEndpoint, delivery.endpoint_id)
        if endpoint is None or not endpoint.is_active:
            delivery.status = STATUS_DEAD
            delivery.last_error = delivery.last_error or "Endpoint missing or inactive"
            delivery.next_attempt_at = None
            db.add(delivery)
            processed.append(delivery)
            continue
        body = (delivery.payload_json or "").encode("utf-8")
        _attempt_delivery(db, endpoint, delivery, body)
        processed.append(delivery)
    db.flush()
    return processed


def retry_delivery_now(
    db: Session,
    delivery_id: UUID,
    *,
    tenant_id: UUID | None = None,
) -> WebhookDelivery | None:
    """Force an immediate retry for a pending/dead delivery."""
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    delivery = db.scalar(
        select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.tenant_id == tid,
        )
    )
    if delivery is None:
        return None
    if delivery.status == STATUS_DELIVERED:
        return delivery
    was_dead = delivery.status == STATUS_DEAD
    max_attempts = delivery.max_attempts or DEFAULT_MAX_ATTEMPTS
    if was_dead or (delivery.attempts or 0) >= max_attempts:
        delivery.max_attempts = max(max_attempts, (delivery.attempts or 0) + 1)
    delivery.status = STATUS_PENDING
    delivery.next_attempt_at = _utc_now()
    db.add(delivery)
    db.flush()
    endpoint = db.get(WebhookEndpoint, delivery.endpoint_id)
    if endpoint is None:
        delivery.status = STATUS_DEAD
        delivery.last_error = "Endpoint missing"
        db.add(delivery)
        db.flush()
        return delivery
    body = (delivery.payload_json or "").encode("utf-8")
    _attempt_delivery(db, endpoint, delivery, body)
    return delivery


def list_deliveries(
    db: Session, *, limit: int = 50, tenant_id: UUID | None = None
) -> list[WebhookDelivery]:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    return list(
        db.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.tenant_id == tid)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        ).all()
    )
