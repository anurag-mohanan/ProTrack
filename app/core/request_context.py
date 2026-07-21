"""Per-request context for audit enrichment (client IP, user agent).

Populated by the request-logging middleware and read by the activity/audit
logger so every audited action can record where it came from without threading
the ``Request`` object through every service call.
"""

from __future__ import annotations

from contextvars import ContextVar

_client_ip: ContextVar[str | None] = ContextVar("protrack_client_ip", default=None)
_user_agent: ContextVar[str | None] = ContextVar("protrack_user_agent", default=None)


def set_request_context(ip: str | None, user_agent: str | None) -> None:
    _client_ip.set(ip)
    _user_agent.set((user_agent or "")[:255] or None)


def get_client_ip() -> str | None:
    return _client_ip.get()


def get_user_agent() -> str | None:
    return _user_agent.get()
