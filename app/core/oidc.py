"""OIDC / Azure AD helpers (R10 spike).

Enable with ``OIDC_ENABLED=true`` and Entra app credentials.
``OIDC_TESTING=true`` skips IdP for automated tests (fake code exchange).
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import FRONTEND_URL, SECRET_KEY

logger = logging.getLogger("protrack.oidc")

_discovery_cache: dict[str, Any] | None = None


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def oidc_enabled() -> bool:
    return _flag("OIDC_ENABLED")


def oidc_testing() -> bool:
    return _flag("OIDC_TESTING")


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str = "openid profile email"


def oidc_settings() -> OidcSettings | None:
    issuer = (os.getenv("OIDC_ISSUER") or "").strip().rstrip("/")
    client_id = (os.getenv("OIDC_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("OIDC_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("OIDC_REDIRECT_URI") or "").strip()
    if not all([issuer, client_id, client_secret, redirect_uri]):
        return None
    return OidcSettings(
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=(os.getenv("OIDC_SCOPES") or "openid profile email").strip(),
    )


def oidc_configured() -> bool:
    if oidc_testing() and oidc_enabled():
        return True
    return oidc_settings() is not None


def oidc_available() -> bool:
    return oidc_enabled() and oidc_configured()


def frontend_sso_landing() -> str:
    base = (os.getenv("OIDC_FRONTEND_LANDING") or "").strip()
    if base:
        return base
    return f"{FRONTEND_URL.rstrip('/')}/login/sso"


def make_state(nonce: str) -> str:
    payload = {
        "purpose": "oidc",
        "nonce": nonce,
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def parse_state(state: str) -> dict[str, Any]:
    return jwt.decode(state, SECRET_KEY, algorithms=["HS256"])


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def _discover(settings: OidcSettings) -> dict[str, Any]:
    global _discovery_cache
    if _discovery_cache and _discovery_cache.get("_issuer") == settings.issuer:
        return _discovery_cache
    url = f"{settings.issuer}/.well-known/openid-configuration"
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    data["_issuer"] = settings.issuer
    _discovery_cache = data
    return data


def build_authorize_url(state: str, nonce: str) -> str:
    if oidc_testing():
        # Relative path resolved by caller against API public URL when needed.
        return f"/api/v1/auth/oidc/testing-authorize?{urlencode({'state': state, 'nonce': nonce})}"

    settings = oidc_settings()
    if settings is None:
        raise RuntimeError("OIDC is not configured")
    discovery = _discover(settings)
    authorize = discovery["authorization_endpoint"]
    query = urlencode(
        {
            "client_id": settings.client_id,
            "response_type": "code",
            "redirect_uri": settings.redirect_uri,
            "scope": settings.scopes,
            "state": state,
            "nonce": nonce,
            "response_mode": "query",
        }
    )
    return f"{authorize}?{query}"


def exchange_code(code: str) -> dict[str, Any]:
    """Return token endpoint JSON (must include id_token)."""
    if oidc_testing():
        if not code.startswith("oidc-test:"):
            raise ValueError("Invalid test authorization code")
        # oidc-test:<sub>:<email>
        parts = code.split(":", 2)
        if len(parts) != 3:
            raise ValueError("Invalid test authorization code format")
        _, sub, email = parts
        now = datetime.now(UTC)
        id_token = jwt.encode(
            {
                "sub": sub,
                "email": email,
                "preferred_username": email,
                "iss": "protrack-oidc-testing",
                "aud": "protrack-oidc-testing",
                "iat": now,
                "exp": now + timedelta(minutes=5),
                "nonce": "testing",
            },
            SECRET_KEY,
            algorithm="HS256",
        )
        return {"id_token": id_token, "token_type": "bearer", "expires_in": 300}

    settings = oidc_settings()
    if settings is None:
        raise RuntimeError("OIDC is not configured")
    discovery = _discover(settings)
    token_url = discovery["token_endpoint"]
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.redirect_uri,
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.post(token_url, data=data)
        response.raise_for_status()
        return response.json()


def verify_id_token(id_token: str, *, expected_nonce: str | None = None) -> dict[str, Any]:
    if oidc_testing():
        claims = jwt.decode(id_token, SECRET_KEY, algorithms=["HS256"], audience="protrack-oidc-testing")
        return claims

    settings = oidc_settings()
    if settings is None:
        raise RuntimeError("OIDC is not configured")
    discovery = _discover(settings)
    jwks_uri = discovery["jwks_uri"]
    jwks_client = PyJWKClient(jwks_uri)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.client_id,
        issuer=settings.issuer,
    )
    if expected_nonce and claims.get("nonce") and claims.get("nonce") != expected_nonce:
        raise ValueError("OIDC nonce mismatch")
    return claims


def claims_email(claims: dict[str, Any]) -> str | None:
    for key in ("email", "preferred_username", "upn"):
        value = claims.get(key)
        if isinstance(value, str) and "@" in value:
            return value.strip().lower()
    return None


def claims_subject(claims: dict[str, Any]) -> str | None:
    sub = claims.get("oid") or claims.get("sub")
    if isinstance(sub, str) and sub.strip():
        return sub.strip()
    return None
