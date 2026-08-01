"""Commercial readiness — sign-offs, design partners, trust checklist (R10-010)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.request_context import get_tenant_id
from app.models.commercial import PROSOHM_TENANT_ID
from app.models.commercial_readiness import (
    CommercialSignoff,
    DesignPartner,
    TrustControlCheck,
)
from app.models.models import Role, User

TRUST_CONTROL_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "control_id": "S2",
        "title": "Admin SSO (or MFA) for privileged roles",
        "severity": "high",
        "must_fix": True,
        "doc_path": "docs/trust/ADMIN_SSO_GATE.md",
    },
    {
        "control_id": "S4",
        "title": "Backup restore drill evidence",
        "severity": "high",
        "must_fix": True,
        "doc_path": "docs/trust/BACKUP_RESTORE_DRILL.md",
    },
    {
        "control_id": "S5",
        "title": "Incident response runbook",
        "severity": "high",
        "must_fix": True,
        "doc_path": "docs/trust/INCIDENT_RESPONSE_RUNBOOK.md",
    },
    {
        "control_id": "S6",
        "title": "Subprocessor inventory",
        "severity": "med",
        "must_fix": True,
        "doc_path": "docs/trust/SUBPROCESSORS.md",
    },
    {
        "control_id": "S12",
        "title": "DPA + privacy notice drafts",
        "severity": "high",
        "must_fix": True,
        "doc_path": "docs/trust/DPA_DRAFT.md",
    },
    {
        "control_id": "S11",
        "title": "Cross-tenant isolation probe",
        "severity": "med",
        "must_fix": True,
        "doc_path": "docs/ADR_R10_PG_RLS.md",
    },
    {
        "control_id": "S1",
        "title": "Quarterly access review attestation",
        "severity": "high",
        "must_fix": False,
        "doc_path": None,
    },
    {
        "control_id": "S3",
        "title": "Change management evidence pack",
        "severity": "med",
        "must_fix": False,
        "doc_path": "docs/trust/CHANGE_MANAGEMENT.md",
    },
    {
        "control_id": "S7",
        "title": "Audit log retention policy stated",
        "severity": "med",
        "must_fix": False,
        "doc_path": "docs/trust/AUDIT_RETENTION.md",
    },
    {
        "control_id": "S8",
        "title": "Vulnerability management cadence",
        "severity": "high",
        "must_fix": False,
        "doc_path": "docs/trust/VULN_MGMT_CADENCE.md",
    },
    {
        "control_id": "S10",
        "title": "IT offboard checklist (IdP/OS)",
        "severity": "med",
        "must_fix": False,
        "doc_path": "docs/trust/IT_OFFBOARD_CHECKLIST.md",
    },
)

TRUST_DOC_INDEX: tuple[dict[str, str], ...] = (
    {"title": "DPA draft", "path": "docs/trust/DPA_DRAFT.md"},
    {"title": "Privacy notice draft", "path": "docs/trust/PRIVACY_NOTICE_DRAFT.md"},
    {"title": "Subprocessors", "path": "docs/trust/SUBPROCESSORS.md"},
    {"title": "Incident response runbook", "path": "docs/trust/INCIDENT_RESPONSE_RUNBOOK.md"},
    {"title": "Backup restore drill", "path": "docs/trust/BACKUP_RESTORE_DRILL.md"},
    {"title": "IT offboard checklist", "path": "docs/trust/IT_OFFBOARD_CHECKLIST.md"},
    {"title": "Change management", "path": "docs/trust/CHANGE_MANAGEMENT.md"},
    {"title": "Vuln management cadence", "path": "docs/trust/VULN_MGMT_CADENCE.md"},
    {"title": "Audit retention", "path": "docs/trust/AUDIT_RETENTION.md"},
    {"title": "Admin SSO gate", "path": "docs/trust/ADMIN_SSO_GATE.md"},
    {"title": "Vision D one-pager", "path": "docs/R10_VISION_D_ONE_PAGER.md"},
    {"title": "Entra SSO smoke", "path": "docs/R10_ENTRA_SSO_SMOKE.md"},
    {"title": "LOI — mold", "path": "docs/R10_LOI_DESIGN_PARTNER_MOLD.md"},
    {"title": "LOI — fixture", "path": "docs/R10_LOI_DESIGN_PARTNER_FIXTURE.md"},
    {"title": "LOI — auto", "path": "docs/R10_LOI_DESIGN_PARTNER_AUTO.md"},
)

VALID_PARTNER_ICP = frozenset({"mold", "fixture", "auto"})
VALID_PARTNER_STATUS = frozenset(
    {"draft", "loi_sent", "signed", "active", "exited"}
)
VALID_CHECK_STATUS = frozenset({"open", "in_progress", "done", "na"})


def _tid(tenant_id: UUID | None = None) -> UUID:
    return tenant_id or get_tenant_id() or PROSOHM_TENANT_ID


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ensure_trust_controls(db: Session, tenant_id: UUID | None = None) -> list[TrustControlCheck]:
    tid = _tid(tenant_id)
    existing = {
        row.control_id: row
        for row in db.scalars(
            select(TrustControlCheck).where(TrustControlCheck.tenant_id == tid)
        ).all()
    }
    created: list[TrustControlCheck] = []
    for item in TRUST_CONTROL_CATALOG:
        if item["control_id"] in existing:
            continue
        row = TrustControlCheck(
            control_id=item["control_id"],
            title=item["title"],
            severity=item["severity"],
            must_fix=bool(item["must_fix"]),
            status="open",
            doc_path=item.get("doc_path"),
            tenant_id=tid,
        )
        db.add(row)
        created.append(row)
    if created:
        db.flush()
    return list(
        db.scalars(
            select(TrustControlCheck)
            .where(TrustControlCheck.tenant_id == tid)
            .order_by(TrustControlCheck.control_id)
        ).all()
    )


def list_signoffs(db: Session, tenant_id: UUID | None = None) -> list[CommercialSignoff]:
    tid = _tid(tenant_id)
    return list(
        db.scalars(
            select(CommercialSignoff)
            .where(CommercialSignoff.tenant_id == tid)
            .order_by(CommercialSignoff.key)
        ).all()
    )


def upsert_signoff(
    db: Session,
    *,
    key: str,
    signer_name: str,
    signer_role: str,
    notes: str | None = None,
    evidence_url: str | None = None,
    tenant_id: UUID | None = None,
) -> CommercialSignoff:
    tid = _tid(tenant_id)
    key = key.strip()
    row = db.scalar(
        select(CommercialSignoff).where(
            CommercialSignoff.tenant_id == tid,
            CommercialSignoff.key == key,
        )
    )
    now = _utc_now()
    if row is None:
        row = CommercialSignoff(
            key=key,
            signer_name=signer_name.strip(),
            signer_role=signer_role.strip(),
            signed_at=now,
            notes=notes,
            evidence_url=evidence_url,
            tenant_id=tid,
        )
        db.add(row)
    else:
        row.signer_name = signer_name.strip()
        row.signer_role = signer_role.strip()
        row.signed_at = now
        row.notes = notes
        row.evidence_url = evidence_url
        db.add(row)
    db.flush()
    return row


def list_partners(db: Session, tenant_id: UUID | None = None) -> list[DesignPartner]:
    tid = _tid(tenant_id)
    return list(
        db.scalars(
            select(DesignPartner)
            .where(DesignPartner.tenant_id == tid)
            .order_by(DesignPartner.created_at.desc())
        ).all()
    )


def create_partner(
    db: Session,
    *,
    icp: str,
    company_name: str,
    status: str = "draft",
    contact_name: str | None = None,
    contact_email: str | None = None,
    loi_doc_ref: str | None = None,
    notes: str | None = None,
    tenant_id: UUID | None = None,
) -> DesignPartner:
    if icp not in VALID_PARTNER_ICP:
        raise ValueError(f"Invalid ICP: {icp}")
    if status not in VALID_PARTNER_STATUS:
        raise ValueError(f"Invalid status: {status}")
    row = DesignPartner(
        icp=icp,
        company_name=company_name.strip(),
        status=status,
        contact_name=contact_name,
        contact_email=contact_email,
        loi_doc_ref=loi_doc_ref,
        notes=notes,
        tenant_id=_tid(tenant_id),
    )
    if status == "loi_sent":
        row.loi_sent_at = _utc_now()
    if status == "signed":
        row.loi_signed_at = _utc_now()
    db.add(row)
    db.flush()
    return row


def update_partner(
    db: Session,
    partner_id: UUID,
    *,
    updates: dict[str, Any],
    tenant_id: UUID | None = None,
) -> DesignPartner | None:
    tid = _tid(tenant_id)
    row = db.scalar(
        select(DesignPartner).where(
            DesignPartner.id == partner_id,
            DesignPartner.tenant_id == tid,
        )
    )
    if row is None:
        return None
    if "icp" in updates and updates["icp"] is not None:
        if updates["icp"] not in VALID_PARTNER_ICP:
            raise ValueError(f"Invalid ICP: {updates['icp']}")
        row.icp = updates["icp"]
    if "status" in updates and updates["status"] is not None:
        if updates["status"] not in VALID_PARTNER_STATUS:
            raise ValueError(f"Invalid status: {updates['status']}")
        row.status = updates["status"]
        if updates["status"] == "loi_sent" and row.loi_sent_at is None:
            row.loi_sent_at = _utc_now()
        if updates["status"] in {"signed", "active"} and row.loi_signed_at is None:
            row.loi_signed_at = _utc_now()
    for field in ("company_name", "contact_name", "contact_email", "loi_doc_ref", "notes"):
        if field in updates and updates[field] is not None:
            setattr(row, field, updates[field])
    db.add(row)
    db.flush()
    return row


def update_trust_check(
    db: Session,
    control_id: str,
    *,
    status: str | None = None,
    owner: str | None = None,
    evidence_notes: str | None = None,
    tenant_id: UUID | None = None,
) -> TrustControlCheck | None:
    ensure_trust_controls(db, tenant_id)
    tid = _tid(tenant_id)
    row = db.scalar(
        select(TrustControlCheck).where(
            TrustControlCheck.tenant_id == tid,
            TrustControlCheck.control_id == control_id,
        )
    )
    if row is None:
        return None
    if status is not None:
        if status not in VALID_CHECK_STATUS:
            raise ValueError(f"Invalid status: {status}")
        row.status = status
        row.completed_at = _utc_now() if status in {"done", "na"} else None
    if owner is not None:
        row.owner = owner
    if evidence_notes is not None:
        row.evidence_notes = evidence_notes
    db.add(row)
    db.flush()
    return row


def access_review_rows(db: Session, tenant_id: UUID | None = None) -> list[dict[str, Any]]:
    """Privileged users for quarterly access attestation."""
    tid = _tid(tenant_id)
    privileged = ("Admin", "HR Admin", "Finance Admin", "System Admin")
    rows = db.execute(
        select(User, Role.name)
        .join(Role, User.role_id == Role.id)
        .where(
            User.tenant_id == tid,
            User.is_deleted.is_(False),
            User.is_archived.is_(False),
            Role.name.in_(privileged),
        )
        .order_by(Role.name, User.email)
    ).all()
    out: list[dict[str, Any]] = []
    for user, role_name in rows:
        out.append(
            {
                "user_id": str(user.id),
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "role": role_name,
                "is_active": user.is_active,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "sso_subject": getattr(user, "sso_subject", None),
            }
        )
    return out


def summary_counts(db: Session, tenant_id: UUID | None = None) -> dict[str, Any]:
    tid = _tid(tenant_id)
    checks = ensure_trust_controls(db, tid)
    partners = list_partners(db, tid)
    signoffs = list_signoffs(db, tid)
    by_status: dict[str, int] = {}
    for p in partners:
        by_status[p.status] = by_status.get(p.status, 0) + 1
    open_checks = sum(1 for c in checks if c.status == "open")
    done_checks = sum(1 for c in checks if c.status == "done")
    must_open = sum(1 for c in checks if c.must_fix and c.status not in {"done", "na"})
    return {
        "signoffs_count": len(signoffs),
        "signoff_keys": [s.key for s in signoffs],
        "partners_count": len(partners),
        "partners_by_status": by_status,
        "trust_open": open_checks,
        "trust_done": done_checks,
        "trust_must_fix_open": must_open,
        "vision_d_ceo_signed": any(s.key == "vision_d_ceo" for s in signoffs),
        "vision_d_cto_signed": any(s.key == "vision_d_cto" for s in signoffs),
    }
