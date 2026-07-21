"""Application rate limiter (slowapi).

Applied primarily to authentication endpoints to blunt credential brute-forcing.
Disabled automatically under pytest so the test-suite's rapid logins don't trip
the limiter.
"""

from __future__ import annotations

import sys

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import AUTH_RATE_LIMIT, RATE_LIMIT_ENABLED

_enabled = RATE_LIMIT_ENABLED and "pytest" not in sys.modules

limiter = Limiter(
    key_func=get_remote_address,
    enabled=_enabled,
    default_limits=[],
)

# Limit string applied to auth endpoints (e.g. "10/minute").
AUTH_LIMIT = AUTH_RATE_LIMIT
