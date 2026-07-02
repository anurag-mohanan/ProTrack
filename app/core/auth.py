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
    impersonator_id: UUID | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, str | int | list[str]] = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "role": role,
        "permissions": permissions,
        "exp": expire,
    }
    if team_id is not None:
        payload["team_id"] = str(team_id)
    if team_name is not None:
        payload["team_name"] = team_name
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
        return TokenPayload(
            sub=user_id,
            email=email,
            name=payload.get("name"),
            role=payload.get("role"),
            permissions=permissions,
            team_id=UUID(team_id_raw) if team_id_raw else None,
            team_name=payload.get("team_name"),
            impersonator_id=UUID(impersonator_id) if impersonator_id else None,
        )
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise InvalidTokenError("Could not validate credentials") from exc
