"""Razorpay gateway client: Orders API, payment lookup and signature checks.

Flow (hosted Checkout):

1. Server creates a Razorpay order for the amount in paise (`create_order`).
2. The browser opens Razorpay Checkout with that order id.
3. Razorpay returns `razorpay_order_id|razorpay_payment_id|razorpay_signature`;
   the server recomputes the HMAC and only then marks the order paid
   (`verify_payment_signature`).
4. Webhooks are verified against the raw request body
   (`verify_webhook_signature`) so they can also be replayed safely.

Only the standard library is used — no extra runtime dependency.
"""
import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from decimal import Decimal

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError

API_BASE = "https://api.razorpay.com/v1"
API_BASE_ENV = "RAZORPAY_API_BASE"  # overridable for local tests/sandboxes

# Demo mode recognises payments minted by the in-app demo checkout.
DEMO_SIGNATURE = "demo"
PAYMENT_DEMO_PREFIX = "pay_demo_"


def is_configured() -> bool:
    return get_settings().razorpay_configured


def is_demo() -> bool:
    """Simulated gateway used for demos/local testing (no credentials needed)."""
    return get_settings().razorpay_demo_mode


def _demo_id(prefix: str) -> str:
    import secrets

    return f"{prefix}_demo_{secrets.token_hex(8)}"


def _require_config() -> None:
    if not is_configured():
        raise BusinessRuleError(
            "RAZORPAY_NOT_CONFIGURED",
            "Online payments are unavailable: set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET",
        )


def amount_to_paise(amount) -> int:
    """Razorpay works in the smallest currency unit (paise for INR)."""
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    paise = int(value * 100)
    if paise <= 0:
        raise BusinessRuleError("BAD_AMOUNT", "Razorpay amount must be positive")
    return paise


def _api_base() -> str:
    import os

    return os.environ.get(API_BASE_ENV, API_BASE).rstrip("/")


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    """Authenticated call to the Razorpay API (basic auth, JSON)."""
    _require_config()
    settings = get_settings()
    url = f"{_api_base()}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    token = base64.b64encode(
        f"{settings.razorpay_key_id}:{settings.razorpay_key_secret}".encode()
    ).decode()
    request.add_header("Authorization", f"Basic {token}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=settings.razorpay_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw).get("error", {}).get("description") or raw
        except ValueError:
            detail = raw
        raise BusinessRuleError(
            "RAZORPAY_ERROR", f"Razorpay rejected the request: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise BusinessRuleError(
            "RAZORPAY_UNREACHABLE", f"Could not reach Razorpay: {exc.reason}"
        ) from exc


def create_order(
    *, amount_paise: int, currency: str, receipt: str, notes: dict | None = None
) -> dict:
    """Create a Razorpay order; `payment_capture: 1` captures automatically.

    In demo mode the order is fabricated locally with the same shape, so the
    checkout flow runs end to end without gateway credentials.
    """
    if is_demo():
        return {
            "id": _demo_id("order"),
            "entity": "order",
            "amount": int(amount_paise),
            "currency": currency,
            "receipt": receipt[:40],
            "status": "created",
            "notes": notes or {},
        }
    return _request(
        "POST",
        "/orders",
        {
            "amount": int(amount_paise),
            "currency": currency,
            "receipt": receipt[:40],
            "payment_capture": 1,
            "notes": notes or {},
        },
    )


def fetch_payment(payment_id: str) -> dict:
    if is_demo():
        return {
            "id": payment_id,
            "entity": "payment",
            "status": "captured",
            "captured": True,
        }
    return _request("GET", f"/payments/{payment_id}")


def refund(payment_id: str, *, amount_paise: int, notes: dict | None = None) -> dict:
    if is_demo():
        return {
            "id": _demo_id("rfnd"),
            "entity": "refund",
            "status": "processed",
            "amount": int(amount_paise),
            "payment_id": payment_id,
        }
    return _request(
        "POST",
        f"/payments/{payment_id}/refund",
        {"amount": int(amount_paise), "notes": notes or {}},
    )


def verify_payment_signature(*, order_id: str, payment_id: str, signature: str) -> bool:
    """`HMAC_SHA256(order_id|payment_id, key_secret)` must match the signature.

    Demo mode accepts the literal signature `demo` for a `pay_demo…` id, which
    is exactly what the in-app demo checkout returns.
    """
    _require_config()
    if not order_id or not payment_id or not signature:
        raise BusinessRuleError("RAZORPAY_BAD_SIGNATURE", "Missing Razorpay payment fields")
    if is_demo():
        if signature == "demo" and payment_id.startswith(PAYMENT_DEMO_PREFIX):
            return True
        raise BusinessRuleError(
            "RAZORPAY_BAD_SIGNATURE",
            "Demo payments must use the in-app demo checkout",
        )
    secret = get_settings().razorpay_key_secret.encode()
    expected = hmac.new(
        secret, f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise BusinessRuleError(
            "RAZORPAY_BAD_SIGNATURE",
            "Payment signature verification failed — the payment is not confirmed",
        )
    return True


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Webhooks are signed with HMAC_SHA256 over the exact request body."""
    settings = get_settings()
    if not settings.razorpay_webhook_secret:
        raise BusinessRuleError(
            "RAZORPAY_WEBHOOK_UNCONFIGURED",
            "Set RAZORPAY_WEBHOOK_SECRET to accept Razorpay webhooks",
        )
    if not signature:
        raise BusinessRuleError("RAZORPAY_BAD_SIGNATURE", "Missing X-Razorpay-Signature")
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise BusinessRuleError("RAZORPAY_BAD_SIGNATURE", "Webhook signature verification failed")
    return True
