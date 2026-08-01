"""Commercial tenancy models — R10 spine (tenant + feature flags)."""

from __future__ import annotations

import uuid
from typing import Optional

from app.db.base import (
    Base,
    Boolean,
    ForeignKey,
    Mapped,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    mapped_column,
)
from app.models.mixins import TimestampMixin

# Stable Prosohm tenant — used as default for all existing deployments.
PROSOHM_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
PROSOHM_TENANT_SLUG = "prosohm"


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    edition: Mapped[str] = mapped_column(String(32), nullable=False, default="enterprise")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Extensible tenant config (terminology, numbering) — JSON text.
    terminology_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    numbering_policy_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class FeatureFlag(Base, TimestampMixin):
    """Per-tenant feature flag state (resolved against edition defaults)."""

    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_feature_flag_tenant_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
