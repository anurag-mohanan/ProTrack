"""IT Operations: assets, computers, networks, IP, accounts, settings."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, UniqueConstraint
from app.models.mixins import TenantMixin, TimestampMixin


class ITSettings(Base, TimestampMixin, TenantMixin):
    __tablename__ = "it_settings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_numbering_pattern: Mapped[str] = mapped_column(
        String(100), nullable=False, default="{prefix}-{seq:04d}"
    )
    computer_naming_pattern: Mapped[str] = mapped_column(
        String(100), nullable=False, default="PRO-{type}{seq:03d}"
    )
    default_domain: Mapped[Optional[str]] = mapped_column(String(100))
    default_email_domain: Mapped[Optional[str]] = mapped_column(String(100))
    ip_allocation_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="sequential"
    )
    next_asset_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    next_computer_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    settings_json: Mapped[Optional[str]] = mapped_column(Text)


class AssetType(Base, TimestampMixin, TenantMixin):
    __tablename__ = "asset_types"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_asset_types_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    numbering_prefix: Mapped[Optional[str]] = mapped_column(String(10))

    assets: Mapped[list["Asset"]] = relationship(back_populates="asset_type")


class Asset(Base, TimestampMixin, TenantMixin):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_number", name="uq_assets_tenant_asset_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("asset_types.id"), nullable=False, index=True
    )
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    make: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", index=True)
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    purchase_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    warranty_expiry: Mapped[Optional[date]] = mapped_column(Date)
    location: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    asset_type: Mapped[AssetType] = relationship(back_populates="assets")
    computer: Mapped[Optional["Computer"]] = relationship(back_populates="asset", uselist=False)
    assignments: Mapped[list["AssetAssignment"]] = relationship(
        back_populates="asset", order_by="AssetAssignment.assigned_date.desc()"
    )


class Computer(Base, TimestampMixin, TenantMixin):
    __tablename__ = "computers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "computer_name", name="uq_computers_tenant_computer_name"),
        UniqueConstraint("tenant_id", "asset_id", name="uq_computers_tenant_asset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    computer_name: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    os: Mapped[Optional[str]] = mapped_column(String(60))
    processor: Mapped[Optional[str]] = mapped_column(String(100))
    ram_gb: Mapped[Optional[int]] = mapped_column(Integer)
    storage_type: Mapped[Optional[str]] = mapped_column(String(20))
    storage_gb: Mapped[Optional[int]] = mapped_column(Integer)
    domain_joined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17))

    asset: Mapped[Asset] = relationship(back_populates="computer")


class AssetAssignment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "asset_assignments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    assigned_to_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    returned_date: Mapped[Optional[date]] = mapped_column(Date)
    return_condition: Mapped[Optional[str]] = mapped_column(String(40))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="assignments")


class Network(Base, TimestampMixin, TenantMixin):
    __tablename__ = "networks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cidr: Mapped[str] = mapped_column(String(18), nullable=False)
    gateway: Mapped[Optional[str]] = mapped_column(String(15))
    dns_primary: Mapped[Optional[str]] = mapped_column(String(15))
    dns_secondary: Mapped[Optional[str]] = mapped_column(String(15))
    vlan_id: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ip_addresses: Mapped[list["IPAddress"]] = relationship(
        back_populates="network", cascade="all, delete-orphan"
    )


class IPAddress(Base, TimestampMixin, TenantMixin):
    __tablename__ = "ip_addresses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "address", name="uq_ip_addresses_tenant_address"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    network_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("networks.id"), nullable=False, index=True
    )
    address: Mapped[str] = mapped_column(String(15), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", index=True)
    allocation_type: Mapped[Optional[str]] = mapped_column(String(20))

    network: Mapped[Network] = relationship(back_populates="ip_addresses")
    assignment_history: Mapped[list["IPAssignmentHistory"]] = relationship(
        back_populates="ip_address", order_by="IPAssignmentHistory.assigned_date.desc()"
    )


class IPAssignmentHistory(Base, TimestampMixin, TenantMixin):
    __tablename__ = "ip_assignment_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ip_addresses.id"), nullable=False, index=True
    )
    assigned_to_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=True
    )
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    hostname: Mapped[Optional[str]] = mapped_column(String(60))
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    released_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    ip_address: Mapped[IPAddress] = relationship(back_populates="assignment_history")


class ITUserAccount(Base, TimestampMixin, TenantMixin):
    """Account metadata only — NEVER store secrets/passwords here."""

    __tablename__ = "it_user_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    account_type: Mapped[str] = mapped_column(String(40), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(120))
    display_name: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_date: Mapped[Optional[date]] = mapped_column(Date)
    deactivated_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
