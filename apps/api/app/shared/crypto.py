"""Fernet encryption for payment provider secrets at rest.

Secrets (Razorpay ``key_secret`` / Stripe ``sk_…`` and webhook secrets) are
encrypted before they reach the database and decrypted only inside the
gateway resolver, right before a provider call. The key comes from
``PAYMENT_ENCRYPTION_KEY``; outside production a deterministic fallback is
derived from ``SECRET_KEY`` (SHA-256 → urlsafe base64) so dev and tests work
out of the box, with a warning that the value is not a stable key.
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError

logger = logging.getLogger("erp")

_warned = False


def _derive_key(raw: str) -> bytes:
    """Turn an arbitrary string into a valid Fernet key (urlsafe base64 SHA-256)."""
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _resolve_key() -> bytes:
    global _warned
    settings = get_settings()
    configured = (settings.payment_encryption_key or "").strip()
    if configured:
        try:
            Fernet(configured.encode("utf-8"))
            return configured.encode("utf-8")
        except ValueError:
            # Not a Fernet-format key: derive one deterministically from it so a
            # passphrase still works, rather than failing every request.
            return _derive_key(configured)
    if settings.is_prod:  # guarded in Settings too; belt and braces
        raise BusinessRuleError(
            "PAYMENT_ENCRYPTION_KEY_MISSING",
            "PAYMENT_ENCRYPTION_KEY must be set in production",
        )
    if not _warned:
        _warned = True
        logger.warning(
            "PAYMENT_ENCRYPTION_KEY is not set — deriving a fallback key from "
            "SECRET_KEY. Set PAYMENT_ENCRYPTION_KEY before storing real keys: "
            "changing SECRET_KEY later would make saved secrets unreadable."
        )
    return _derive_key(settings.secret_key)


def _fernet() -> Fernet:
    return Fernet(_resolve_key())


def encrypt_secret(value: str) -> str:
    """Encrypt a provider secret for storage. Returns a Fernet token."""
    if value is None:
        raise BusinessRuleError("SECRET_REQUIRED", "No secret to encrypt")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    """Decrypt a stored Fernet token back to the provider secret."""
    if not value:
        raise BusinessRuleError("SECRET_REQUIRED", "No stored secret to decrypt")
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise BusinessRuleError(
            "SECRET_DECRYPT_FAILED",
            "Stored payment secret cannot be decrypted with the current "
            "PAYMENT_ENCRYPTION_KEY — re-enter the provider keys",
        ) from exc