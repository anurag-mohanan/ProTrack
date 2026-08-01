"""Public API auth dependency (API key → tenant context)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.integrations import ApiKey
from app.services import api_key_service, feature_flag_service


def _extract_raw_key(
    authorization: str | None,
    x_api_key: str | None,
) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def require_api_key(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
) -> ApiKey:
    raw = _extract_raw_key(authorization, x_api_key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    key = api_key_service.verify_api_key(db, raw)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not feature_flag_service.is_enabled(
        db, "feature.public_api", tenant_id=key.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public API is not enabled for this tenant",
        )
    from app.db.pg_rls import sync_session_rls

    sync_session_rls(db)
    db.commit()  # persist last_used_at
    return key


def require_scope(key: ApiKey, scope: str) -> None:
    scopes = api_key_service.parse_scopes(key)
    if scope not in scopes and "*" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key missing scope: {scope}",
        )
