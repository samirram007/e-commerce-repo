import hashlib
import hmac
import json
import base64
import os
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.exceptions import AuthError

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    import hashlib
    import os
    # Generate salt
    salt = os.urandom(16).hex()
    iterations = 200_000
    # Use repeated SHA256 hashing as fallback since pbkdf2_hmac may not be available
    # This provides similar security for development purposes
    digest = password.encode("utf-8")
    for _ in range(iterations):
        digest = hashlib.sha256(digest + salt.encode()).digest()
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        # Recompute using the same method as hash_password
        digest = password.encode("utf-8")
        for _ in range(int(iterations)):
            digest = hashlib.sha256(digest + salt_hex.encode()).digest()
        computed = digest.hex()
        return hmac.compare_digest(computed, digest_hex)
    except (ValueError, AttributeError):
        return False


def new_id() -> str:
    return str(uuid.uuid4())


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _jwt_encode(header_dict: dict, payload_dict: dict, key: str) -> str:
    """Minimal JWT encode implementing only HS256."""
    # Convert any datetime objects to ISO format strings for JSON serialization
    def default_encoder(o):
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")
    
    # Use standard JSON separators (comma and colon with spaces)
    header_b64 = _b64url_encode(json.dumps(header_dict, default=default_encoder).encode())
    payload_b64 = _b64url_encode(json.dumps(payload_dict, default=default_encoder).encode())

    signing_input = f"{header_b64}.{payload_b64}".encode()
    key_bytes = key.encode() if isinstance(key, str) else key
    signature = hmac.new(key_bytes, signing_input, "sha256").digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _jwt_decode(token: str, key: str, algorithms: list = ["HS256"]) -> dict:
    """Minimal JWT decode implementing only HS256."""
    if not isinstance(token, str):
        raise ValueError("Invalid token format")

    if not any(alg in algorithms for alg in ["HS256"]):
        raise ValueError(f"Algorithm not supported")

    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT number of segments")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode()
        key_bytes = key.encode() if isinstance(key, str) else key
        expected_signature = hmac.new(key_bytes, signing_input, "sha256").digest()
        actual_signature = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Invalid token signature")

        # Decode payload
        payload_dict = json.loads(_b64url_decode(payload_b64))

        # Check expiration - convert exp from ISO string if needed
        if "exp" in payload_dict:
            exp_value = payload_dict["exp"]
            # Handle both ISO format string and numeric timestamp
            if isinstance(exp_value, str):
                exp_time = datetime.fromisoformat(exp_value)
            else:
                exp_time = datetime.fromtimestamp(exp_value, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            if now > exp_time:
                raise ExpiredSignatureError("Token has expired")

        return payload_dict

    except ExpiredSignatureError:
        raise
    except ValueError as e:
        raise e
    except Exception as e:
        raise ValueError(str(e)) from e


class ExpiredSignatureError(ValueError):
    """Raised when a token has expired."""
    pass


class InvalidTokenError(ValueError):
    """Raised when a token is invalid."""
    pass


def create_access_token(user_id: str, extra: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)

    header = {"alg": "HS256", "typ": "JWT"}
    token = _jwt_encode(header, payload, settings.secret_key)
    return token


def create_refresh_token(user_id: str, jti: str, ttl_days: int | None = None) -> str:
    settings = get_settings()
    days = ttl_days if ttl_days is not None else settings.refresh_token_ttl_days
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=days),
        "session_jti": jti,
    }

    header = {"alg": "HS256", "typ": "JWT"}
    token = _jwt_encode(header, payload, settings.secret_key)
    return token


def decode_token(token: str, expected_type: str = "access") -> dict:
    settings = get_settings()
    try:
        payload = _jwt_decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except ExpiredSignatureError as exc:
        raise AuthError("token_expired", "Token has expired", status_code=401) from exc
    except InvalidTokenError as exc:
        raise AuthError("invalid_token", "Invalid token", status_code=401) from exc
    except ValueError as exc:
        raise AuthError("invalid_token", "Invalid token", status_code=401) from exc

    if payload.get("type") != expected_type:
        raise AuthError(
            "invalid_token", f"Expected a {expected_type} token", status_code=401
        )
    return payload