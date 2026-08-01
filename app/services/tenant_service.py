"""Tenant ensure/seed and request binding helpers."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commercial import PROSOHM_TENANT_ID, PROSOHM_TENANT_SLUG, Tenant

DEFAULT_PROSOHM_TERMINOLOGY = {
    "project": "Project",
    "projects": "Projects",
    "tool_number": "Tool number",
    "part_description": "Part description",
    "customer": "Customer",
    "customers": "Customers",
    "contact": "Contact",
    "timesheet": "Timesheet",
    "timesheets": "Timesheets",
    "milestone": "Milestone",
    "milestones": "Milestones",
    "team": "Team",
    "teams": "Teams",
    "stream": "Stream",
    "quote": "Quote",
    "quotes": "Quotes",
    "work_order": "Work order",
    "designer": "Designer",
    "surfacer": "Surfacer",
}

DEFAULT_PROSOHM_NUMBERING = {
    "project_code_source": "stream_or_manual",
    "stream_prefix_enabled": True,
    "tool_number_required": True,
    "quote_number_prefix": "Q",
    "ticket_number_prefix": "T",
}


def ensure_prosohm_tenant(db: Session) -> Tenant:
    row = db.get(Tenant, PROSOHM_TENANT_ID)
    if row is not None:
        return row
    by_slug = db.scalar(select(Tenant).where(Tenant.slug == PROSOHM_TENANT_SLUG))
    if by_slug is not None:
        return by_slug
    row = Tenant(
        id=PROSOHM_TENANT_ID,
        slug=PROSOHM_TENANT_SLUG,
        name="Prosohm",
        edition="enterprise",
        is_active=True,
        terminology_json=json.dumps(DEFAULT_PROSOHM_TERMINOLOGY),
        numbering_policy_json=json.dumps(DEFAULT_PROSOHM_NUMBERING),
        notes="Default internal production tenant (R10 spine).",
    )
    db.add(row)
    db.flush()
    return row


def get_tenant(db: Session, tenant_id: UUID) -> Tenant | None:
    return db.get(Tenant, tenant_id)


def list_tenants(db: Session) -> list[Tenant]:
    return list(db.scalars(select(Tenant).order_by(Tenant.name)).all())


def create_tenant(
    db: Session,
    *,
    slug: str,
    name: str,
    edition: str = "trial",
    notes: str | None = None,
) -> Tenant:
    """Create an external/commercial tenant and seed edition flags."""
    from app.core.editions import edition_codes
    from app.db.tenant_filter import without_tenant_filter
    from app.services import feature_flag_service

    clean_slug = slug.strip().lower().replace(" ", "-")
    if not clean_slug or not name.strip():
        raise ValueError("slug and name are required")
    if edition not in edition_codes():
        raise ValueError(f"Invalid edition: {edition}")
    existing = db.scalar(select(Tenant).where(Tenant.slug == clean_slug))
    if existing is not None:
        raise ValueError(f"Tenant slug already exists: {clean_slug}")
    row = Tenant(
        slug=clean_slug,
        name=name.strip(),
        edition=edition,
        is_active=True,
        terminology_json=json.dumps(DEFAULT_PROSOHM_TERMINOLOGY),
        numbering_policy_json=json.dumps(DEFAULT_PROSOHM_NUMBERING),
        notes=notes,
    )
    db.add(row)
    db.flush()
    # Flags belong to the new tenant; opt out of request-tenant write guard.
    with without_tenant_filter():
        feature_flag_service.ensure_tenant_flags(db, row.id)
        db.flush()
    return row


def parse_json_dict(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
