"""Application rate limiter (slowapi).

Applied primarily to authentication endpoints to blunt credential brute-forcing.
Disabled automatically under pytest so the test-suite's rapid logins don't trip
the limiter.

``slowapi`` is treated as an *optional* dependency: if it is not installed the
app still boots with rate limiting silently disabled, rather than crashing on
import. This keeps a running deployment alive if requirements were not yet
reinstalled after an upgrade. Install ``requirements.txt`` to restore limiting.

All slowapi symbols the rest of the app needs (``limiter``,
``RateLimitExceeded``, ``rate_limit_exceeded_handler``) are re-exported here so
there is a single import site guarded by the availability check.
"""

from __future__ import annotations

import logging
import sys

from starlette.responses import JSONResponse

from app.core.config import AUTH_RATE_LIMIT, RATE_LIMIT_ENABLED

logger = logging.getLogger("protrack.startup")

# Limit string applied to auth endpoints (e.g. "10/minute").
AUTH_LIMIT = AUTH_RATE_LIMIT

try:
    from slowapi import Limiter
    from slowapi import _rate_limit_exceeded_handler as _slowapi_handler
    from slowapi.errors import RateLimitExceeded as _SlowApiRateLimitExceeded
    from slowapi.util import get_remote_address

    _SLOWAPI_AVAILABLE = True
except Exception:  # ImportError, or any load-time failure
    _SLOWAPI_AVAILABLE = False


if _SLOWAPI_AVAILABLE:
    _enabled = RATE_LIMIT_ENABLED and "pytest" not in sys.modules
    limiter = Limiter(
        key_func=get_remote_address,
        enabled=_enabled,
        default_limits=[],
    )
    RateLimitExceeded = _SlowApiRateLimitExceeded
    rate_limit_exceeded_handler = _slowapi_handler
else:
    logger.warning(
        "slowapi is not installed; rate limiting is disabled. "
        "Run 'pip install -r requirements.txt' to enable it."
    )

    class RateLimitExceeded(Exception):  # noqa: N818 — mirrors slowapi's name
        """Placeholder so exception-handler registration stays valid."""

    class _NoopLimiter:
        """Drop-in limiter whose ``limit`` decorator does nothing."""

        enabled = False

        def limit(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    limiter = _NoopLimiter()

    def rate_limit_exceeded_handler(_request, _exc):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
