"""Commercial tenancy & feature flags API (R10 spine)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db
from app.core.editions import FLAG_CATALOG, default_flags_for_edition, edition_codes
from app.core.exceptions import ProTrackValidationError
from app.models.commercial import PROSOHM_TENANT_ID
from app.models.models import User
from app.services import feature_flag_service, tenant_pack_service, tenant_service

router = APIRouter(prefix="/commercial", tags=["commercial"])
admin = Depends(require_roles("Admin"))


class TenantRead(BaseModel):
    id: UUID
    slug: str
    name: str
    edition: str
    is_active: bool
    terminology: dict = Field(default_factory=dict)
    numbering_policy: dict = Field(default_factory=dict)
    notes: str | None = None


class TenantPackRead(BaseModel):
    tenant_id: str
    slug: str
    name: str
    edition: str
    terminology: dict = Field(default_factory=dict)
    terminology_catalog: dict = Field(default_factory=dict)
    numbering_policy: dict = Field(default_factory=dict)
    numbering_catalog: dict = Field(default_factory=dict)
    branding: dict = Field(default_factory=dict)
    branding_defaults: dict = Field(default_factory=dict)
    company: dict = Field(default_factory=dict)
    sources: dict = Field(default_factory=dict)


class TerminologyUpdate(BaseModel):
    terminology: dict[str, str] = Field(default_factory=dict)


class NumberingUpdate(BaseModel):
    numbering_policy: dict = Field(default_factory=dict)


class FeatureFlagRead(BaseModel):
    id: UUID
    tenant_id: UUID
    key: str
    enabled: bool
    description: str | None = None


class FeatureFlagUpdate(BaseModel):
    enabled: bool


class EditionCatalogRead(BaseModel):
    editions: list[str]
    flag_catalog: dict[str, str]
    defaults_by_edition: dict[str, dict[str, bool]]


def _tenant_read(row) -> TenantRead:
    return TenantRead(
        id=row.id,
        slug=row.slug,
        name=row.name,
        edition=row.edition,
        is_active=row.is_active,
        terminology=tenant_service.parse_json_dict(row.terminology_json),
        numbering_policy=tenant_service.parse_json_dict(row.numbering_policy_json),
        notes=row.notes,
    )


@router.get("/me", response_model=TenantRead)
def current_tenant(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Active request tenant (defaults to Prosohm)."""
    from app.core.request_context import get_tenant_id

    tenant_service.ensure_prosohm_tenant(db)
    tid = get_tenant_id() or PROSOHM_TENANT_ID
    row = tenant_service.get_tenant(db, tid) or tenant_service.ensure_prosohm_tenant(db)
    tenant_pack_service.ensure_tenant_config_defaults(db, row)
    db.commit()
    return _tenant_read(row)


@router.get("/me/pack", response_model=TenantPackRead)
def current_tenant_pack(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Resolved branding + terminology + numbering pack for the active tenant."""
    pack = tenant_pack_service.get_tenant_pack(db)
    db.commit()
    return TenantPackRead(**pack)


@router.patch("/me/terminology", response_model=TenantPackRead, dependencies=[admin])
def patch_terminology(
    payload: TerminologyUpdate,
    db: Session = Depends(get_db),
):
    tenant_pack_service.update_terminology(db, payload.terminology)
    pack = tenant_pack_service.get_tenant_pack(db)
    db.commit()
    return TenantPackRead(**pack)


@router.patch("/me/numbering", response_model=TenantPackRead, dependencies=[admin])
def patch_numbering(
    payload: NumberingUpdate,
    db: Session = Depends(get_db),
):
    tenant_pack_service.update_numbering(db, payload.numbering_policy)
    pack = tenant_pack_service.get_tenant_pack(db)
    db.commit()
    return TenantPackRead(**pack)


@router.get("/tenants", response_model=list[TenantRead], dependencies=[admin])
def list_tenants(db: Session = Depends(get_db)):
    tenant_service.ensure_prosohm_tenant(db)
    feature_flag_service.ensure_tenant_flags(db, PROSOHM_TENANT_ID)
    db.commit()
    return [_tenant_read(row) for row in tenant_service.list_tenants(db)]


class TenantCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=200)
    edition: str = "trial"
    notes: str | None = None


@router.post("/tenants", response_model=TenantRead, dependencies=[admin])
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    tenant_service.ensure_prosohm_tenant(db)
    try:
        row = tenant_service.create_tenant(
            db,
            slug=payload.slug,
            name=payload.name,
            edition=payload.edition,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return _tenant_read(row)


@router.get("/editions", response_model=EditionCatalogRead, dependencies=[admin])
def edition_catalog():
    return EditionCatalogRead(
        editions=edition_codes(),
        flag_catalog=FLAG_CATALOG,
        defaults_by_edition={
            code: default_flags_for_edition(code) for code in edition_codes()
        },
    )


@router.get(
    "/tenants/{tenant_id}/flags",
    response_model=list[FeatureFlagRead],
    dependencies=[admin],
)
def list_tenant_flags(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant_service.ensure_prosohm_tenant(db)
    if tenant_service.get_tenant(db, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    rows = feature_flag_service.list_flags(db, tenant_id)
    db.commit()
    return [
        FeatureFlagRead(
            id=row.id,
            tenant_id=row.tenant_id,
            key=row.key,
            enabled=row.enabled,
            description=row.description,
        )
        for row in rows
    ]


@router.patch(
    "/tenants/{tenant_id}/flags/{flag_key}",
    response_model=FeatureFlagRead,
    dependencies=[admin],
)
def patch_tenant_flag(
    tenant_id: UUID,
    flag_key: str,
    payload: FeatureFlagUpdate,
    db: Session = Depends(get_db),
):
    tenant_service.ensure_prosohm_tenant(db)
    if tenant_service.get_tenant(db, tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    try:
        row = feature_flag_service.set_flag(
            db, tenant_id=tenant_id, key=flag_key, enabled=payload.enabled
        )
        db.commit()
        db.refresh(row)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    return FeatureFlagRead(
        id=row.id,
        tenant_id=row.tenant_id,
        key=row.key,
        enabled=row.enabled,
        description=row.description,
    )


# --- Public API keys + webhooks (admin) -------------------------------------


class ApiKeyRead(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    is_active: bool
    last_used_at: str | None = None
    notes: str | None = None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["projects:read"])
    notes: str | None = None


class ApiKeyCreated(ApiKeyRead):
    raw_key: str


class WebhookEndpointRead(BaseModel):
    id: UUID
    name: str
    url: str
    secret: str
    events: list[str] = Field(default_factory=list)
    is_active: bool
    description: str | None = None


class WebhookEndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=500)
    events: list[str] = Field(default_factory=lambda: ["project.updated"])
    description: str | None = None


class WebhookDeliveryRead(BaseModel):
    id: UUID
    endpoint_id: UUID
    event: str
    status: str
    http_status: int | None = None
    attempts: int
    max_attempts: int = 5
    next_attempt_at: str | None = None
    last_error: str | None = None


class WebhookPingRequest(BaseModel):
    endpoint_id: UUID | None = None


def _require_flag(db: Session, key: str) -> None:
    if not feature_flag_service.is_enabled(db, key):
        raise HTTPException(status_code=403, detail=f"Feature disabled: {key}")


def _delivery_read(row) -> WebhookDeliveryRead:
    next_at = row.next_attempt_at.isoformat() if getattr(row, "next_attempt_at", None) else None
    return WebhookDeliveryRead(
        id=row.id,
        endpoint_id=row.endpoint_id,
        event=row.event,
        status=row.status,
        http_status=row.http_status,
        attempts=row.attempts or 0,
        max_attempts=getattr(row, "max_attempts", None) or 5,
        next_attempt_at=next_at,
        last_error=row.last_error,
    )


@router.get("/api-keys", response_model=list[ApiKeyRead], dependencies=[admin])
def list_api_keys(db: Session = Depends(get_db)):
    from app.services import api_key_service

    _require_flag(db, "feature.public_api")
    rows = api_key_service.list_api_keys(db)
    return [
        ApiKeyRead(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            scopes=api_key_service.parse_scopes(row),
            is_active=row.is_active,
            last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
            notes=row.notes,
        )
        for row in rows
    ]


@router.post("/api-keys", response_model=ApiKeyCreated, dependencies=[admin])
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services import api_key_service

    _require_flag(db, "feature.public_api")
    row, raw = api_key_service.create_api_key(
        db,
        name=payload.name,
        scopes=payload.scopes,
        notes=payload.notes,
        created_by_id=user.id,
    )
    db.commit()
    db.refresh(row)
    return ApiKeyCreated(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        scopes=api_key_service.parse_scopes(row),
        is_active=row.is_active,
        last_used_at=None,
        notes=row.notes,
        raw_key=raw,
    )


@router.delete("/api-keys/{key_id}", response_model=ApiKeyRead, dependencies=[admin])
def revoke_api_key(key_id: UUID, db: Session = Depends(get_db)):
    from app.services import api_key_service

    _require_flag(db, "feature.public_api")
    row = api_key_service.revoke_api_key(db, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    db.commit()
    db.refresh(row)
    return ApiKeyRead(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        scopes=api_key_service.parse_scopes(row),
        is_active=row.is_active,
        last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
        notes=row.notes,
    )


@router.get("/webhooks", response_model=list[WebhookEndpointRead], dependencies=[admin])
def list_webhooks(db: Session = Depends(get_db)):
    from app.services import webhook_service

    _require_flag(db, "feature.webhooks")
    rows = webhook_service.list_endpoints(db)
    return [
        WebhookEndpointRead(
            id=row.id,
            name=row.name,
            url=row.url,
            secret=row.secret,
            events=webhook_service.parse_events(row),
            is_active=row.is_active,
            description=row.description,
        )
        for row in rows
    ]


@router.post("/webhooks", response_model=WebhookEndpointRead, dependencies=[admin])
def create_webhook(payload: WebhookEndpointCreate, db: Session = Depends(get_db)):
    from app.services import webhook_service

    _require_flag(db, "feature.webhooks")
    row = webhook_service.create_endpoint(
        db,
        name=payload.name,
        url=payload.url,
        events=payload.events,
        description=payload.description,
    )
    db.commit()
    db.refresh(row)
    return WebhookEndpointRead(
        id=row.id,
        name=row.name,
        url=row.url,
        secret=row.secret,
        events=webhook_service.parse_events(row),
        is_active=row.is_active,
        description=row.description,
    )


@router.get(
    "/webhooks/deliveries",
    response_model=list[WebhookDeliveryRead],
    dependencies=[admin],
)
def list_webhook_deliveries(db: Session = Depends(get_db)):
    from app.services import webhook_service

    _require_flag(db, "feature.webhooks")
    rows = webhook_service.list_deliveries(db)
    return [_delivery_read(row) for row in rows]


@router.post(
    "/webhooks/process-retries",
    response_model=list[WebhookDeliveryRead],
    dependencies=[admin],
)
def process_webhook_retries(db: Session = Depends(get_db)):
    from app.services import webhook_service

    _require_flag(db, "feature.webhooks")
    rows = webhook_service.process_due_deliveries(db, limit=50)
    db.commit()
    return [_delivery_read(row) for row in rows]


@router.post(
    "/webhooks/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryRead,
    dependencies=[admin],
)
def retry_webhook_delivery(delivery_id: UUID, db: Session = Depends(get_db)):
    from app.services import webhook_service

    _require_flag(db, "feature.webhooks")
    row = webhook_service.retry_delivery_now(db, delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    db.commit()
    return _delivery_read(row)


@router.post(
    "/webhooks/ping",
    response_model=list[WebhookDeliveryRead],
    dependencies=[admin],
)
def ping_webhooks(payload: WebhookPingRequest, db: Session = Depends(get_db)):
    from app.services import webhook_service

    _require_flag(db, "feature.webhooks")
    deliveries = webhook_service.emit_event(
        db,
        "ping",
        {
            "message": "ProTrack webhook ping",
            "endpoint_id": str(payload.endpoint_id) if payload.endpoint_id else None,
        },
        deliver=True,
    )
    if payload.endpoint_id:
        deliveries = [d for d in deliveries if d.endpoint_id == payload.endpoint_id]
    db.commit()
    return [_delivery_read(row) for row in deliveries]


@router.delete(
    "/webhooks/{endpoint_id}",
    response_model=WebhookEndpointRead,
    dependencies=[admin],
)
def deactivate_webhook(endpoint_id: UUID, db: Session = Depends(get_db)):
    from app.services import webhook_service

    _require_flag(db, "feature.webhooks")
    row = webhook_service.deactivate_endpoint(db, endpoint_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.commit()
    db.refresh(row)
    return WebhookEndpointRead(
        id=row.id,
        name=row.name,
        url=row.url,
        secret=row.secret,
        events=webhook_service.parse_events(row),
        is_active=row.is_active,
        description=row.description,
    )


# --- Commercial readiness (GTM / trust / sign-off) ---------------------------


class SignoffRead(BaseModel):
    id: UUID
    key: str
    signer_name: str
    signer_role: str
    signed_at: str
    notes: str | None = None
    evidence_url: str | None = None


class SignoffUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    signer_name: str = Field(min_length=1, max_length=200)
    signer_role: str = Field(min_length=1, max_length=80)
    notes: str | None = None
    evidence_url: str | None = None


class DesignPartnerRead(BaseModel):
    id: UUID
    icp: str
    company_name: str
    status: str
    contact_name: str | None = None
    contact_email: str | None = None
    loi_doc_ref: str | None = None
    loi_sent_at: str | None = None
    loi_signed_at: str | None = None
    notes: str | None = None


class DesignPartnerCreate(BaseModel):
    icp: str = Field(min_length=1, max_length=32)
    company_name: str = Field(min_length=1, max_length=200)
    status: str = "draft"
    contact_name: str | None = None
    contact_email: str | None = None
    loi_doc_ref: str | None = None
    notes: str | None = None


class DesignPartnerUpdate(BaseModel):
    icp: str | None = None
    company_name: str | None = None
    status: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    loi_doc_ref: str | None = None
    notes: str | None = None


class TrustCheckRead(BaseModel):
    id: UUID
    control_id: str
    title: str
    severity: str
    must_fix: bool
    status: str
    owner: str | None = None
    evidence_notes: str | None = None
    doc_path: str | None = None
    completed_at: str | None = None


class TrustCheckUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    evidence_notes: str | None = None


class ReadinessSummary(BaseModel):
    signoffs_count: int
    signoff_keys: list[str] = Field(default_factory=list)
    partners_count: int
    partners_by_status: dict[str, int] = Field(default_factory=dict)
    trust_open: int
    trust_done: int
    trust_must_fix_open: int
    vision_d_ceo_signed: bool
    vision_d_cto_signed: bool
    require_sso_for_admins: bool
    audit_retention_days: int
    oidc_enabled: bool
    oidc_testing: bool
    oidc_available: bool
    documents: list[dict[str, str]] = Field(default_factory=list)


def _signoff_read(row) -> SignoffRead:
    return SignoffRead(
        id=row.id,
        key=row.key,
        signer_name=row.signer_name,
        signer_role=row.signer_role,
        signed_at=row.signed_at.isoformat() if row.signed_at else "",
        notes=row.notes,
        evidence_url=row.evidence_url,
    )


def _partner_read(row) -> DesignPartnerRead:
    return DesignPartnerRead(
        id=row.id,
        icp=row.icp,
        company_name=row.company_name,
        status=row.status,
        contact_name=row.contact_name,
        contact_email=row.contact_email,
        loi_doc_ref=row.loi_doc_ref,
        loi_sent_at=row.loi_sent_at.isoformat() if row.loi_sent_at else None,
        loi_signed_at=row.loi_signed_at.isoformat() if row.loi_signed_at else None,
        notes=row.notes,
    )


def _trust_read(row) -> TrustCheckRead:
    return TrustCheckRead(
        id=row.id,
        control_id=row.control_id,
        title=row.title,
        severity=row.severity,
        must_fix=row.must_fix,
        status=row.status,
        owner=row.owner,
        evidence_notes=row.evidence_notes,
        doc_path=row.doc_path,
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
    )


@router.get(
    "/readiness/summary",
    response_model=ReadinessSummary,
    dependencies=[admin],
)
def readiness_summary(db: Session = Depends(get_db)):
    from app.core.oidc import oidc_available, oidc_enabled, oidc_testing
    from app.services import commercial_readiness_service
    from app.services.security_policy_service import get_effective_policy

    counts = commercial_readiness_service.summary_counts(db)
    db.commit()
    policy = get_effective_policy(db)
    return ReadinessSummary(
        **counts,
        require_sso_for_admins=policy.require_sso_for_admins,
        audit_retention_days=policy.audit_retention_days,
        oidc_enabled=oidc_enabled(),
        oidc_testing=oidc_testing(),
        oidc_available=oidc_available(),
        documents=list(commercial_readiness_service.TRUST_DOC_INDEX),
    )


@router.get(
    "/readiness/signoffs",
    response_model=list[SignoffRead],
    dependencies=[admin],
)
def list_signoffs(db: Session = Depends(get_db)):
    from app.services import commercial_readiness_service

    return [_signoff_read(r) for r in commercial_readiness_service.list_signoffs(db)]


@router.post(
    "/readiness/signoffs",
    response_model=SignoffRead,
    dependencies=[admin],
)
def upsert_signoff(payload: SignoffUpsert, db: Session = Depends(get_db)):
    from app.services import commercial_readiness_service

    row = commercial_readiness_service.upsert_signoff(
        db,
        key=payload.key,
        signer_name=payload.signer_name,
        signer_role=payload.signer_role,
        notes=payload.notes,
        evidence_url=payload.evidence_url,
    )
    db.commit()
    db.refresh(row)
    return _signoff_read(row)


@router.get(
    "/readiness/partners",
    response_model=list[DesignPartnerRead],
    dependencies=[admin],
)
def list_design_partners(db: Session = Depends(get_db)):
    from app.services import commercial_readiness_service

    return [_partner_read(r) for r in commercial_readiness_service.list_partners(db)]


@router.post(
    "/readiness/partners",
    response_model=DesignPartnerRead,
    dependencies=[admin],
)
def create_design_partner(payload: DesignPartnerCreate, db: Session = Depends(get_db)):
    from app.services import commercial_readiness_service

    try:
        row = commercial_readiness_service.create_partner(
            db,
            icp=payload.icp,
            company_name=payload.company_name,
            status=payload.status,
            contact_name=payload.contact_name,
            contact_email=payload.contact_email,
            loi_doc_ref=payload.loi_doc_ref,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return _partner_read(row)


@router.patch(
    "/readiness/partners/{partner_id}",
    response_model=DesignPartnerRead,
    dependencies=[admin],
)
def patch_design_partner(
    partner_id: UUID, payload: DesignPartnerUpdate, db: Session = Depends(get_db)
):
    from app.services import commercial_readiness_service

    try:
        row = commercial_readiness_service.update_partner(
            db, partner_id, updates=payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Design partner not found")
    db.commit()
    db.refresh(row)
    return _partner_read(row)


@router.get(
    "/readiness/trust-checks",
    response_model=list[TrustCheckRead],
    dependencies=[admin],
)
def list_trust_checks(db: Session = Depends(get_db)):
    from app.services import commercial_readiness_service

    rows = commercial_readiness_service.ensure_trust_controls(db)
    db.commit()
    return [_trust_read(r) for r in rows]


@router.patch(
    "/readiness/trust-checks/{control_id}",
    response_model=TrustCheckRead,
    dependencies=[admin],
)
def patch_trust_check(
    control_id: str, payload: TrustCheckUpdate, db: Session = Depends(get_db)
):
    from app.services import commercial_readiness_service

    try:
        row = commercial_readiness_service.update_trust_check(
            db,
            control_id,
            status=payload.status,
            owner=payload.owner,
            evidence_notes=payload.evidence_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Trust control not found")
    db.commit()
    db.refresh(row)
    return _trust_read(row)


@router.get("/readiness/access-review", dependencies=[admin])
def access_review_export(db: Session = Depends(get_db), format: str = "json"):
    from app.services import commercial_readiness_service

    rows = commercial_readiness_service.access_review_rows(db)
    if format.lower() == "csv":
        import csv
        import io

        from fastapi.responses import PlainTextResponse

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "user_id",
                "email",
                "name",
                "role",
                "is_active",
                "last_login",
                "sso_subject",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return PlainTextResponse(
            buf.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=access-review.csv"
            },
        )
    return {"count": len(rows), "items": rows}


class RequireSsoUpdate(BaseModel):
    enabled: bool


@router.put("/readiness/require-sso-for-admins", dependencies=[admin])
def set_require_sso_for_admins(
    payload: RequireSsoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    from app.services.security_policy_service import get_effective_policy, update_policy

    update_policy(db, {"require_sso_for_admins": payload.enabled}, current_user)
    policy = get_effective_policy(db)
    return {"require_sso_for_admins": policy.require_sso_for_admins}
