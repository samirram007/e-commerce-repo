"""Payment provider adapters — the core domain depends on the interface only.

The flow mirrors what hosted checkout (Razorpay Checkout / Stripe PaymentElement)
needs:

1. ``create_intent``      — create a provider-side order/payment intent; the
                            browser uses ``client_payload`` to collect the card.
2. ``verify_client_payment`` — confirm the browser's callback (signature check
                            for Razorpay, PaymentIntent status for Stripe).
3. ``parse_webhook``      — verify + normalize the provider's server-to-server
                            notification, so webhooks can confirm what the
                            browser never reported.
4. ``refund``             — return money against the original charge.

Credentials are passed in as a :class:`GatewayCredentials` resolved per company
and per mode (test/live) by ``modules/payments/gateways.py`` — adapters never
read configuration themselves. Amounts are ``Decimal`` in major units and are
converted to the provider's minor units (paise/cents) only at the boundary.

``MockGatewayAdapter`` stays deterministic and offline so dev/test flows run
without credentials. Wire a new provider by implementing
:class:`PaymentProviderAdapter` and registering it in ``_ADAPTERS``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import httpx

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.shared.money import dec, money

#: All provider HTTP calls share one hard timeout.
HTTP_TIMEOUT = 15.0
logger = logging.getLogger("erp")

#: Event ids we never echo credentials with; only these normalized types flow on.
WEBHOOK_PAYMENT_SUCCEEDED = "payment.succeeded"
WEBHOOK_PAYMENT_FAILED = "payment.failed"
WEBHOOK_REFUND_SUCCEEDED = "refund.succeeded"


@dataclass(frozen=True)
class GatewayCredentials:
    """Decrypted credentials for one provider in one mode."""

    mode: str  # "test" | "live"
    public_key: str
    secret_key: str
    webhook_secret: str | None = None


@dataclass(frozen=True)
class IntentResult:
    provider: str
    intent_id: str
    #: Everything the browser needs to complete the payment (key/order id or
    #: client_secret + publishable key). Never contains a secret.
    client_payload: dict


@dataclass(frozen=True)
class VerifyResult:
    succeeded: bool
    provider_ref: str | None = None
    amount: Decimal | None = None
    error_code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class WebhookEvent:
    event_id: str
    type: str  # payment.succeeded | payment.failed | refund.succeeded
    intent_id: str | None
    provider_ref: str | None
    amount: Decimal | None


@dataclass(frozen=True)
class ProviderChargeResult:
    provider: str
    provider_ref: str
    succeeded: bool
    error_code: str | None = None
    message: str | None = None


class PaymentProviderAdapter(Protocol):
    name: str

    def create_intent(
        self, creds: GatewayCredentials, *, amount: Decimal, currency: str, receipt: str,
        customer: dict, idempotency_key: str,
    ) -> IntentResult: ...

    def verify_client_payment(
        self, creds: GatewayCredentials, *, payload: dict
    ) -> VerifyResult: ...

    def parse_webhook(
        self, creds: GatewayCredentials, *, raw_body: bytes, headers: dict
    ) -> WebhookEvent: ...

    def refund(
        self, creds: GatewayCredentials, *, provider_ref: str, amount: Decimal,
        currency: str, idempotency_key: str,
    ) -> ProviderChargeResult: ...

    def test_connection(self, creds: GatewayCredentials) -> tuple[bool, str]: ...


# ---- key/mode sanity -------------------------------------------------------
# Reject a key that belongs to the other mode before it can ever reach a call.

_KEY_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "stripe": {"test": ("pk_test_", "sk_test_"), "live": ("pk_live_", "sk_live_")},
    "razorpay": {"test": ("rzp_test_",), "live": ("rzp_live_",)},
}


def validate_key_mode(provider: str, mode: str, public_key: str | None, secret_key: str | None) -> None:
    """Raise if stored/provided keys do not belong to `mode`.

    Stripe keys are unambiguous (``pk_test_``/``sk_test_`` vs ``pk_live_``/
    ``sk_live_``). Razorpay key ids are prefixed ``rzp_test_``/``rzp_live_``;
    its key secrets carry no prefix, so the secret is only checked when it
    looks prefixed.
    """
    rules = _KEY_RULES.get(provider)
    if not rules or mode not in rules:
        return
    expected = rules[mode]
    public_key = (public_key or "").strip()
    secret_key = (secret_key or "").strip()

    if provider == "stripe":
        pk_prefix, sk_prefix = expected
        if public_key and not public_key.startswith(pk_prefix):
            raise BusinessRuleError(
                "KEY_MODE_MISMATCH",
                f"Publishable key must start with '{pk_prefix}' for {mode} mode",
            )
        if secret_key and not secret_key.startswith(sk_prefix):
            raise BusinessRuleError(
                "KEY_MODE_MISMATCH",
                f"Secret key must start with '{sk_prefix}' for {mode} mode",
            )
        return

    # razorpay
    prefix = expected[0]
    if public_key and not public_key.startswith(prefix):
        raise BusinessRuleError(
            "KEY_MODE_MISMATCH",
            f"Razorpay key id must start with '{prefix}' for {mode} mode",
        )
    if secret_key.startswith("rzp_") and not secret_key.startswith(prefix):
        raise BusinessRuleError(
            "KEY_MODE_MISMATCH",
            f"Razorpay key secret belongs to the other mode (expected '{prefix}')",
        )


# ---- amount boundary -------------------------------------------------------
def to_minor_units(amount) -> int:
    """Major units (Decimal) → provider minor units (paise/cents)."""
    return int(money(dec(amount), 2) * 100)


def from_minor_units(minor) -> Decimal:
    """Provider minor units → major units Decimal (never float)."""
    return money(Decimal(int(minor)) / Decimal(100), 2)


def _provider_error(provider: str, response: httpx.Response) -> BusinessRuleError:
    """Map a provider HTTP error to a safe AppError (no secrets, truncated)."""
    try:
        body = response.json()
        message = body.get("error", {}).get("message") if isinstance(body, dict) else None
        code = body.get("error", {}).get("code") if isinstance(body, dict) else None
    except Exception:  # noqa: BLE001 - provider may return HTML/plain text
        message, code = None, None
    detail = str(message or response.text or "")[:300]
    suffix = f" ({code})" if code else ""
    return BusinessRuleError(
        "PAYMENT_PROVIDER_ERROR",
        f"{provider} rejected the request (HTTP {response.status_code}){suffix}: {detail}",
        status_code=502,
    )


class _HttpAdapterBase:
    """Shared httpx plumbing: one timeout, injectable transport, safe errors."""

    name: str = ""
    base_url: str = ""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url, timeout=HTTP_TIMEOUT, transport=self._transport
        )

    def _request(self, client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            # Never include the request object (it carries auth headers).
            raise BusinessRuleError(
                "PAYMENT_PROVIDER_ERROR",
                f"{self.name} is unreachable: {exc.__class__.__name__}",
                status_code=502,
            ) from exc
        return response


# ---- Razorpay --------------------------------------------------------------
class RazorpayAdapter(_HttpAdapterBase):
    """Razorpay Orders API + Checkout verification + webhook HMAC."""

    name = "razorpay"
    base_url = "https://api.razorpay.com"

    def create_intent(
        self, creds: GatewayCredentials, *, amount: Decimal, currency: str, receipt: str,
        customer: dict, idempotency_key: str,
    ) -> IntentResult:
        validate_key_mode(self.name, creds.mode, creds.public_key, creds.secret_key)
        payload: dict = {
            "amount": str(to_minor_units(amount)),
            "currency": currency.upper(),
            "receipt": (receipt or "order")[:250],
        }
        notes = {}
        if customer and customer.get("ref"):
            notes["customer_ref"] = str(customer["ref"])[:80]
        if notes:
            payload["notes"] = notes
        with self._client() as client:
            response = self._request(
                client, "POST", "/v1/orders", json=payload,
                auth=(creds.public_key, creds.secret_key),
                headers={"Idempotency-Key": idempotency_key},
            )
        if response.status_code >= 400:
            raise _provider_error(self.name, response)
        data = response.json()
        intent_id = data.get("id")
        if not intent_id:
            raise BusinessRuleError(
                "PAYMENT_PROVIDER_ERROR", "Razorpay returned no order id", status_code=502
            )
        return IntentResult(
            provider=self.name,
            intent_id=intent_id,
            client_payload={
                "provider": self.name,
                "mode": creds.mode,
                "key": creds.public_key,
                "order_id": intent_id,
                "amount": to_minor_units(amount),
                "currency": currency.upper(),
            },
        )

    def verify_client_payment(self, creds: GatewayCredentials, *, payload: dict) -> VerifyResult:
        order_id = payload.get("razorpay_order_id") or payload.get("order_id")
        payment_id = payload.get("razorpay_payment_id") or payload.get("payment_id")
        signature = payload.get("razorpay_signature") or payload.get("signature")
        if not (order_id and payment_id and signature):
            return VerifyResult(
                False, error_code="MISSING_FIELDS",
                message="razorpay_order_id, razorpay_payment_id and razorpay_signature are required",
            )
        expected = hmac.new(
            creds.secret_key.encode("utf-8"),
            f"{order_id}|{payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, str(signature)):
            return VerifyResult(False, error_code="BAD_SIGNATURE", message="Signature verification failed")
        return VerifyResult(True, provider_ref=str(payment_id))

    def parse_webhook(
        self, creds: GatewayCredentials, *, raw_body: bytes, headers: dict
    ) -> WebhookEvent:
        if not creds.webhook_secret:
            raise BusinessRuleError(
                "WEBHOOK_NOT_CONFIGURED", "No webhook secret configured for this mode"
            )
        signature = _header(headers, "X-Razorpay-Signature")
        if not signature:
            raise BusinessRuleError("WEBHOOK_BAD_SIGNATURE", "Missing X-Razorpay-Signature header")
        expected = hmac.new(
            creds.webhook_secret.encode("utf-8"), raw_body or b"", hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise BusinessRuleError("WEBHOOK_BAD_SIGNATURE", "Webhook signature verification failed")
        body = json.loads(raw_body or b"{}")
        event = str(body.get("event") or "")
        payload = body.get("payload") or {}
        payment = (payload.get("payment") or {}).get("entity") or {}
        refund = (payload.get("refund") or {}).get("entity") or {}

        if event == "payment.captured":
            event_type = WEBHOOK_PAYMENT_SUCCEEDED
        elif event == "payment.failed":
            event_type = WEBHOOK_PAYMENT_FAILED
        elif event == "refund.processed":
            event_type = WEBHOOK_REFUND_SUCCEEDED
        else:
            raise BusinessRuleError(
                "WEBHOOK_UNSUPPORTED_EVENT", f"Event '{event}' is not handled"
            )

        event_id = (
            _header(headers, "X-Razorpay-Event-Id")
            or _header(headers, "X-Razorpay-Request-Id")
            or hashlib.sha256(raw_body or b"").hexdigest()[:32]
        )
        if event_type == WEBHOOK_REFUND_SUCCEEDED:
            amount_minor = refund.get("amount")
            return WebhookEvent(
                event_id=str(event_id),
                type=event_type,
                intent_id=payment.get("order_id") or refund.get("order_id"),
                provider_ref=refund.get("id"),
                amount=from_minor_units(amount_minor) if amount_minor else None,
            )
        amount_minor = payment.get("amount")
        return WebhookEvent(
            event_id=str(event_id),
            type=event_type,
            intent_id=payment.get("order_id"),
            provider_ref=payment.get("id"),
            amount=from_minor_units(amount_minor) if amount_minor else None,
        )

    def refund(
        self, creds: GatewayCredentials, *, provider_ref: str, amount: Decimal,
        currency: str, idempotency_key: str,
    ) -> ProviderChargeResult:
        validate_key_mode(self.name, creds.mode, creds.public_key, creds.secret_key)
        with self._client() as client:
            response = self._request(
                client, "POST", f"/v1/payments/{provider_ref}/refund",
                json={"amount": str(to_minor_units(amount)), "currency": currency.upper()},
                auth=(creds.public_key, creds.secret_key),
                headers={"Idempotency-Key": idempotency_key},
            )
        if response.status_code >= 400:
            raise _provider_error(self.name, response)
        refund_id = response.json().get("id") or f"refund_{provider_ref}"
        return ProviderChargeResult(self.name, str(refund_id), True)

    def test_connection(self, creds: GatewayCredentials) -> tuple[bool, str]:
        try:
            with self._client() as client:
                response = self._request(
                    client, "GET", "/v1/orders", params={"count": 1},
                    auth=(creds.public_key, creds.secret_key),
                )
        except BusinessRuleError as exc:
            return False, exc.message
        if response.status_code == 401:
            return False, "Authentication failed — check the key id and secret"
        if response.status_code >= 400:
            return False, f"Razorpay returned HTTP {response.status_code}"
        return True, f"Connected to Razorpay ({creds.mode} mode)"


# ---- Stripe ----------------------------------------------------------------
class StripeAdapter(_HttpAdapterBase):
    """Stripe PaymentIntents (form-encoded REST) + webhook signature."""

    name = "stripe"
    base_url = "https://api.stripe.com"

    def create_intent(
        self, creds: GatewayCredentials, *, amount: Decimal, currency: str, receipt: str,
        customer: dict, idempotency_key: str,
    ) -> IntentResult:
        validate_key_mode(self.name, creds.mode, creds.public_key, creds.secret_key)
        data = {
            "amount": str(to_minor_units(amount)),
            "currency": currency.lower(),
            "automatic_payment_methods[enabled]": "true",
            "metadata[receipt]": (receipt or "")[:100],
        }
        if customer and customer.get("ref"):
            data["metadata[customer_ref]"] = str(customer["ref"])[:80]
        with self._client() as client:
            response = self._request(
                client, "POST", "/v1/payment_intents", data=data,
                headers={
                    "Authorization": f"Bearer {creds.secret_key}",
                    "Idempotency-Key": idempotency_key,
                },
            )
        if response.status_code >= 400:
            raise _provider_error(self.name, response)
        payload = response.json()
        intent_id, client_secret = payload.get("id"), payload.get("client_secret")
        if not intent_id or not client_secret:
            raise BusinessRuleError(
                "PAYMENT_PROVIDER_ERROR", "Stripe returned no payment intent", status_code=502
            )
        return IntentResult(
            provider=self.name,
            intent_id=str(intent_id),
            client_payload={
                "provider": self.name,
                "mode": creds.mode,
                "client_secret": str(client_secret),
                "publishable_key": creds.public_key,
                "payment_intent_id": str(intent_id),
            },
        )

    def verify_client_payment(self, creds: GatewayCredentials, *, payload: dict) -> VerifyResult:
        intent_id = payload.get("payment_intent_id") or payload.get("intent_id")
        if not intent_id:
            return VerifyResult(
                False, error_code="MISSING_FIELDS", message="payment_intent_id is required"
            )
        with self._client() as client:
            response = self._request(
                client, "GET", f"/v1/payment_intents/{intent_id}",
                headers={"Authorization": f"Bearer {creds.secret_key}"},
            )
        if response.status_code >= 400:
            raise _provider_error(self.name, response)
        data = response.json()
        if data.get("status") != "succeeded":
            return VerifyResult(
                False, error_code="NOT_SUCCEEDED",
                message=f"PaymentIntent status is '{data.get('status')}'",
            )
        amount_minor = data.get("amount")
        return VerifyResult(
            True,
            provider_ref=str(data.get("id")),
            amount=from_minor_units(amount_minor) if amount_minor else None,
        )

    def parse_webhook(
        self, creds: GatewayCredentials, *, raw_body: bytes, headers: dict
    ) -> WebhookEvent:
        if not creds.webhook_secret:
            raise BusinessRuleError(
                "WEBHOOK_NOT_CONFIGURED", "No webhook secret configured for this mode"
            )
        _verify_stripe_signature(
            creds.webhook_secret, raw_body or b"", _header(headers, "Stripe-Signature")
        )
        body = json.loads(raw_body or b"{}")
        event_type = str(body.get("type") or "")
        obj = (body.get("data") or {}).get("object") or {}
        amount_minor = obj.get("amount")

        if event_type == "payment_intent.succeeded":
            normalized = WEBHOOK_PAYMENT_SUCCEEDED
        elif event_type == "payment_intent.payment_failed":
            normalized = WEBHOOK_PAYMENT_FAILED
        elif event_type == "charge.refunded":
            normalized = WEBHOOK_REFUND_SUCCEEDED
        else:
            raise BusinessRuleError(
                "WEBHOOK_UNSUPPORTED_EVENT", f"Event '{event_type}' is not handled"
            )

        intent_id = obj.get("payment_intent") if normalized == WEBHOOK_REFUND_SUCCEEDED else obj.get("id")
        return WebhookEvent(
            event_id=str(body.get("id") or hashlib.sha256(raw_body or b"").hexdigest()[:32]),
            type=normalized,
            intent_id=str(intent_id) if intent_id else None,
            provider_ref=str(obj.get("id")) if obj.get("id") else None,
            amount=from_minor_units(amount_minor) if amount_minor else None,
        )

    def refund(
        self, creds: GatewayCredentials, *, provider_ref: str, amount: Decimal,
        currency: str, idempotency_key: str,
    ) -> ProviderChargeResult:
        validate_key_mode(self.name, creds.mode, creds.public_key, creds.secret_key)
        data = {
            "payment_intent": provider_ref,
            "amount": str(to_minor_units(amount)),
        }
        with self._client() as client:
            response = self._request(
                client, "POST", "/v1/refunds", data=data,
                headers={
                    "Authorization": f"Bearer {creds.secret_key}",
                    "Idempotency-Key": idempotency_key,
                },
            )
        if response.status_code >= 400:
            raise _provider_error(self.name, response)
        refund_id = response.json().get("id") or f"refund_{provider_ref}"
        return ProviderChargeResult(self.name, str(refund_id), True)

    def test_connection(self, creds: GatewayCredentials) -> tuple[bool, str]:
        try:
            with self._client() as client:
                response = self._request(
                    client, "GET", "/v1/balance",
                    headers={"Authorization": f"Bearer {creds.secret_key}"},
                )
        except BusinessRuleError as exc:
            return False, exc.message
        if response.status_code == 401:
            return False, "Authentication failed — check the secret key"
        if response.status_code >= 400:
            return False, f"Stripe returned HTTP {response.status_code}"
        return True, f"Connected to Stripe ({creds.mode} mode)"


def _header(headers: dict, name: str) -> str | None:
    if not headers:
        return None
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _verify_stripe_signature(secret: str, raw_body: bytes, header: str | None, now: int | None = None) -> None:
    """Verify ``Stripe-Signature`` (``t=…,v1=…``) with a 5-minute tolerance."""
    import time

    if not header:
        raise BusinessRuleError("WEBHOOK_BAD_SIGNATURE", "Missing Stripe-Signature header")
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        parts.setdefault(key, []).append(value)
    timestamp = parts.get("t", [""])[0]
    candidates = parts.get("v1", [])
    if not timestamp or not candidates:
        raise BusinessRuleError("WEBHOOK_BAD_SIGNATURE", "Malformed Stripe-Signature header")
    signed = f"{timestamp}.".encode("utf-8") + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise BusinessRuleError("WEBHOOK_BAD_SIGNATURE", "Webhook signature verification failed")
    try:
        issued = int(timestamp)
    except ValueError as exc:
        raise BusinessRuleError("WEBHOOK_BAD_SIGNATURE", "Malformed Stripe timestamp") from exc
    current = int(time.time()) if now is None else now
    if abs(current - issued) > 300:
        raise BusinessRuleError("WEBHOOK_STALE", "Webhook timestamp outside the 5-minute tolerance")


# ---- mock ------------------------------------------------------------------
class MockGatewayAdapter:
    """Deterministic in-process mock provider (no network, no credentials).

    ``create_intent`` derives a stable id from the idempotency key, and
    ``verify_client_payment`` always succeeds, so checkout tests exercise the
    full intent → confirm → paid path offline.
    """

    name = "mock"

    def create_intent(
        self, creds: GatewayCredentials, *, amount: Decimal, currency: str, receipt: str,
        customer: dict, idempotency_key: str,
    ) -> IntentResult:
        if dec(amount) <= 0:
            raise BusinessRuleError("INVALID_AMOUNT", "Amount must be positive")
        if not idempotency_key:
            raise BusinessRuleError("MISSING_KEY", "Idempotency key required")
        digest = hashlib.sha256(f"{idempotency_key}|{amount}|{currency}".encode()).hexdigest()[:24]
        intent_id = f"mock_order_{digest}"
        return IntentResult(
            provider=self.name,
            intent_id=intent_id,
            client_payload={
                "provider": self.name,
                "mode": creds.mode,
                "intent_id": intent_id,
                "amount": str(money(dec(amount), 2)),
                "currency": currency,
            },
        )

    def verify_client_payment(self, creds: GatewayCredentials, *, payload: dict) -> VerifyResult:
        payment_id = (
            payload.get("razorpay_payment_id")
            or payload.get("payment_id")
            or payload.get("payment_intent_id")
            or "mock_payment"
        )
        return VerifyResult(True, provider_ref=str(payment_id))

    def parse_webhook(
        self, creds: GatewayCredentials, *, raw_body: bytes, headers: dict
    ) -> WebhookEvent:
        # Dev/test only: the mock provider has no signing scheme, so the body
        # itself describes the event (still idempotent by event_id downstream).
        body = json.loads(raw_body or b"{}")
        event_type = str(body.get("type") or WEBHOOK_PAYMENT_SUCCEEDED)
        if event_type not in (WEBHOOK_PAYMENT_SUCCEEDED, WEBHOOK_PAYMENT_FAILED, WEBHOOK_REFUND_SUCCEEDED):
            raise BusinessRuleError("WEBHOOK_UNSUPPORTED_EVENT", f"Event '{event_type}' is not handled")
        amount = body.get("amount")
        return WebhookEvent(
            event_id=str(body.get("event_id") or hashlib.sha256(raw_body or b"").hexdigest()[:32]),
            type=event_type,
            intent_id=body.get("intent_id"),
            provider_ref=body.get("provider_ref"),
            amount=money(dec(amount), 2) if amount is not None else None,
        )

    def refund(
        self, creds: GatewayCredentials, *, provider_ref: str, amount: Decimal,
        currency: str, idempotency_key: str,
    ) -> ProviderChargeResult:
        if dec(amount) <= 0:
            return ProviderChargeResult(self.name, "", False, "INVALID_AMOUNT", "Amount must be positive")
        return ProviderChargeResult(self.name, f"refund_{provider_ref}", True)

    def test_connection(self, creds: GatewayCredentials) -> tuple[bool, str]:
        return True, "Mock gateway is always available"


# ---- cash on delivery --------------------------------------------------------
class CashAdapter:
    """Cash on delivery: no external call, money is collected by the courier.

    A pending cash record is opened at checkout and settled on delivery
    (``sales.collect_cash_on_delivery``); refunds are recorded as cash-out so
    accounting stays complete. Not admin-configurable (not in
    ``GATEWAY_PROVIDERS``) — it only serves refunds of COD receipts.
    """

    name = "cash"

    def create_intent(
        self, creds: GatewayCredentials, *, amount: Decimal, currency: str, receipt: str,
        customer: dict, idempotency_key: str,
    ) -> IntentResult:
        raise BusinessRuleError("CASH_NO_INTENT", "Cash on delivery has no online payment step")

    def verify_client_payment(self, creds: GatewayCredentials, *, payload: dict) -> VerifyResult:
        return VerifyResult(False, error_code="CASH_NO_INTENT", message="Cash is collected on delivery")

    def parse_webhook(
        self, creds: GatewayCredentials, *, raw_body: bytes, headers: dict
    ) -> WebhookEvent:
        raise BusinessRuleError("WEBHOOK_UNSUPPORTED_PROVIDER", "Cash on delivery has no webhooks")

    def refund(
        self, creds: GatewayCredentials, *, provider_ref: str, amount: Decimal,
        currency: str, idempotency_key: str,
    ) -> ProviderChargeResult:
        if dec(amount) <= 0:
            return ProviderChargeResult(self.name, "", False, "INVALID_AMOUNT", "Amount must be positive")
        digest = hashlib.sha256(f"cash-refund|{provider_ref}|{amount}|{idempotency_key}".encode()).hexdigest()[:16]
        return ProviderChargeResult(self.name, f"cash_refund_{digest}", True)

    def test_connection(self, creds: GatewayCredentials) -> tuple[bool, str]:
        return True, "Cash on delivery needs no connection"


ADAPTERS: dict[str, PaymentProviderAdapter] = {
    "mock": MockGatewayAdapter(),
    "razorpay": RazorpayAdapter(),
    "stripe": StripeAdapter(),
    "cash": CashAdapter(),
}


def get_adapter(name: str = "mock") -> PaymentProviderAdapter:
    adapter = ADAPTERS.get(name)
    if adapter is None:
        raise NotFoundError("Payment provider")
    return adapter