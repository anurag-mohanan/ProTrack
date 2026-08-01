from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

# Keep in sync with app.models.commercial.PROSOHM_TENANT_ID (avoid circular import at class body).
_PROSOHM_TENANT_ID_LITERAL = "00000000-0000-4000-8000-000000000001"


def _default_tenant_id() -> UUID:
    from app.core.request_context import get_tenant_id
    from app.models.commercial import PROSOHM_TENANT_ID

    return get_tenant_id() or PROSOHM_TENANT_ID


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Commercial tenancy — default Prosohm / request tenant (R10 M1)."""

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=_default_tenant_id,
        insert_default=_default_tenant_id,
        # Allows legacy raw SQL seeds that omit tenant_id (phase syncers).
        # Phase70 normalizes SQLite storage to hex to match ORM Uuid binding.
        server_default=text(f"'{_PROSOHM_TENANT_ID_LITERAL}'"),
    )
