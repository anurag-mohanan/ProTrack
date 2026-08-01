"""Per-request context for audit enrichment and commercial tenancy.

Populated by request middleware and read by services without threading Request.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

_client_ip: ContextVar[str | None] = ContextVar("protrack_client_ip", default=None)
_user_agent: ContextVar[str | None] = ContextVar("protrack_user_agent", default=None)
_tenant_id: ContextVar[UUID | None] = ContextVar("protrack_tenant_id", default=None)


def set_request_context(ip: str | None, user_agent: str | None) -> None:
    _client_ip.set(ip)
    _user_agent.set((user_agent or "")[:255] or None)


def set_tenant_id(tenant_id: UUID | None) -> None:
    _tenant_id.set(tenant_id)


def get_client_ip() -> str | None:
    return _client_ip.get()


def get_user_agent() -> str | None:
    return _user_agent.get()


def get_tenant_id() -> UUID | None:
    return _tenant_id.get()
