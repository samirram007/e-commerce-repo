import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthError

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def new_id() -> str:
    return str(uuid.uuid4())


def _create_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": new_id(),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: str, extra: dict | None = None) -> str:
    settings = get_settings()
    return _create_token(
        user_id, "access", timedelta(minutes=settings.access_token_ttl_minutes), extra
    )


def create_refresh_token(user_id: str, jti: str, ttl_days: int | None = None) -> str:
    settings = get_settings()
    days = ttl_days if ttl_days is not None else settings.refresh_token_ttl_days
    return _create_token(user_id, "refresh", timedelta(days=days), {"session_jti": jti})


def decode_token(token: str, expected_type: str = "access") -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token_expired", "Token has expired", status_code=401) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("invalid_token", "Invalid token", status_code=401) from exc
    if payload.get("type") != expected_type:
        raise AuthError("invalid_token", f"Expected a {expected_type} token", status_code=401)
    return payload
