"""Commercial readiness — sign-offs, design partners, trust checks (R10-010)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.db.base import (
    Base,
    Boolean,
    DateTime,
    Mapped,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    mapped_column,
)
from app.models.mixins import TenantMixin, TimestampMixin


class CommercialSignoff(Base, TimestampMixin, TenantMixin):
    __tablename__ = "commercial_signoffs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_commercial_signoffs_tenant_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    signer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signer_role: Mapped[str] = mapped_column(String(80), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    evidence_url: Mapped[Optional[str]] = mapped_column(String(500))


class DesignPartner(Base, TimestampMixin, TenantMixin):
    __tablename__ = "design_partners"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    icp: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    contact_name: Mapped[Optional[str]] = mapped_column(String(200))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    loi_doc_ref: Mapped[Optional[str]] = mapped_column(String(255))
    loi_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    loi_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)


class TrustControlCheck(Base, TimestampMixin, TenantMixin):
    __tablename__ = "trust_control_checks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "control_id", name="uq_trust_control_tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    control_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="med")
    must_fix: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    owner: Mapped[Optional[str]] = mapped_column(String(120))
    evidence_notes: Mapped[Optional[str]] = mapped_column(Text)
    doc_path: Mapped[Optional[str]] = mapped_column(String(255))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
