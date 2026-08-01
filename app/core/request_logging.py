"""Structured HTTP request/response logging for API diagnostics."""

from __future__ import annotations

import logging
import time
import traceback
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import set_request_context, set_tenant_id
from app.models.commercial import PROSOHM_TENANT_ID

logger = logging.getLogger("protrack.api")


def _actor_label(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user is None:
        return "anonymous"
    name = " ".join(
        part
        for part in (getattr(user, "first_name", None), getattr(user, "last_name", None))
        if part
    ).strip()
    if name:
        return name
    return getattr(user, "email", None) or str(getattr(user, "id", "unknown"))


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log endpoint, user, parameters, status, elapsed time, and exceptions."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Populate per-request context for audit enrichment.
        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        elif request.client is not None:
            client_ip = request.client.host
        set_request_context(client_ip, request.headers.get("user-agent"))

        # Commercial spine: optional X-Tenant-Id; default Prosohm for continuity.
        raw_tenant = (request.headers.get("x-tenant-id") or "").strip()
        tenant_uuid = PROSOHM_TENANT_ID
        if raw_tenant:
            try:
                from uuid import UUID as _UUID

                tenant_uuid = _UUID(raw_tenant)
            except ValueError:
                tenant_uuid = PROSOHM_TENANT_ID
        set_tenant_id(tenant_uuid)

        started = time.perf_counter()
        params = dict(request.query_params)
        actor = _actor_label(request)
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            logger.error(
                "%s %s\nUser:\n%s\nParameters:\n%s\nElapsed:\n%dms\nStatus:\n%d\nException:\n%s",
                request.method,
                request.url.path,
                actor,
                params or "{}",
                elapsed_ms,
                status_code,
                traceback.format_exc(),
            )
            raise
        finally:
            if response is not None:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                log_fn = logger.warning if status_code >= 400 else logger.info
                log_fn(
                    "%s %s | user=%s | params=%s | elapsed=%dms | status=%d",
                    request.method,
                    request.url.path,
                    actor,
                    params or "{}",
                    elapsed_ms,
                    status_code,
                )
