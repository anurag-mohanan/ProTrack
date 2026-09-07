"""Resource Planning shifts — shift masters and effective-dated assignments.

Deliberately separate from ``User.working_model`` (commercial billing) and from
``User.working_hours_per_day`` (the fallback capacity baseline). A shift says
*when* somebody works; the working model says *how* they are billed.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, UniqueConstraint
from app.models.mixins import TenantMixin, TimestampMixin

ASSIGNMENT_TYPE_PERMANENT = "permanent"
ASSIGNMENT_TYPE_ROTATIONAL = "rotational"
ASSIGNMENT_TYPES = frozenset({ASSIGNMENT_TYPE_PERMANENT, ASSIGNMENT_TYPE_ROTATIONAL})

ROTATION_PATTERNS = frozenset({"daily", "weekly", "biweekly", "monthly", "custom"})


class ResourceShift(Base, TimestampMixin, TenantMixin):
    """A named working window (Day / Evening / Night / custom)."""

    __tablename__ = "rp_shifts"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_rp_shifts_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # "HH:MM" 24h wall-clock. Stored as text so SQLite/Postgres behave identically
    # and so an overnight shift needs no date arithmetic at rest.
    start_time: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    end_time: Mapped[str] = mapped_column(String(5), nullable=False, default="18:00")
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_overnight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    assignments: Mapped[list["ResourceShiftAssignment"]] = relationship(
        back_populates="shift",
    )


class ResourceShiftAssignment(Base, TimestampMixin, TenantMixin):
    """Who is on which shift, over which effective period.

    Rows are never rewritten when a shift changes — the previous row is
    end-dated and a new one is opened, so history stays queryable.
    """

    __tablename__ = "rp_shift_assignments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rp_shifts.id"), nullable=False, index=True
    )
    assignment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ASSIGNMENT_TYPE_PERMANENT
    )
    rotation_pattern: Mapped[Optional[str]] = mapped_column(String(20))
    # JSON payload for rotational assignments, e.g.
    # {"weekdays": [0, 1, 2], "cycle_index": 0, "days_of_month": [1, 15]}
    rotation_json: Mapped[Optional[str]] = mapped_column(Text)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    shift: Mapped[ResourceShift] = relationship(back_populates="assignments")
