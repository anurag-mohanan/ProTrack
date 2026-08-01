"""Feature flag resolution against edition defaults + tenant overrides."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.editions import FLAG_CATALOG, default_flags_for_edition
from app.core.request_context import get_tenant_id
from app.models.commercial import PROSOHM_TENANT_ID, FeatureFlag
from app.services.tenant_service import ensure_prosohm_tenant, get_tenant


def ensure_tenant_flags(db: Session, tenant_id: UUID) -> list[FeatureFlag]:
    """Create missing flag rows for a tenant from edition defaults (idempotent)."""
    tenant = get_tenant(db, tenant_id)
    if tenant is None:
        tenant = ensure_prosohm_tenant(db)
        tenant_id = tenant.id
    defaults = default_flags_for_edition(tenant.edition)
    existing = {
        row.key: row
        for row in db.scalars(
            select(FeatureFlag).where(FeatureFlag.tenant_id == tenant_id)
        ).all()
    }
    changed = False
    for key, enabled in defaults.items():
        if key in existing:
            continue
        db.add(
            FeatureFlag(
                tenant_id=tenant_id,
                key=key,
                enabled=enabled,
                description=FLAG_CATALOG.get(key),
            )
        )
        changed = True
    if changed:
        db.flush()
    return list(
        db.scalars(select(FeatureFlag).where(FeatureFlag.tenant_id == tenant_id)).all()
    )


def list_flags(db: Session, tenant_id: UUID | None = None) -> list[FeatureFlag]:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    ensure_prosohm_tenant(db)
    return ensure_tenant_flags(db, tid)


def is_enabled(db: Session, key: str, *, tenant_id: UUID | None = None) -> bool:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    ensure_prosohm_tenant(db)
    ensure_tenant_flags(db, tid)
    row = db.scalar(
        select(FeatureFlag).where(
            FeatureFlag.tenant_id == tid,
            FeatureFlag.key == key,
        )
    )
    if row is not None:
        return bool(row.enabled)
    return bool(default_flags_for_edition("enterprise").get(key, False))


def set_flag(
    db: Session,
    *,
    tenant_id: UUID,
    key: str,
    enabled: bool,
) -> FeatureFlag:
    if key not in FLAG_CATALOG:
        from app.core.exceptions import ProTrackValidationError

        raise ProTrackValidationError(f"Unknown feature flag key: {key}")
    ensure_tenant_flags(db, tenant_id)
    row = db.scalar(
        select(FeatureFlag).where(
            FeatureFlag.tenant_id == tenant_id,
            FeatureFlag.key == key,
        )
    )
    if row is None:
        row = FeatureFlag(
            tenant_id=tenant_id,
            key=key,
            enabled=enabled,
            description=FLAG_CATALOG.get(key),
        )
        db.add(row)
    else:
        row.enabled = enabled
        db.add(row)
    db.flush()
    return row
