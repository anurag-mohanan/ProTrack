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

# Ownership codes (labels are tenant-configurable via ITSettings.settings_json).
PURCHASED_BY_CODES = frozenset(
    {"organization", "customer", "vendor", "leased", "other", "unknown"}
)

# Default "current inventory" statuses (returned/disposed/retired excluded).
CURRENT_INVENTORY_STATUSES = frozenset(
    {"available", "assigned", "maintenance", "awaiting_return"}
)


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


class ITImportBatch(Base, TimestampMixin, TenantMixin):
    """One controlled IT Data Import run (preview → commit → optional rollback)."""

    __tablename__ = "it_import_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_code", name="uq_it_import_batches_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    import_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(120))
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # preview | committed | failed | rolled_back | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="preview", index=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    summary_json: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class ITMigrationException(Base, TimestampMixin, TenantMixin):
    """Review-only migration exception rows (not assets)."""

    __tablename__ = "it_migration_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    exception_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(200))
    source_row: Mapped[Optional[str]] = mapped_column(String(40))
    identifier: Mapped[Optional[str]] = mapped_column(String(120))
    issue: Mapped[Optional[str]] = mapped_column(Text)
    action: Mapped[Optional[str]] = mapped_column(Text)
    # open | resolved | dismissed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)


class ITSupplier(Base, TimestampMixin, TenantMixin):
    __tablename__ = "it_suppliers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_it_suppliers_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    email: Mapped[Optional[str]] = mapped_column(String(120))
    address: Mapped[Optional[str]] = mapped_column(Text)
    products: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))


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


class AssetCategory(Base, TimestampMixin, TenantMixin):
    """Reusable IT asset category (e.g. computer, peripheral). Source for cascading."""

    __tablename__ = "it_asset_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_it_asset_categories_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class AssetMake(Base, TimestampMixin, TenantMixin):
    """Reusable make/brand. Linked to asset types for cascading filters."""

    __tablename__ = "it_asset_makes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", name="uq_it_asset_makes_tenant_norm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    type_links: Mapped[list["AssetMakeTypeLink"]] = relationship(
        back_populates="make", cascade="all, delete-orphan"
    )
    models: Mapped[list["AssetModel"]] = relationship(back_populates="make")


class AssetMakeTypeLink(Base, TimestampMixin, TenantMixin):
    """Associates a make with an asset type (Category→Type→Make cascade)."""

    __tablename__ = "it_asset_make_type_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "make_id", "asset_type_id", name="uq_it_asset_make_type_link"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    make_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_asset_makes.id"), nullable=False, index=True
    )
    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("asset_types.id"), nullable=False, index=True
    )

    make: Mapped["AssetMake"] = relationship(back_populates="type_links")
    asset_type: Mapped["AssetType"] = relationship()


class AssetModel(Base, TimestampMixin, TenantMixin):
    """Model under a make + asset type context."""

    __tablename__ = "it_asset_models"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "make_id",
            "asset_type_id",
            "normalized_name",
            name="uq_it_asset_models_ctx_norm",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    make_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_asset_makes.id"), nullable=False, index=True
    )
    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("asset_types.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    make: Mapped["AssetMake"] = relationship(back_populates="models")
    asset_type: Mapped["AssetType"] = relationship()


class Asset(Base, TimestampMixin, TenantMixin):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_number", name="uq_assets_tenant_asset_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    legacy_asset_number: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("asset_types.id"), nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(255))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    service_tag: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    make: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    make_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_asset_makes.id"), nullable=True, index=True
    )
    model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_asset_models.id"), nullable=True, index=True
    )
    parent_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="available", index=True)
    # Ownership (who purchased/owns) — separate from usage and customer_used_for.
    purchased_by: Mapped[str] = mapped_column(
        String(40), nullable=False, default="organization", index=True
    )
    owner_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    customer_used_for_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_suppliers.id"), nullable=True
    )
    invoice_number: Mapped[Optional[str]] = mapped_column(String(80))
    condition: Mapped[Optional[str]] = mapped_column(String(40))
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    purchase_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    warranty_expiry: Mapped[Optional[date]] = mapped_column(Date)
    location: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Durable import lineage (sequential IT Data Import)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))
    source_record_id: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    source_row: Mapped[Optional[int]] = mapped_column(Integer)

    asset_type: Mapped[AssetType] = relationship(back_populates="assets")
    parent_asset: Mapped[Optional["Asset"]] = relationship(
        "Asset",
        remote_side="Asset.id",
        foreign_keys=[parent_asset_id],
        back_populates="child_assets",
    )
    child_assets: Mapped[list["Asset"]] = relationship(
        "Asset",
        foreign_keys=[parent_asset_id],
        back_populates="parent_asset",
    )
    computer: Mapped[Optional["Computer"]] = relationship(back_populates="asset", uselist=False)
    assignments: Mapped[list["AssetAssignment"]] = relationship(
        back_populates="asset", order_by="AssetAssignment.assigned_date.desc()"
    )
    customer_returns: Mapped[list["AssetCustomerReturn"]] = relationship(
        back_populates="asset", order_by="AssetCustomerReturn.return_date.desc()"
    )


class AssetCustomerReturn(Base, TimestampMixin, TenantMixin):
    """History of returning a customer-owned asset to its owner. Never delete the asset."""

    __tablename__ = "asset_customer_returns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    owner_customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    returned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    received_by_name: Mapped[Optional[str]] = mapped_column(String(200))
    condition_at_return: Mapped[Optional[str]] = mapped_column(String(40))
    return_reason: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    original_assignee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    asset: Mapped[Asset] = relationship(back_populates="customer_returns")


class InventoryItem(Base, TimestampMixin, TenantMixin):
    """Non-serialized / consumable stock (not one Asset per unit)."""

    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(40))
    sku: Mapped[Optional[str]] = mapped_column(String(60))
    purchased_by: Mapped[str] = mapped_column(
        String(40), nullable=False, default="organization", index=True
    )
    owner_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_suppliers.id"), nullable=True
    )
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issued_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    location: Mapped[Optional[str]] = mapped_column(String(120))
    condition: Mapped[Optional[str]] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="current")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))
    source_record_id: Mapped[Optional[str]] = mapped_column(String(80), index=True)


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
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))

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
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )

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
    # active | migration_required | reset_required — never holds a password
    credential_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="active"
    )
    created_date: Mapped[Optional[date]] = mapped_column(Date)
    deactivated_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))


LICENSE_TYPE_CODES = frozenset(
    {
        "named_user",
        "floating",
        "concurrent",
        "device_bound",
        "subscription",
        "perpetual",
        "network",
        "other",
    }
)

SOFTWARE_REQUIREMENT_LEVELS = frozenset({"required", "optional"})


class SoftwareCatalog(Base, TimestampMixin, TenantMixin):
    __tablename__ = "software_catalog"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_software_catalog_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    vendor: Mapped[Optional[str]] = mapped_column(String(120))
    version: Mapped[Optional[str]] = mapped_column(String(80))
    edition: Mapped[Optional[str]] = mapped_column(String(80))
    category: Mapped[Optional[str]] = mapped_column(String(80))
    code: Mapped[Optional[str]] = mapped_column(String(40))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SoftwareLicensePool(Base, TimestampMixin, TenantMixin):
    __tablename__ = "software_license_pools"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    software_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("software_catalog.id"), nullable=False, index=True
    )
    purchased_by: Mapped[str] = mapped_column(
        String(40), nullable=False, default="organization", index=True
    )
    owner_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    license_type: Mapped[Optional[str]] = mapped_column(String(40))
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[Optional[str]] = mapped_column(String(3))
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    renewal_mode: Mapped[Optional[str]] = mapped_column(String(80))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))


class SoftwareAssignment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "software_assignments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_pool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("software_license_pools.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    computer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("computers.id"), nullable=True, index=True
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=True, index=True
    )
    assigned_date: Mapped[Optional[date]] = mapped_column(Date)
    released_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    department: Mapped[Optional[str]] = mapped_column(String(100))
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )


class EmployeeSoftwareRequirement(Base, TimestampMixin, TenantMixin):
    """Per-employee software entitlement / role requirement (not a license seat)."""

    __tablename__ = "employee_software_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    software_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("software_catalog.id"), nullable=False, index=True
    )
    # required | optional
    requirement_level: Mapped[str] = mapped_column(String(20), nullable=False, default="required")
    version: Mapped[Optional[str]] = mapped_column(String(80))
    effective_from: Mapped[Optional[date]] = mapped_column(Date)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    reason: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)
