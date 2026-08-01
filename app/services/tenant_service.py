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


def parse_json_dict(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
