"""Tenant API key create / verify (R10 public API)."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SECRET_KEY
from app.core.request_context import get_tenant_id, set_tenant_id
from app.models.commercial import PROSOHM_TENANT_ID
from app.models.integrations import ApiKey

DEFAULT_SCOPES = ["projects:read"]
KNOWN_SCOPES = ("projects:read", "milestones:read", "users:read", "*")


def _hash_key(raw: str) -> str:
    return hashlib.sha256(f"{SECRET_KEY}:api-key:{raw}".encode("utf-8")).hexdigest()


def generate_raw_key() -> tuple[str, str]:
    """Return (raw_key, prefix)."""
    token = secrets.token_urlsafe(32)
    raw = f"pt_live_{token}"
    prefix = raw[:16]
    return raw, prefix


def create_api_key(
    db: Session,
    *,
    name: str,
    scopes: list[str] | None = None,
    notes: str | None = None,
    created_by_id: UUID | None = None,
    tenant_id: UUID | None = None,
) -> tuple[ApiKey, str]:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    raw, prefix = generate_raw_key()
    row = ApiKey(
        name=name.strip() or "API key",
        key_prefix=prefix,
        key_hash=_hash_key(raw),
        scopes_json=json.dumps(scopes or DEFAULT_SCOPES),
        is_active=True,
        created_by_id=created_by_id,
        notes=notes,
        tenant_id=tid,
    )
    db.add(row)
    db.flush()
    return row, raw


def list_api_keys(db: Session, tenant_id: UUID | None = None) -> list[ApiKey]:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    return list(
        db.scalars(
            select(ApiKey)
            .where(ApiKey.tenant_id == tid)
            .order_by(ApiKey.created_at.desc())
        ).all()
    )


def revoke_api_key(db: Session, key_id: UUID, tenant_id: UUID | None = None) -> ApiKey | None:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    row = db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == tid)
    )
    if row is None:
        return None
    row.is_active = False
    db.add(row)
    db.flush()
    return row


def parse_scopes(row: ApiKey) -> list[str]:
    try:
        data = json.loads(row.scopes_json or "[]")
    except json.JSONDecodeError:
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def verify_api_key(db: Session, raw: str) -> ApiKey | None:
    if not raw or not raw.startswith("pt_live_"):
        return None
    prefix = raw[:16]
    digest = _hash_key(raw)
    # Lookup without tenant filter — key itself binds tenant.
    from app.db.tenant_filter import without_tenant_filter

    with without_tenant_filter():
        candidates = list(
            db.scalars(
                select(ApiKey).where(
                    ApiKey.key_prefix == prefix,
                    ApiKey.is_active.is_(True),
                )
            ).all()
        )
    for row in candidates:
        if row.key_hash == digest:
            row.last_used_at = datetime.now(UTC)
            db.add(row)
            set_tenant_id(row.tenant_id)
            return row
    return None
