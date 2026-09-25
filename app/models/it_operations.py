"""IT Operations: assets, computers, networks, IP, accounts, settings."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    {"available", "assigned", "reserved", "maintenance", "awaiting_return"}
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
    # Computing class for primary devices (ENG_WS, GENERAL_LAPTOP, …); null for peripherals.
    computer_type: Mapped[Optional[str]] = mapped_column(String(40), index=True)
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
    number_history: Mapped[list["AssetNumberHistory"]] = relationship(
        back_populates="asset", order_by="AssetNumberHistory.effective_from.desc()"
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
    # Imported snapshot quantities (kept for lineage); stock control uses on_hand_qty.
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

    # Stock control (quantity-based; never one Asset per unit)
    item_kind: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    on_hand_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_stock: Mapped[Optional[int]] = mapped_column(Integer)
    reorder_point: Mapped[Optional[int]] = mapped_column(Integer)
    target_stock: Mapped[Optional[int]] = mapped_column(Integer)
    reorder_qty: Mapped[Optional[int]] = mapped_column(Integer)
    supplier_sku: Mapped[Optional[str]] = mapped_column(String(80))
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    last_purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    last_purchase_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    is_returnable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_stock_locations.id"), nullable=True, index=True
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
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))

    asset: Mapped[Asset] = relationship(back_populates="computer")
    interfaces: Mapped[list["ComputerNetworkInterface"]] = relationship(
        back_populates="computer",
        cascade="all, delete-orphan",
        order_by="ComputerNetworkInterface.is_primary.desc(), ComputerNetworkInterface.name",
    )
    name_history: Mapped[list["ComputerNameHistory"]] = relationship(
        back_populates="computer",
        order_by="ComputerNameHistory.effective_from.desc()",
    )


class ComputerNetworkInterface(Base, TimestampMixin, TenantMixin):
    """Physical/virtual NIC on a computer — enables intentional multi-homing."""

    __tablename__ = "computer_network_interfaces"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "computer_id",
            "name",
            name="uq_computer_nics_tenant_computer_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    computer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("computers.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    # lan | wifi | vpn | other
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="lan")
    mac_address: Mapped[Optional[str]] = mapped_column(String(17))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    computer: Mapped[Computer] = relationship(back_populates="interfaces")


class ComputerNameHistory(Base, TimestampMixin, TenantMixin):
    """Effective-dated computer names — never rewritten or recycled."""

    __tablename__ = "it_computer_name_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    computer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("computers.id"), nullable=False, index=True
    )
    computer_name: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    computer: Mapped["Computer"] = relationship(back_populates="name_history")


# AssetAssignment.assignment_type values
ASSIGNMENT_TYPE_PRIMARY = "PRIMARY"
ASSIGNMENT_TYPE_SHIFT_SHARED = "SHIFT_SHARED"
ASSIGNMENT_TYPE_TEMPORARY = "TEMPORARY"
ASSIGNMENT_TYPE_BACKUP = "BACKUP"
ASSET_ASSIGNMENT_TYPES = frozenset(
    {
        ASSIGNMENT_TYPE_PRIMARY,
        ASSIGNMENT_TYPE_SHIFT_SHARED,
        ASSIGNMENT_TYPE_TEMPORARY,
        ASSIGNMENT_TYPE_BACKUP,
    }
)

# Onboarding computer type codes (requirement only — not asset numbers)
COMPUTER_TYPE_ENG_WS = "ENG_WS"
COMPUTER_TYPE_GENERAL_WS = "GENERAL_WS"
COMPUTER_TYPE_IT_WS = "IT_WS"
COMPUTER_TYPE_ENG_LAPTOP = "ENG_LAPTOP"
COMPUTER_TYPE_GENERAL_LAPTOP = "GENERAL_LAPTOP"
COMPUTER_TYPES = frozenset(
    {
        COMPUTER_TYPE_ENG_WS,
        COMPUTER_TYPE_GENERAL_WS,
        COMPUTER_TYPE_IT_WS,
        COMPUTER_TYPE_ENG_LAPTOP,
        COMPUTER_TYPE_GENERAL_LAPTOP,
    }
)
COMPUTER_TYPE_LABELS = {
    COMPUTER_TYPE_ENG_WS: "Engineering Workstation",
    COMPUTER_TYPE_GENERAL_WS: "General Workstation",
    COMPUTER_TYPE_IT_WS: "IT Workstation",
    COMPUTER_TYPE_ENG_LAPTOP: "Engineering Laptop",
    COMPUTER_TYPE_GENERAL_LAPTOP: "General Laptop",
}
LAPTOP_COMPUTER_TYPES = frozenset({COMPUTER_TYPE_ENG_LAPTOP, COMPUTER_TYPE_GENERAL_LAPTOP})

PROVISIONING_STATUSES = frozenset(
    {
        "OPEN",
        "IN_PROGRESS",
        "WAITING_FOR_ASSET",
        "WAITING_FOR_LICENSE",
        "READY",
        "COMPLETED",
        "REJECTED",
        "CANCELLED",
    }
)
PROVISIONING_TERMINAL = frozenset({"COMPLETED", "REJECTED", "CANCELLED"})

SOFTWARE_REQUIREMENT_STATUSES = frozenset(
    {
        "REQUESTED",
        "UNDER_REVIEW",
        "APPROVED",
        "AVAILABLE",
        "LICENSE_ASSIGNED",
        "INSTALLATION_PENDING",
        "INSTALLED",
        "LICENSE_NOT_AVAILABLE",
        "REJECTED",
        "CANCELLED",
    }
)

DEFAULT_MONITOR_MAX = 4
ONBOARDING_SOFTWARE_MAX = 5


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
    # Optional shift slot for shared desks (First/Second/General). Null = legacy single assignee.
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rp_shifts.id"), nullable=True, index=True
    )
    assignment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ASSIGNMENT_TYPE_PRIMARY
    )
    override_reason: Mapped[Optional[str]] = mapped_column(String(500))
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    returned_date: Mapped[Optional[date]] = mapped_column(Date)
    return_condition: Mapped[Optional[str]] = mapped_column(String(40))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="assignments")


class AssetNumberHistory(Base, TimestampMixin, TenantMixin):
    """Effective-dated asset numbers — never rewritten or recycled."""

    __tablename__ = "it_asset_number_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    asset_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    asset: Mapped["Asset"] = relationship(back_populates="number_history")


class AssetOwnershipHistory(Base, TimestampMixin, TenantMixin):
    """Effective-dated ownership periods — never rewritten."""

    __tablename__ = "asset_ownership_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    purchased_by: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)


class AssetLocationHistory(Base, TimestampMixin, TenantMixin):
    """Effective-dated location periods — never rewritten."""

    __tablename__ = "asset_location_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    location: Mapped[Optional[str]] = mapped_column(String(120))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)


class AssetStatusHistory(Base, TimestampMixin, TenantMixin):
    """Effective-dated status/maintenance periods — never rewritten."""

    __tablename__ = "asset_status_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)


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
    # Optional NIC binding for multi-homed computers.
    interface_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("computer_network_interfaces.id"), nullable=True, index=True
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

# Commercial entitlement (how the right to use is sold) — separate from assignment model.
COMMERCIAL_MODELS = frozenset({"perpetual", "subscription"})

# How seats are consumed (named user / floating / device …).
ASSIGNMENT_LICENSE_TYPES = frozenset(
    {
        "named_user",
        "floating",
        "concurrent",
        "device_bound",
        "network",
        "other",
    }
)

RENEWAL_FREQUENCIES = frozenset(
    {
        "monthly",
        "quarterly",
        "half_yearly",
        "yearly",
        "every_2_years",
        "custom",
    }
)

LICENSE_POOL_STATUSES = frozenset(
    {
        "draft",
        "active",
        "suspended",
        "terminated",
        "cancelled",
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
    """Purchased license entitlement (seat pool) linked optionally to a Finance expense."""

    __tablename__ = "software_license_pools"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    software_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("software_catalog.id"), nullable=False, index=True
    )
    entitlement_code: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    purchased_by: Mapped[str] = mapped_column(
        String(40), nullable=False, default="organization", index=True
    )
    owner_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Legacy mixed field; prefer commercial_model + assignment_model going forward.
    license_type: Mapped[Optional[str]] = mapped_column(String(40))
    commercial_model: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    assignment_model: Mapped[Optional[str]] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[Optional[str]] = mapped_column(String(3))
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    renewal_mode: Mapped[Optional[str]] = mapped_column(String(80))
    subscription_start_date: Mapped[Optional[date]] = mapped_column(Date)
    renewal_frequency: Mapped[Optional[str]] = mapped_column(String(40))
    renewal_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    renewal_notice_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    amc_required: Mapped[Optional[bool]] = mapped_column(Boolean)
    amc_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    amc_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    amc_amount_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    amc_start_date: Mapped[Optional[date]] = mapped_column(Date)
    amc_due_date: Mapped[Optional[date]] = mapped_column(Date)
    amc_vendor: Mapped[Optional[str]] = mapped_column(String(200))
    terminated_at: Mapped[Optional[date]] = mapped_column(Date)
    termination_reason: Mapped[Optional[str]] = mapped_column(String(200))
    terminated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    expense_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("expenses.id"), nullable=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_import_batches.id"), nullable=True, index=True
    )
    source_system: Mapped[Optional[str]] = mapped_column(String(120))


class SoftwareLicenseRenewal(Base, TimestampMixin, TenantMixin):
    """Immutable renewal / AMC history rows for a license entitlement."""

    __tablename__ = "software_license_renewals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_pool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("software_license_pools.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="subscription")
    # subscription | amc
    period_start: Mapped[Optional[date]] = mapped_column(Date)
    period_end: Mapped[Optional[date]] = mapped_column(Date)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[Optional[str]] = mapped_column(String(3))
    expense_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("expenses.id"), nullable=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    recorded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


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


class SoftwareInstallation(Base, TimestampMixin, TenantMixin):
    """Software present on a computer — distinct from a license seat assignment."""

    __tablename__ = "software_installations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    computer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("computers.id"), nullable=False, index=True
    )
    software_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("software_catalog.id"), nullable=False, index=True
    )
    installed_date: Mapped[date] = mapped_column(Date, nullable=False)
    uninstalled_date: Mapped[Optional[date]] = mapped_column(Date)
    installed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)


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
    provisioning_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("it_provisioning_requests.id"),
        nullable=True,
        index=True,
    )
    license_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    purpose: Mapped[Optional[str]] = mapped_column(String(500))
    requested_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="REQUESTED")


class ResourcePackage(Base, TimestampMixin, TenantMixin):
    """Requirement template (not inventory). Hardware/software lines describe a typical setup."""

    __tablename__ = "it_resource_packages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_it_resource_packages_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    requires_ip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    hardware_lines: Mapped[list["ResourcePackageHardwareLine"]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="ResourcePackageHardwareLine.created_at",
    )
    software_lines: Mapped[list["ResourcePackageSoftwareLine"]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="ResourcePackageSoftwareLine.created_at",
    )


class ResourcePackageHardwareLine(Base, TimestampMixin, TenantMixin):
    __tablename__ = "it_resource_package_hardware_lines"
    __table_args__ = (
        UniqueConstraint(
            "package_id",
            "asset_type_id",
            name="uq_it_resource_package_hw_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_resource_packages.id"), nullable=False, index=True
    )
    asset_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("asset_types.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    package: Mapped[ResourcePackage] = relationship(back_populates="hardware_lines")
    asset_type: Mapped[AssetType] = relationship()


class ResourcePackageSoftwareLine(Base, TimestampMixin, TenantMixin):
    __tablename__ = "it_resource_package_software_lines"
    __table_args__ = (
        UniqueConstraint(
            "package_id",
            "software_id",
            name="uq_it_resource_package_sw",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_resource_packages.id"), nullable=False, index=True
    )
    software_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("software_catalog.id"), nullable=False, index=True
    )
    requirement_level: Mapped[str] = mapped_column(String(20), nullable=False, default="required")
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    package: Mapped[ResourcePackage] = relationship(back_populates="software_lines")
    software: Mapped["SoftwareCatalog"] = relationship()


class ItProvisioningRequest(Base, TimestampMixin, TenantMixin):
    """Structured IT onboarding request (requirements) linked to Help Desk ticket."""

    __tablename__ = "it_provisioning_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    checklist_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("onboarding_checklists.id"), nullable=True
    )
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id"), nullable=True, index=True
    )
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rp_shifts.id"), nullable=True
    )
    required_by: Mapped[Optional[date]] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="OPEN", index=True)
    assigned_it_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    hardware: Mapped[Optional["ItProvisioningHardware"]] = relationship(
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
    )
    software_requirements: Mapped[list["EmployeeSoftwareRequirement"]] = relationship(
        foreign_keys="EmployeeSoftwareRequirement.provisioning_request_id",
        primaryjoin=(
            "ItProvisioningRequest.id == EmployeeSoftwareRequirement.provisioning_request_id"
        ),
        viewonly=True,
    )


class ItProvisioningHardware(Base, TimestampMixin, TenantMixin):
    """Hardware requirements for an IT provisioning request (not asset assignment)."""

    __tablename__ = "it_provisioning_hardware"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provisioning_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("it_provisioning_requests.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    computer_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    computer_type: Mapped[Optional[str]] = mapped_column(String(40))
    computer_is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    monitor_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monitor_is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mouse_3d_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mouse_3d_is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mouse_3d_model_hint: Mapped[Optional[str]] = mapped_column(String(200))
    mouse_3d_asset_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("asset_types.id"), nullable=True
    )
    wireless_mouse_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    laptop_dock_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    laptop_bag_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    headset_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    wireless_keyboard_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    request: Mapped["ItProvisioningRequest"] = relationship(back_populates="hardware")


# --- Physical workstation equipment packages (distinct from ResourcePackage templates) ---

PACKAGE_STATUS_ACTIVE = "ACTIVE"
PACKAGE_STATUS_MAINTENANCE = "MAINTENANCE"
PACKAGE_STATUS_INCOMPLETE = "INCOMPLETE"
PACKAGE_STATUS_RETIRED = "RETIRED"
PACKAGE_STATUSES = frozenset(
    {
        PACKAGE_STATUS_ACTIVE,
        PACKAGE_STATUS_MAINTENANCE,
        PACKAGE_STATUS_INCOMPLETE,
        PACKAGE_STATUS_RETIRED,
    }
)

MEMBER_ROLE_PRIMARY_COMPUTER = "PRIMARY_COMPUTER"
MEMBER_ROLE_PRIMARY_MONITOR = "PRIMARY_MONITOR"
MEMBER_ROLE_SECONDARY_MONITOR = "SECONDARY_MONITOR"
MEMBER_ROLE_3D_MOUSE = "3D_MOUSE"
MEMBER_ROLE_WIRELESS_MOUSE = "WIRELESS_MOUSE"
MEMBER_ROLE_KEYBOARD = "KEYBOARD"
MEMBER_ROLE_DOCK = "DOCK"
MEMBER_ROLE_BAG = "BAG"
MEMBER_ROLE_HEADSET = "HEADSET"
MEMBER_ROLE_OTHER = "OTHER"
MEMBER_ROLES = frozenset(
    {
        MEMBER_ROLE_PRIMARY_COMPUTER,
        MEMBER_ROLE_PRIMARY_MONITOR,
        MEMBER_ROLE_SECONDARY_MONITOR,
        MEMBER_ROLE_3D_MOUSE,
        MEMBER_ROLE_WIRELESS_MOUSE,
        MEMBER_ROLE_KEYBOARD,
        MEMBER_ROLE_DOCK,
        MEMBER_ROLE_BAG,
        MEMBER_ROLE_HEADSET,
        MEMBER_ROLE_OTHER,
    }
)

SHIFT_AVAIL_AVAILABLE = "AVAILABLE"
SHIFT_AVAIL_ASSIGNED = "ASSIGNED"
SHIFT_AVAIL_CONFLICT = "CONFLICT"
SHIFT_AVAIL_PARTIAL = "PARTIALLY_AVAILABLE"
SHIFT_AVAIL_UNAVAILABLE = "UNAVAILABLE"


class WorkstationPackage(Base, TimestampMixin, TenantMixin):
    """Physical equipment grouping: one computer + peripherals (not a requirement template)."""

    __tablename__ = "it_workstation_packages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_it_workstation_packages_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_computer_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    computer_type: Mapped[Optional[str]] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=PACKAGE_STATUS_ACTIVE)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    members: Mapped[list["WorkstationPackageMember"]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="WorkstationPackageMember.created_at",
    )
    assignments: Mapped[list["WorkstationPackageAssignment"]] = relationship(
        back_populates="package",
        cascade="all, delete-orphan",
    )


class WorkstationPackageMember(Base, TimestampMixin, TenantMixin):
    """Effective-dated package membership for a physical asset."""

    __tablename__ = "it_workstation_package_members"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_workstation_packages.id"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    follows_workstation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    removed_reason: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    package: Mapped["WorkstationPackage"] = relationship(back_populates="members")


class WorkstationPackageAssignment(Base, TimestampMixin, TenantMixin):
    """Employee + shift + date-range assignment of an entire workstation package."""

    __tablename__ = "it_workstation_package_assignments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_workstation_packages.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rp_shifts.id"), nullable=False, index=True
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    override_reason: Mapped[Optional[str]] = mapped_column(String(500))
    provisioning_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_provisioning_requests.id"), nullable=True
    )

    package: Mapped["WorkstationPackage"] = relationship(back_populates="assignments")


# --- Virtual Seats (logical; derived from AssetAssignment) ---


class VirtualSeat(Base, TimestampMixin, TenantMixin):
    """Stable identity for a derived seat: employee + shift slot + primary computing device.

    Holds no asset data. Components are always read live from AssetAssignment.
    """

    __tablename__ = "it_virtual_seats"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_it_virtual_seats_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rp_shifts.id"), nullable=True, index=True
    )
    primary_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True
    )
    primary_assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("asset_assignments.id"), nullable=True
    )
    # active | ended
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[Optional[date]] = mapped_column(Date)
    # Last observed component asset ids (JSON list) — only used to audit add/remove.
    component_snapshot: Mapped[Optional[str]] = mapped_column(Text)


# --- Consumable stock control ---

STOCK_MOVEMENT_RECEIVE = "receive"
STOCK_MOVEMENT_ISSUE = "issue"
STOCK_MOVEMENT_RETURN = "return"
STOCK_MOVEMENT_ADJUST = "adjust"
STOCK_MOVEMENT_DAMAGE = "damage"
STOCK_MOVEMENT_DISPOSE = "dispose"
STOCK_MOVEMENT_TRANSFER_OUT = "transfer_out"
STOCK_MOVEMENT_TRANSFER_IN = "transfer_in"
STOCK_MOVEMENT_OPENING = "opening_balance"
STOCK_MOVEMENT_TYPES = frozenset(
    {
        STOCK_MOVEMENT_RECEIVE,
        STOCK_MOVEMENT_ISSUE,
        STOCK_MOVEMENT_RETURN,
        STOCK_MOVEMENT_ADJUST,
        STOCK_MOVEMENT_DAMAGE,
        STOCK_MOVEMENT_DISPOSE,
        STOCK_MOVEMENT_TRANSFER_OUT,
        STOCK_MOVEMENT_TRANSFER_IN,
        STOCK_MOVEMENT_OPENING,
    }
)


class StockLocation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "it_stock_locations"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_it_stock_locations_tenant_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StockMovement(Base, TimestampMixin, TenantMixin):
    """Immutable ledger row for every on-hand quantity change."""

    __tablename__ = "it_stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    new_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    performed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    employee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(300))
    reference: Mapped[Optional[str]] = mapped_column(String(120))
    related_movement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_stock_movements.id"), nullable=True
    )
    reservation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_stock_reservations.id"), nullable=True
    )
    restock_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_restock_requests.id"), nullable=True
    )
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id"), nullable=True
    )
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_suppliers.id"), nullable=True
    )
    purchase_order: Mapped[Optional[str]] = mapped_column(String(80))
    invoice_number: Mapped[Optional[str]] = mapped_column(String(80))
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    counterpart_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_stock_locations.id"), nullable=True
    )
    # For issues of returnable items: how many units have come back.
    returned_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class StockReservation(Base, TimestampMixin, TenantMixin):
    """Units held for a request; reduces available (not on-hand) stock."""

    __tablename__ = "it_stock_reservations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # active | fulfilled | released
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    for_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tickets.id"), nullable=True, index=True
    )
    provisioning_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_provisioning_requests.id"), nullable=True, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(300))
    reserved_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    close_reason: Mapped[Optional[str]] = mapped_column(String(300))


class StockAlert(Base, TimestampMixin, TenantMixin):
    """One row per low/out-of-stock episode; resolved when stock is restored."""

    __tablename__ = "it_stock_alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    # low_stock | out_of_stock
    alert_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # active | resolved
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    available_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    min_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class RestockRequest(Base, TimestampMixin, TenantMixin):
    """IT purchase request for a stock item (requested → ordered → received)."""

    __tablename__ = "it_restock_requests"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_it_restock_requests_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # requested | ordered | partially_received | received | cancelled
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="requested", index=True)
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_suppliers.id"), nullable=True
    )
    purchase_order: Mapped[Optional[str]] = mapped_column(String(80))
    expected_date: Mapped[Optional[date]] = mapped_column(Date)
    alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("it_stock_alerts.id"), nullable=True
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
