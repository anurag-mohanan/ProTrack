"""Request bodies for the IT inventory (stock) and Virtual Seat APIs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StockItemBase(BaseModel):
    description: Optional[str] = None
    item_kind: Optional[str] = Field(default=None, max_length=40)
    sku: Optional[str] = Field(default=None, max_length=60)
    supplier_id: Optional[UUID] = None
    supplier_sku: Optional[str] = Field(default=None, max_length=80)
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    min_stock: Optional[int] = Field(default=None, ge=0)
    reorder_point: Optional[int] = Field(default=None, ge=0)
    target_stock: Optional[int] = Field(default=None, ge=0)
    reorder_qty: Optional[int] = Field(default=None, ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0)
    is_returnable: Optional[bool] = None
    location_id: Optional[UUID] = None
    notes: Optional[str] = None


class StockItemCreate(StockItemBase):
    name: str = Field(min_length=1, max_length=200)
    opening_qty: int = Field(default=0, ge=0)


class StockItemUpdate(StockItemBase):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)


class StockReceive(BaseModel):
    quantity: int = Field(gt=0)
    received_on: Optional[date] = None
    supplier_id: Optional[UUID] = None
    purchase_order: Optional[str] = Field(default=None, max_length=80)
    invoice_number: Optional[str] = Field(default=None, max_length=80)
    unit_cost: Optional[Decimal] = Field(default=None, ge=0)
    restock_request_id: Optional[UUID] = None
    notes: Optional[str] = None


class StockIssue(BaseModel):
    quantity: int = Field(gt=0)
    employee_user_id: UUID
    reason: Optional[str] = Field(default=None, max_length=300)
    reference: Optional[str] = Field(default=None, max_length=120)
    reservation_id: Optional[UUID] = None
    ticket_id: Optional[UUID] = None
    issued_on: Optional[date] = None


class StockReturn(BaseModel):
    quantity: int = Field(gt=0)
    issue_movement_id: Optional[UUID] = None
    employee_user_id: Optional[UUID] = None
    reason: Optional[str] = Field(default=None, max_length=300)


class StockAdjust(BaseModel):
    counted_qty: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=300)


class StockWriteOff(BaseModel):
    movement_type: Literal["damage", "dispose"]
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=300)


class StockTransfer(BaseModel):
    quantity: int = Field(gt=0)
    to_location_id: UUID
    reason: Optional[str] = Field(default=None, max_length=300)


class StockReserve(BaseModel):
    quantity: int = Field(gt=0)
    for_user_id: Optional[UUID] = None
    ticket_id: Optional[UUID] = None
    provisioning_request_id: Optional[UUID] = None
    reason: Optional[str] = Field(default=None, max_length=300)


class ReservationRelease(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class RestockCreate(BaseModel):
    item_id: UUID
    quantity: Optional[int] = Field(default=None, gt=0)
    supplier_id: Optional[UUID] = None
    expected_date: Optional[date] = None
    notes: Optional[str] = None


class RestockUpdate(BaseModel):
    status: Literal["ordered", "cancelled"]
    purchase_order: Optional[str] = Field(default=None, max_length=80)
    expected_date: Optional[date] = None
    notes: Optional[str] = None


class StockLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: Optional[str] = None


class SeatRequirementLine(BaseModel):
    role: str = Field(min_length=1, max_length=40)
    required: int = Field(ge=0, le=8)
    recommended: int = Field(ge=0, le=8)


class SeatRequirementsUpdate(BaseModel):
    lines: list[SeatRequirementLine]
