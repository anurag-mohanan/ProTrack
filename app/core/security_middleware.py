"""HTTP edge-hardening middleware: security headers and request-body caps."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import ENABLE_HSTS, MAX_REQUEST_BODY_BYTES

# Paths that render the interactive API docs; they need a relaxed CSP because
# Swagger UI / ReDoc load assets from a CDN and use inline styles.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

_STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
_DOCS_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        is_docs = any(request.url.path.startswith(p) for p in _DOCS_PATHS)
        headers.setdefault("Content-Security-Policy", _DOCS_CSP if is_docs else _STRICT_CSP)

        if ENABLE_HSTS:
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose declared body exceeds the configured cap.

    This is the primary defence against memory-exhaustion DoS from large
    uploads; per-endpoint checks provide friendlier messages for files.
    """

    def __init__(self, app, max_body_bytes: int = MAX_REQUEST_BODY_BYTES):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large."},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )
        return await call_next(request)
