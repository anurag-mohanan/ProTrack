"""TTL cache for expensive AI computations."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any


class AiCache:
    """In-process TTL cache. Swap for Redis in multi-worker deployments."""

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl_seconds

    def _key(self, namespace: str, params: dict[str, Any]) -> str:
        payload = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"{namespace}:{digest}"

    def get(self, namespace: str, params: dict[str, Any]) -> Any | None:
        key = self._key(namespace, params)
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(
        self,
        namespace: str,
        params: dict[str, Any],
        value: Any,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        key = self._key(namespace, params)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._store[key] = (time.time() + ttl, value)

    def invalidate_namespace(self, namespace: str) -> None:
        prefix = f"{namespace}:"
        for key in list(self._store):
            if key.startswith(prefix):
                del self._store[key]


ai_cache = AiCache()
