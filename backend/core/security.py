import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

from .config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        return False


def make_token(user_id: int, kind: str, ttl: timedelta, **claims: str
               ) -> tuple[str, str, datetime]:
    """Returns (token, jti, expiry). kind is 'access', 'refresh', or the purpose of an
    emailed link ('verify', 'reset')."""
    jti = uuid.uuid4().hex
    expires = datetime.now(UTC) + ttl
    payload = {**claims, "sub": str(user_id), "kind": kind, "jti": jti, "exp": expires}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256"), jti, expires


def read_token(token: str, kind: str) -> dict[str, Any] | None:
    try:
        payload: dict[str, Any] = jwt.decode(token, get_settings().jwt_secret,
                                             algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("kind") == kind else None
