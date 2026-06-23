from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from app.schemas.auth import TokenPayload


def create_access_token(*, user_id: UUID, email: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = UUID(payload["sub"])
        email = payload.get("email")
        if email is None:
            raise InvalidTokenError("Missing email claim")
        return TokenPayload(sub=user_id, email=email)
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise InvalidTokenError("Could not validate credentials") from exc
