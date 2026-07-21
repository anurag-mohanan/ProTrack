from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from app.schemas.auth import TokenPayload


def create_access_token(
    *,
    user_id: UUID,
    email: str,
    name: str,
    role: str,
    permissions: list[str],
    team_id: UUID | None = None,
    team_name: str | None = None,
    team_ids: list[UUID] | None = None,
    team_names: list[str] | None = None,
    impersonator_id: UUID | None = None,
    token_version: int = 0,
) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, str | int | list[str]] = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "role": role,
        "permissions": permissions,
        "exp": expire,
        "iat": now,
        "tv": int(token_version),
    }
    if team_id is not None:
        payload["team_id"] = str(team_id)
    if team_name is not None:
        payload["team_name"] = team_name
    if team_ids:
        payload["team_ids"] = [str(team_id_value) for team_id_value in team_ids]
    if team_names:
        payload["team_names"] = team_names
    if impersonator_id is not None:
        payload["imp"] = str(impersonator_id)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = UUID(payload["sub"])
        email = payload.get("email")
        if email is None:
            raise InvalidTokenError("Missing email claim")
        impersonator_id = payload.get("imp")
        permissions = payload.get("permissions", [])
        if not isinstance(permissions, list):
            permissions = []
        team_id_raw = payload.get("team_id")
        team_ids_raw = payload.get("team_ids", [])
        team_names_raw = payload.get("team_names", [])
        team_ids = (
            [UUID(value) for value in team_ids_raw]
            if isinstance(team_ids_raw, list)
            else []
        )
        team_names = (
            [str(value) for value in team_names_raw]
            if isinstance(team_names_raw, list)
            else []
        )
        issued_at_raw = payload.get("iat")
        issued_at = (
            datetime.fromtimestamp(issued_at_raw, tz=UTC)
            if isinstance(issued_at_raw, (int, float))
            else None
        )
        token_version_raw = payload.get("tv", 0)
        token_version = token_version_raw if isinstance(token_version_raw, int) else 0
        return TokenPayload(
            sub=user_id,
            email=email,
            name=payload.get("name"),
            role=payload.get("role"),
            permissions=permissions,
            team_id=UUID(team_id_raw) if team_id_raw else None,
            team_name=payload.get("team_name"),
            team_ids=team_ids,
            team_names=team_names,
            impersonator_id=UUID(impersonator_id) if impersonator_id else None,
            token_version=token_version,
            issued_at=issued_at,
        )
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise InvalidTokenError("Could not validate credentials") from exc
