"""R10 tenant config pack — terminology, numbering, branding, company façade."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.request_context import get_tenant_id
from app.crud.foundation import (
    get_or_create_branding_settings,
    get_or_create_company_settings,
)
from app.db.phase9_schema_sync import DEFAULT_BRANDING
from app.models.commercial import PROSOHM_TENANT_ID, Tenant
from app.services import tenant_service

# Full Prosohm / tooling dictionary — missing keys filled on ensure.
TERMINOLOGY_CATALOG: dict[str, str] = {
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

NUMBERING_CATALOG: dict[str, Any] = {
    "project_code_source": "stream_or_manual",
    "stream_prefix_enabled": True,
    "tool_number_required": True,
    "quote_number_prefix": "Q",
    "ticket_number_prefix": "T",
}

BRANDING_PACK_KEYS = tuple(DEFAULT_BRANDING.keys())


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=True)


def ensure_tenant_config_defaults(db: Session, tenant: Tenant | None = None) -> Tenant:
    """Fill missing terminology/numbering keys; keep tenant-specific overrides."""
    row = tenant or tenant_service.ensure_prosohm_tenant(db)
    terminology = tenant_service.parse_json_dict(row.terminology_json)
    numbering = tenant_service.parse_json_dict(row.numbering_policy_json)
    changed = False
    for key, value in TERMINOLOGY_CATALOG.items():
        if key not in terminology:
            terminology[key] = value
            changed = True
    for key, value in NUMBERING_CATALOG.items():
        if key not in numbering:
            numbering[key] = value
            changed = True
    if changed or not row.terminology_json:
        row.terminology_json = _dump(terminology)
        changed = True
    if changed or not row.numbering_policy_json:
        # only rewrite numbering when we filled keys or empty
        row.numbering_policy_json = _dump(numbering)
    if changed:
        db.add(row)
        db.flush()
    # Ensure branding + company rows exist for this tenant (M1c-scoped).
    get_or_create_branding_settings(db)
    get_or_create_company_settings(db)
    return row


def _branding_dict(db: Session) -> dict[str, Any]:
    settings = get_or_create_branding_settings(db)
    return {key: getattr(settings, key) for key in BRANDING_PACK_KEYS}


def _company_dict(db: Session) -> dict[str, Any]:
    company = get_or_create_company_settings(db)
    return {
        "company_name": company.company_name,
        "company_short_name": company.company_short_name,
        "logo_url": company.logo_url,
        "currency": company.currency,
        "timezone": company.timezone,
    }


def get_tenant_pack(db: Session, tenant_id: UUID | None = None) -> dict[str, Any]:
    """Resolved config pack for the active (or given) tenant."""
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    row = tenant_service.get_tenant(db, tid) or tenant_service.ensure_prosohm_tenant(db)
    row = ensure_tenant_config_defaults(db, row)
    terminology = tenant_service.parse_json_dict(row.terminology_json)
    numbering = tenant_service.parse_json_dict(row.numbering_policy_json)
    return {
        "tenant_id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "edition": row.edition,
        "terminology": terminology,
        "terminology_catalog": TERMINOLOGY_CATALOG,
        "numbering_policy": numbering,
        "numbering_catalog": NUMBERING_CATALOG,
        "branding": _branding_dict(db),
        "branding_defaults": dict(DEFAULT_BRANDING),
        "company": _company_dict(db),
        "sources": {
            "terminology": "tenants.terminology_json",
            "numbering": "tenants.numbering_policy_json",
            "branding": "branding_settings",
            "company": "company_settings",
        },
    }


def update_terminology(db: Session, updates: dict[str, str], tenant_id: UUID | None = None) -> dict[str, Any]:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    row = tenant_service.get_tenant(db, tid) or tenant_service.ensure_prosohm_tenant(db)
    current = tenant_service.parse_json_dict(row.terminology_json)
    for key, value in updates.items():
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        current[key] = cleaned[:120]
    # Keep catalog keys present
    for key, value in TERMINOLOGY_CATALOG.items():
        current.setdefault(key, value)
    row.terminology_json = _dump(current)
    db.add(row)
    db.flush()
    return current


def update_numbering(db: Session, updates: dict[str, Any], tenant_id: UUID | None = None) -> dict[str, Any]:
    tid = tenant_id or get_tenant_id() or PROSOHM_TENANT_ID
    row = tenant_service.get_tenant(db, tid) or tenant_service.ensure_prosohm_tenant(db)
    current = tenant_service.parse_json_dict(row.numbering_policy_json)
    for key, value in updates.items():
        if key not in NUMBERING_CATALOG and key not in current:
            # allow known catalog keys only for new entries
            if key not in NUMBERING_CATALOG:
                continue
        current[key] = value
    for key, value in NUMBERING_CATALOG.items():
        current.setdefault(key, value)
    row.numbering_policy_json = _dump(current)
    db.add(row)
    db.flush()
    return current
